"""Backfill FY2014-2018 audit reports into listing.json (ferc.gov-origin only).

The live ferc.gov/audits page lists only 2019+ reports (see ISSUES.md). Older
reports are recovered from a saved Internet Archive Wayback snapshot of
ferc.gov/audits (2021-12-07), which listed reports back to FY2014 via legacy
`opennat?fileID=` links. Those archived links resolve only to the eLibrary SPA
shell (no PDF bytes), so each report's eLibrary accession was resolved out-of-band
via the eLibrary Docket Search API and saved to
data/sources/elibrary_docket_accessions_*.json. This module joins the two and
appends ListingEntry records to listing.json.

Provenance (CLAUDE.md → Data handling): every backfilled record records the
Wayback snapshot it was listed on (`archived_via`) and a human-readable
`source_note`. Only ferc.gov-origin documents are ingested — any archived link
whose host is not a *.ferc.gov host is skipped.

Run AFTER `pipeline.listing` (which regenerates listing.json from the live
snapshot) and BEFORE fetch/classify/extract/structure. Idempotent: an accession
already in listing.json is never added twice.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from pydantic import ValidationError

from pipeline import config
from pipeline.listing import _accession_to_date, _slugify, write_listing
from pipeline.models import ListingEntry

logger = logging.getLogger(__name__)

# Provenance of the Wayback snapshot used for the backfill listing.
WAYBACK_SNAPSHOT = config.DATA_DIR / "sources" / "ferc-audits-wayback-20211207.html"
WAYBACK_TIMESTAMP = "20211207020015"
WAYBACK_CAPTURED = date(2021, 12, 7)
WAYBACK_URL = (
    f"https://web.archive.org/web/{WAYBACK_TIMESTAMP}/https://www.ferc.gov/audits"
)
ACCESSION_MAP = config.DATA_DIR / "sources" / "elibrary_docket_accessions_20260525.json"

# Anchor text on the archived page: "FA14-2 Entergy Corporation" (sometimes with
# a leading en-dash, e.g. "FA15-12 – Plantation Pipe Line Company").
_DOCKET_RE = re.compile(r"^(?P<docket>[A-Z]{2}\d{2}-\d+)\s+[–—-]?\s*(?P<company>.*)$")


def _norm_docket(docket: str | None) -> str:
    return re.sub(r"-000$", "", (docket or "").upper())


def _is_ferc_host(href: str) -> bool:
    """True only for *.ferc.gov hosts — enforces the ferc.gov-only rule."""
    host = urlparse(href).netloc.lower()
    return host == "ferc.gov" or host.endswith(".ferc.gov")


def build_backfill_entries(
    html: str, accession_map: dict[str, str], current_dockets: set[str]
) -> list[ListingEntry]:
    """Join archived /audits docket rows with resolved accessions -> ListingEntry."""
    soup = BeautifulSoup(html, "lxml")
    entries: list[ListingEntry] = []
    seen: set[str] = set()
    skipped_non_ferc = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "opennat" not in href.lower():
            continue
        if not _is_ferc_host(href):  # ferc.gov-origin guard
            skipped_non_ferc += 1
            logger.warning("skipping non-ferc.gov archived link: %s", href[:80])
            continue
        text = " ".join(a.get_text(" ", strip=True).split())
        m = _DOCKET_RE.match(text)
        if not m:
            continue
        docket = _norm_docket(m.group("docket"))
        company = m.group("company").strip()
        if docket in current_dockets:
            continue  # already listed on the live page; the live entry wins
        accession = accession_map.get(docket)
        if not accession:
            logger.warning("no accession resolved for %s (%s); skipping", docket, company)
            continue
        if accession in seen:
            continue
        seen.add(accession)
        file_id = (parse_qs(urlparse(href).query).get("fileID") or [None])[0]
        issued = _accession_to_date(accession)
        slug_bits = [issued.isoformat() if issued else accession, _slugify(company)[:48], _slugify(docket)]
        try:
            entries.append(
                ListingEntry(
                    id="_".join(b for b in slug_bits if b),
                    company=company,
                    company_raw=f"{m.group('docket')} {company}".strip(),
                    docket=docket,
                    accession_number=accession,
                    issued_date=issued,
                    source_page_url=(
                        "https://elibrary.ferc.gov/eLibrary/filelist"
                        f"?accession_number={accession}&optimized=false"
                    ),
                    pdf_download_url=(
                        "https://elibrary.ferc.gov/eLibraryWebAPI/api/File/DownloadPDF"
                        f"?accesssionNumber={accession}"
                    ),
                    captured_at=WAYBACK_CAPTURED,
                    source_note=(
                        "Listed on FERC ferc.gov/audits via Internet Archive Wayback "
                        f"Machine (snapshot {WAYBACK_CAPTURED.isoformat()}; origin "
                        f"www.ferc.gov); report PDF from FERC eLibrary, accession {accession}"
                        + (f" (fileID {file_id})" if file_id else "") + "."
                    ),
                    archived_via=WAYBACK_URL,
                )
            )
        except ValidationError as exc:
            logger.warning("skipping %s: %s", accession, exc)
    logger.info(
        "backfill: %d entries built (%d non-ferc.gov links skipped)", len(entries), skipped_non_ferc
    )
    return entries


def merge_into_listing(existing: list[dict], backfill: list[ListingEntry]) -> list[dict]:
    """Append backfill entries not already present (by accession); sort newest-first."""
    have = {d["accession_number"] for d in existing}
    added = 0
    merged = list(existing)
    for e in backfill:
        if e.accession_number in have:
            continue
        merged.append(json.loads(e.model_dump_json()))
        have.add(e.accession_number)
        added += 1
    merged.sort(key=lambda d: (d.get("issued_date") or "", d["accession_number"]), reverse=True)
    logger.info("merged %d new backfill entries (listing now %d)", added, len(merged))
    return merged


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Backfill FY2014-2018 reports into listing.json")
    ap.add_argument("--snapshot", type=Path, default=WAYBACK_SNAPSHOT)
    ap.add_argument("--accessions", type=Path, default=ACCESSION_MAP)
    ap.add_argument("--listing", type=Path, default=config.LISTING_PATH)
    args = ap.parse_args()

    existing = json.loads(args.listing.read_text(encoding="utf-8")) if args.listing.exists() else []
    current_dockets = {_norm_docket(d.get("docket")) for d in existing if d.get("docket")}
    accession_map = json.loads(args.accessions.read_text(encoding="utf-8"))["dockets"]
    html = args.snapshot.read_text(encoding="utf-8", errors="replace")

    backfill = build_backfill_entries(html, accession_map, current_dockets)
    merged = merge_into_listing(existing, backfill)
    args.listing.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("wrote %s (%d entries)", args.listing, len(merged))


if __name__ == "__main__":
    main()
