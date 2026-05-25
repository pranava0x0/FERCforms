"""Build data/listing.json from a saved ferc.gov/audits snapshot.

The live /audits page is behind Cloudflare (see ISSUES.md), so the listing is
parsed from a captured snapshot in data/sources/. Each audit report links to
eLibrary via an accession number, and the report's issue date is embedded in
that accession (YYYYMMDD-####). Re-runnable and idempotent.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from pydantic import ValidationError

from pipeline import config
from pipeline.models import ListingEntry

logger = logging.getLogger(__name__)

# Provenance of the bundled snapshot (Wayback timestamp of the saved HTML).
DEFAULT_SNAPSHOT = config.DATA_DIR / "sources" / "ferc-audits-20260203.html"
SNAPSHOT_CAPTURED = date(2026, 2, 3)

# Anchor text looks like: "Portland General Electric Company (PA23-10)".
_ANCHOR_RE = re.compile(
    r"^(?P<company>.*?)\s*\((?P<docket>[A-Z]{2}\d{2}-\d+(?:-\d+)?)\)\s*$"
)
_ACCESSION_DATE_RE = re.compile(r"^(\d{8})-")


def _accession_to_date(accession: str) -> Optional[date]:
    m = _ACCESSION_DATE_RE.match(accession)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def parse_listing(html: str, captured_at: date) -> list[ListingEntry]:
    """Parse audit-report rows out of an /audits snapshot, newest first."""
    soup = BeautifulSoup(html, "lxml")
    entries: dict[str, ListingEntry] = {}
    skipped = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "filelist" not in href.lower():
            continue
        accession = (parse_qs(urlparse(href).query).get("accession_number") or [None])[0]
        if not accession:
            skipped += 1
            continue
        text = a.get_text(strip=True).rstrip("\\").strip()
        m = _ANCHOR_RE.match(text)
        company = m.group("company").strip() if m else text
        docket = m.group("docket") if m else None
        issued = _accession_to_date(accession)
        slug_bits = [issued.isoformat() if issued else accession, _slugify(company)[:48]]
        if docket:
            slug_bits.append(_slugify(docket))
        try:
            entry = ListingEntry(
                id="_".join(b for b in slug_bits if b),
                company=company,
                company_raw=text,
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
                captured_at=captured_at,
                source_note=(
                    f"Listed on FERC {config.AUDITS_LISTING_URL} "
                    f"(listing captured {captured_at.isoformat()})."
                ),
                archived_via=None,
            )
        except ValidationError as exc:
            logger.warning("skipping accession %s: %s", accession, exc)
            skipped += 1
            continue
        entries[accession] = entry  # dedupe by accession number

    result = sorted(
        entries.values(),
        key=lambda e: (e.issued_date or date.min, e.accession_number),
        reverse=True,
    )
    logger.info("parsed %d reports (%d links skipped)", len(result), skipped)
    return result


def write_listing(entries: list[ListingEntry], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [json.loads(e.model_dump_json()) for e in entries]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Build listing.json from an /audits snapshot")
    ap.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    ap.add_argument("--out", type=Path, default=config.LISTING_PATH)
    args = ap.parse_args()

    html = args.snapshot.read_text(encoding="utf-8", errors="replace")
    entries = parse_listing(html, SNAPSHOT_CAPTURED)
    write_listing(entries, args.out)
    logger.info("wrote %s (%d entries)", args.out, len(entries))


if __name__ == "__main__":
    main()
