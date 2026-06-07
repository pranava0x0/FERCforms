"""Ingest non-FERC-audit documents (prudence reviews / state PUC audits).

The FERC audit corpus seeds from `data/listing.json` and fetches via eLibrary's
F5 cookie dance (`pipeline/fetch.py`). Other regulators publish PDFs at stable
URLs, so this module runs a simpler, generic path from per-source seeds in
`data/seeds/<source>.json` (one `SourceSeed` record per document):

    seed -> fetch (plain GET, rate-limited, cached) -> extract pages
         -> AuditReport (metadata-only) -> data/processed/<id>/report.json

`parse=False` (the default) ingests a document metadata-only — captured with its
source link and full provenance but NOT machine-extracted into findings. This is
deliberate for legal orders and testimony (see the multi-source policy): their
shape doesn't fit the FERC executive-summary -> findings -> recommendations
parser, and emitting garbled "verbatim" findings would break the project's
quote discipline. Findings extraction for the clean management-audit subset
(PA Bureau of Audits, MI consultant reports) is a separate BACKLOG item.

Idempotent and cached (existing PDFs are skipped); one failed document never
aborts the run. Output report.json is committed; the raw PDF and per-page text
are gitignored (re-fetchable from the seed).
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from pipeline import config, fetch
from pipeline.extract import extract_pages, pymupdf_pages
from pipeline.models import AuditReport, ListingEntry, ReportText, SourceSeed
from pipeline.state_structure import structure_mo_audit

logger = logging.getLogger(__name__)

_PDF_MAGIC = b"%PDF-"
_MIN_PDF_BYTES = 1024
# A real document PDF is bigger than this; a smaller one that still has the %PDF
# magic is usually a scanned cover sheet or an eDocket "placeholder" (e.g. AZ's
# edocket.azcc.gov/docketpdf/ returns blank ~5 KB pages). We still keep it, but
# log a warning so it surfaces for page-1 verification instead of passing
# silently. Set above the observed ~5 KB placeholder; the smallest real orders
# we've ingested are tens of KB, so this won't false-flag legitimate short docs.
_SUSPICIOUS_PDF_BYTES = 8192


def _return_cached(dest: Path) -> Path:
    """Return an already-downloaded PDF, re-warning if it's suspiciously small —
    so a previously-cached blank placeholder doesn't go silent on re-runs."""
    n = dest.stat().st_size
    if n < _SUSPICIOUS_PDF_BYTES:
        logger.warning(
            "cached: %s is only %d bytes — possible placeholder/cover page; verify page 1", dest.name, n
        )
    else:
        logger.info("cached: %s", dest.name)
    return dest


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff with jitter, capped — gives a throttling host time to
    recover (the failure mode behind transient connection-reset / 000 / 429 seen
    on puc.idaho.gov, apps.puc.state.or.us, apiproxy.utc.wa.gov under request bursts)."""
    return min(config.BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), 90) + random.uniform(0, 3)


class SourceFetchError(Exception):
    """A source document PDF could not be downloaded after retries."""


# Only ingest documents from OFFICIAL GOVERNMENT sources — never third-party
# mirrors or aggregators (DocumentCloud, SEC EDGAR, scribd, news sites, etc.).
# This generalizes the existing "ferc.gov-origin only" rule (pipeline/backfill.py)
# to every regulator. Accepted: any `.gov` host (federal + most state/agency
# domains, e.g. puc.pa.gov, michigan.gov, ferc.gov) and the legacy state-government
# pattern `*.state.<xx>.us` (e.g. Ohio PUCO's dis.puc.state.oh.us).
_STATE_LEGACY_GOV_RE = re.compile(r"\.state\.[a-z]{2}\.us$")

# A NARROW, explicit allowlist of official US-government regulatory commissions that
# publish on a `.org` (not `.gov`) host. Each entry is the commission's OWN domain —
# a verified government source, not a third-party mirror. Kept as an exact-domain set
# (matches the domain or any subdomain) so the guard stays tight: a random `.org`
# (documentcloud.org, a law firm, a news site) is still rejected. Admitting these
# serves the rule's intent (official government, never third-party) where a commission
# simply predates/never adopted `.gov`. Decision logged in ISSUES.md (2026-06-02).
_OFFICIAL_GOV_ORG_DOMAINS = frozenset({
    "dcpsc.org",  # District of Columbia Public Service Commission (edocket.dcpsc.org, www.dcpsc.org)
})


def is_official_gov(url: str) -> bool:
    """True if the URL's host is an official government domain (see notes above)."""
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    if host == "gov" or host.endswith(".gov") or _STATE_LEGACY_GOV_RE.search(host):
        return True
    return any(host == d or host.endswith("." + d) for d in _OFFICIAL_GOV_ORG_DOMAINS)


