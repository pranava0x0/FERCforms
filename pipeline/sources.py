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
import time
from pathlib import Path

import requests

from pipeline import config
from pipeline.extract import extract_pages
from pipeline.models import AuditReport, SourceSeed

logger = logging.getLogger(__name__)

_PDF_MAGIC = b"%PDF-"
_MIN_PDF_BYTES = 1024


class SourceFetchError(Exception):
    """A source document PDF could not be downloaded after retries."""


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
        logger.info("cached: %s", dest.name)
        return dest

    last_error: str | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        time.sleep(config.REQUEST_DELAY_SECONDS)
        try:
            resp = session.get(seed.pdf_url, timeout=config.REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            last_error = f"request error: {exc}"
            time.sleep(config.BACKOFF_BASE_SECONDS)
            continue

        ctype = resp.headers.get("content-type", "")
        if (
            resp.status_code == 200
            and ("application/pdf" in ctype or resp.content[:5] == _PDF_MAGIC)
            and resp.content[:5] == _PDF_MAGIC
        ):
            tmp = dest.with_suffix(".pdf.part")
            tmp.write_bytes(resp.content)
            tmp.replace(dest)
            logger.info("downloaded %s (%d bytes)", dest.name, len(resp.content))
            return dest

        if resp.status_code == 429:
            wait = config.BACKOFF_BASE_SECONDS * attempt
            last_error = "HTTP 429 (rate limited)"
            logger.warning("429 for %s; backing off %ss", seed.id, wait)
            time.sleep(wait)
            continue

        last_error = f"unexpected response: {resp.status_code} {ctype} ({len(resp.content)}b)"
        logger.warning("attempt %d/%d for %s: %s", attempt, config.MAX_RETRIES, seed.id, last_error)
        time.sleep(config.BACKOFF_BASE_SECONDS)

    raise SourceFetchError(f"{seed.id}: {last_error}")


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


def load_seed(path: Path) -> list[SourceSeed]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [SourceSeed.model_validate(d) for d in data]


def process_seed(
    path: Path, *, raw_dir: Path, processed_dir: Path, force: bool = False
) -> tuple[int, list[tuple[str, str]]]:
    """Fetch + extract + structure every document in one seed file."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = make_session()
    seeds = load_seed(path)
    logger.info("processing %d document(s) from %s", len(seeds), path.name)
    ok = 0
    failures: list[tuple[str, str]] = []
    for i, seed in enumerate(seeds, 1):
        logger.info("[%d/%d] %s — %s", i, len(seeds), seed.id, seed.company)
        try:
            pdf_path = fetch_doc(session, seed, raw_dir, force=force)
            pages = extract_pages(pdf_path)
            scanned = [p.page for p in pages if p.is_image_only]
            report = structure_seed(seed, page_count=len(pages), scanned_pages=scanned)
            out_dir = processed_dir / seed.id
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "report.json").write_text(
                report.model_dump_json(indent=2), encoding="utf-8"
            )
            logger.info("ingested %s (%d pages, metadata-only)", seed.id, len(pages))
            ok += 1
        except Exception as exc:  # noqa: BLE001 — one doc never aborts the batch
            failures.append((seed.id, str(exc)))
            logger.error("FAILED %s: %s", seed.id, exc)
    return ok, failures


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

    total_ok = 0
    total_fail: list[tuple[str, str]] = []
    for sp in seed_paths:
        ok, failures = process_seed(
            sp, raw_dir=config.RAW_DIR, processed_dir=config.PROCESSED_DIR, force=args.force
        )
        total_ok += ok
        total_fail += failures

    logger.info("done: %d ingested, %d failed", total_ok, len(total_fail))
    for sid, error in total_fail:
        logger.error("  %s: %s", sid, error)


if __name__ == "__main__":
    main()