def _assert_official_gov(seed: SourceSeed) -> None:
    """Reject any seed whose PDF or source-page URL isn't an official .gov host."""
    for label, url in (("pdf_url", seed.pdf_url), ("source_page_url", seed.source_page_url)):
        if not is_official_gov(url):
            raise ValueError(
                f"{seed.id}: {label} {url!r} is not an official government source "
                f"— only .gov (and *.state.xx.us) sources are allowed"
            )


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": config.USER_AGENT,
            "Accept": "application/pdf,*/*",
        }
    )
    return session


def fetch_doc(
    session: requests.Session, seed: SourceSeed, raw_dir: Path, *, force: bool = False
) -> Path:
    """Download one source PDF to raw_dir/<id>.pdf. Raises SourceFetchError."""
    dest = raw_dir / f"{seed.id}.pdf"
    if not force and dest.exists() and dest.stat().st_size > _MIN_PDF_BYTES:
        return _return_cached(dest)

    last_error: str | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        time.sleep(config.REQUEST_DELAY_SECONDS)
        try:
            resp = session.get(seed.pdf_url, timeout=config.REQUEST_TIMEOUT_SECONDS)
        except requests.exceptions.SSLError as exc:
            # Broken / hostname-mismatched TLS cert (AZ images.edocket.azcc.gov,
            # MS InSite). Retrying never fixes a cert — fail fast with the fix.
            raise SourceFetchError(
                f"{seed.id}: TLS verification failed ({exc.__class__.__name__}) — the host's "
                f"certificate is invalid or doesn't match the hostname. Look for a valid-cert host "
                f"alias (e.g. AZ's docket.images.azcc.gov), else browser-capture + seed fetch=false."
            ) from exc
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            # Connection refused/reset or read timeout — usually host throttling
            # after a burst. Exponential backoff gives it time to recover.
            wait = _backoff_seconds(attempt)
            last_error = f"{exc.__class__.__name__} (connection/timeout — possible throttling)"
            logger.warning(
                "attempt %d/%d for %s: %s — backing off %.0fs", attempt, config.MAX_RETRIES, seed.id, last_error, wait
            )
            time.sleep(wait)
            continue
        except requests.RequestException as exc:
            last_error = f"request error: {exc}"
            time.sleep(_backoff_seconds(attempt))
            continue

        ctype = resp.headers.get("content-type", "")
        if resp.status_code == 200 and resp.content[:5] == _PDF_MAGIC:
            n = len(resp.content)
            tmp = dest.with_suffix(".pdf.part")
            tmp.write_bytes(resp.content)
            tmp.replace(dest)
            if n < _SUSPICIOUS_PDF_BYTES:
                logger.warning(
                    "downloaded %s but only %d bytes — possible placeholder/cover page; verify page 1",
                    dest.name, n,
                )
            else:
                logger.info("downloaded %s (%d bytes)", dest.name, n)
            return dest

        if resp.status_code in (401, 403):
            # WAF / login wall (OH PUCO F5, NC Cloudflare, IA efs.iowa.gov, NM
            # PRCe360). A plain GET can't pass it — fail fast with the workaround.
            raise SourceFetchError(
                f"{seed.id}: HTTP {resp.status_code} ({ctype or 'no content-type'}) — looks like a "
                f"WAF or login wall. Open in a real browser (Chrome MCP) and seed fetch=false, or "
                f"find a host that isn't walled."
            )

        if resp.status_code == 429:
            wait = _backoff_seconds(attempt)
            last_error = "HTTP 429 (rate limited)"
            logger.warning("429 for %s; backing off %.0fs", seed.id, wait)
            time.sleep(wait)
            continue

        last_error = f"unexpected response: {resp.status_code} {ctype} ({len(resp.content)}b)"
        logger.warning("attempt %d/%d for %s: %s", attempt, config.MAX_RETRIES, seed.id, last_error)
        time.sleep(_backoff_seconds(attempt))

    raise SourceFetchError(f"{seed.id}: {last_error}")


def _as_listing_entry(seed: SourceSeed) -> ListingEntry:
    """Adapt an eLibrary-backed seed to a ListingEntry so the FERC fetch path
    (F5 cookie dance + DownloadPDF) can download it. Used only when seed.accession
    is set (e.g. FERC prudence orders)."""
    return ListingEntry(
        id=seed.id,
        company=seed.company,
        company_raw=seed.company,
        docket=seed.docket,
        accession_number=seed.accession,  # type: ignore[arg-type]  (guarded by caller)
        issued_date=seed.issued_date,
        source_page_url=seed.source_page_url,
        pdf_download_url=seed.pdf_url,
        captured_at=seed.captured_at,
        source_note=seed.source_note,
        archived_via=seed.archived_via,
    )


def structure_seed(seed: SourceSeed, page_count: int, scanned_pages: list[int]) -> AuditReport:
    """Build a metadata-only AuditReport from a seed + its extracted page stats.

    Findings are intentionally empty (`structured=False`): these documents are
    captured with their source for the pattern library, not parsed into findings
    (see module docstring). The UI renders them as "Listed for reference".
    """
    return AuditReport(
        collection=seed.collection,
        jurisdiction=seed.jurisdiction,
        source=seed.source,
        doc_type=seed.doc_type,
        id=seed.id,
        company=seed.company,
        company_raw=seed.company,
        docket=seed.docket,
        docket_full=None,
        issued_date=seed.issued_date,
        source_page_url=seed.source_page_url,
        pdf_download_url=seed.pdf_url,
        captured_at=seed.captured_at,
        source_note=seed.source_note,
        archived_via=seed.archived_via,
        industry=seed.industry,
        page_count=page_count,
        scanned_pages=scanned_pages,
        ocr_used=False,
        finding_count=0,
        findings=[],
        structured=False,
    )


# Single-attempt timeout for eLibrary DownloadPDF. eLibrary generates the combined
# PDF server-side; normal orders return in seconds, but huge ALJ decisions can take
# minutes. For metadata-only records the download is a *bonus* (page count + a local
# provenance copy) — the verified accession + eLibrary source link is the real
# provenance — so we try once and fall back to metadata-only rather than retry-storm.
ELIBRARY_SINGLE_TIMEOUT: int = 90


def _fetch_elibrary_once(
    session: requests.Session, seed: SourceSeed, raw_dir: Path, *, force: bool = False
) -> Path:
    """One-shot eLibrary download (F5 cookie dance + DownloadPDF). Raises on miss."""
    acc = seed.accession
    dest = raw_dir / f"{acc}.pdf"
    if not force and dest.exists() and dest.stat().st_size > _MIN_PDF_BYTES:
        return _return_cached(dest)
    filelist = f"{config.ELIBRARY_ORIGIN}/eLibrary/filelist?accession_number={acc}&optimized=false"
    if not session.cookies:  # seed the F5 session cookie once
        session.get(filelist, timeout=ELIBRARY_SINGLE_TIMEOUT).raise_for_status()
    time.sleep(config.REQUEST_DELAY_SECONDS)
    resp = session.post(
        seed.pdf_url,
        json={"serverLocation": ""},
        headers={"Referer": filelist, "Content-Type": "application/json"},
        timeout=ELIBRARY_SINGLE_TIMEOUT,
    )
    if resp.status_code == 200 and resp.content[:5] == _PDF_MAGIC:
        tmp = dest.with_suffix(".pdf.part")
        tmp.write_bytes(resp.content)
        tmp.replace(dest)
        logger.info("downloaded %s (%d bytes)", dest.name, len(resp.content))
        return dest
    raise SourceFetchError(
        f"{acc}: {resp.status_code} {resp.headers.get('content-type', '')} ({len(resp.content)}b)"
    )


def load_seed(path: Path) -> list[SourceSeed]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    seeds = [SourceSeed.model_validate(d) for d in data]
    for seed in seeds:  # official-government-source guard (fail loud, like backfill's ferc.gov check)
        _assert_official_gov(seed)
    return seeds


def process_seed(
    path: Path, *, raw_dir: Path, processed_dir: Path, force: bool = False
) -> tuple[int, list[str]]:
    """Fetch (best-effort) + extract + structure every document in one seed file.

    The download is best-effort for these metadata-only records: if the PDF can't
    be fetched (eLibrary slow on a huge decision, a transient error), we still
    write the record from its seed (page_count=0) — the verified source link is
    the provenance. Returns (#written, [ids written WITHOUT a fetched PDF]).
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = make_session()
    elib_session: requests.Session | None = None  # lazily created (shares the F5 cookie)
    seeds = load_seed(path)
    logger.info("processing %d document(s) from %s", len(seeds), path.name)
    written = 0
    no_pdf: list[str] = []
    for i, seed in enumerate(seeds, 1):
        logger.info("[%d/%d] %s — %s", i, len(seeds), seed.id, seed.company)
        page_count, scanned, pages = 0, [], []  # type: ignore[var-annotated]
        pdf_path = None
        try:
            if not seed.fetch:
                # URL captured out-of-band (e.g. a WAF-blocked source opened in a browser).
                # Don't hit the blocked endpoint — write metadata-only straight from the seed.
                raise SourceFetchError(f"{seed.id}: fetch disabled (browser-captured URL)")
            if seed.accession:
                if elib_session is None:
                    elib_session = fetch.make_session()
                pdf_path = _fetch_elibrary_once(elib_session, seed, raw_dir, force=force)
            else:
                pdf_path = fetch_doc(session, seed, raw_dir, force=force)
            pages = extract_pages(pdf_path)
            page_count = len(pages)
            scanned = [p.page for p in pages if p.is_image_only]
        except Exception as exc:  # noqa: BLE001 — fetch is best-effort for metadata-only records
            logger.warning(
                "could not fetch/extract %s (%s) — writing metadata-only with no page count",
                seed.id, exc,
            )
            no_pdf.append(seed.id)

        out_dir = processed_dir / seed.id
        out_dir.mkdir(parents=True, exist_ok=True)

        # parse=True seeds (currently PA M&O audits) get findings extracted from the
        # PDF; everything else — and any parse miss — is written metadata-only. The
        # extracted text is saved (re-runnable + feeds the no-regression test, like
        # the FERC path); a parser failure never aborts the run.
        report: AuditReport | None = None
        if seed.parse and pdf_path is not None:
            # Re-extract with PyMuPDF (clean table linearization for the parser),
            # save it as text.json (re-runnable + feeds the no-regression test).
            parse_pages = pymupdf_pages(pdf_path)
            (out_dir / "text.json").write_text(
                ReportText(
                    id=seed.id, accession_number=seed.accession or seed.id,
                    page_count=len(parse_pages), ocr_used=False,
                    scanned_pages=[p.page for p in parse_pages if p.is_image_only],
                    pages=parse_pages,
                ).model_dump_json(indent=2),
                encoding="utf-8",
            )
            try:
                report = structure_mo_audit(seed, parse_pages, scanned)
            except Exception as exc:  # noqa: BLE001 — parser miss falls back to metadata-only
                logger.warning("parse failed for %s (%s) — metadata-only", seed.id, exc)
            if report is None:
                logger.info("%s: parse yielded no findings — metadata-only", seed.id)

        if report is None:
            report = structure_seed(seed, page_count=page_count, scanned_pages=scanned)
            kind = "metadata-only"
        else:
            kind = (
                f"{report.finding_count} findings, "
                f"{sum(len(f.recommendations) for f in report.findings)} recs"
            )
        (out_dir / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
        logger.info("ingested %s (%d pages, %s)", seed.id, page_count, kind)
        written += 1
    return written, no_pdf


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Ingest prudence / state-PUC source documents")
    ap.add_argument(
        "--seed",
        type=Path,
        default=None,
        help="a single seed file (default: every data/seeds/*.json)",
    )
    ap.add_argument("--force", action="store_true", help="re-download even if cached")
    args = ap.parse_args()

    seed_paths = [args.seed] if args.seed else sorted(config.SEEDS_DIR.glob("*.json"))
    if not seed_paths:
        logger.warning("no seed files found in %s", config.SEEDS_DIR)
        return

    total_written = 0
    total_no_pdf: list[str] = []
    for sp in seed_paths:
        written, no_pdf = process_seed(
            sp, raw_dir=config.RAW_DIR, processed_dir=config.PROCESSED_DIR, force=args.force
        )
        total_written += written
        total_no_pdf += no_pdf

    logger.info(
        "done: %d ingested (%d metadata-only without a fetched PDF)",
        total_written, len(total_no_pdf),
    )
    for sid in total_no_pdf:
        logger.warning("  no PDF fetched (record still written from seed): %s", sid)


if __name__ == "__main__":
    main()
