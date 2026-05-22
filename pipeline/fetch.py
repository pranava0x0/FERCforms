"""Download audit-report PDFs from eLibrary into data/raw/.

eLibrary sits behind an F5 WAF (see ISSUES.md / DATA_STRUCTURE §5.1): GET a
filelist page to seed the session cookie, then POST the DownloadPDF API with
app-like headers and body {"serverLocation": ""}. The response is the combined
PDF for the accession.

Rate-limited, cached (existing files are skipped), and idempotent. One failed
report never aborts the run — failures are logged and summarized.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import requests

from pipeline import config
from pipeline.models import ListingEntry

logger = logging.getLogger(__name__)

_PDF_MAGIC = b"%PDF-"
_MIN_PDF_BYTES = 1024


class FetchError(Exception):
    """A report PDF could not be downloaded after retries."""


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": config.USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Origin": config.ELIBRARY_ORIGIN,
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    return session


def _filelist_url(accession: str) -> str:
    return (
        f"{config.ELIBRARY_ORIGIN}/eLibrary/filelist"
        f"?accession_number={accession}&optimized=false"
    )


def _warm(session: requests.Session, accession: str) -> None:
    """GET the filelist page to (re)seed the F5 session cookie."""
    resp = session.get(_filelist_url(accession), timeout=config.REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()


def download_pdf(
    session: requests.Session,
    entry: ListingEntry,
    dest_dir: Path,
    *,
    force: bool = False,
) -> Path:
    """Download one report PDF. Returns the path; raises FetchError on failure."""
    dest = dest_dir / f"{entry.accession_number}.pdf"
    if not force and dest.exists() and dest.stat().st_size > _MIN_PDF_BYTES:
        logger.info("cached: %s", dest.name)
        return dest

    headers = {
        "Referer": _filelist_url(entry.accession_number),
        "Content-Type": "application/json",
    }
    last_error: str | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        # Seed the cookie on the first attempt (if unseeded) and again on retries.
        if attempt > 1 or not session.cookies:
            try:
                _warm(session, entry.accession_number)
            except requests.RequestException as exc:
                last_error = f"warm-up failed: {exc}"
                time.sleep(config.BACKOFF_BASE_SECONDS)
                continue
        time.sleep(config.REQUEST_DELAY_SECONDS)
        try:
            resp = session.post(
                entry.pdf_download_url,
                json={"serverLocation": ""},
                headers=headers,
                timeout=config.REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            last_error = f"request error: {exc}"
            time.sleep(config.BACKOFF_BASE_SECONDS)
            continue

        ctype = resp.headers.get("content-type", "")
        if (
            resp.status_code == 200
            and "application/pdf" in ctype
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
            logger.warning("429 for %s; backing off %ss", entry.accession_number, wait)
            time.sleep(wait)
            continue

        last_error = f"unexpected response: {resp.status_code} {ctype} ({len(resp.content)}b)"
        logger.warning("attempt %d/%d for %s: %s", attempt, config.MAX_RETRIES, entry.accession_number, last_error)
        time.sleep(config.BACKOFF_BASE_SECONDS)

    raise FetchError(f"{entry.accession_number}: {last_error}")


def load_listing(path: Path) -> list[ListingEntry]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ListingEntry.model_validate(d) for d in data]


def fetch_all(
    entries: list[ListingEntry], dest_dir: Path, *, force: bool = False
) -> tuple[int, list[tuple[str, str]]]:
    """Download every entry. Returns (#ok, [(accession, error), ...])."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    session = make_session()
    ok = 0
    failures: list[tuple[str, str]] = []
    for i, entry in enumerate(entries, 1):
        logger.info("[%d/%d] %s — %s", i, len(entries), entry.accession_number, entry.company)
        try:
            download_pdf(session, entry, dest_dir, force=force)
            ok += 1
        except FetchError as exc:
            failures.append((entry.accession_number, str(exc)))
            logger.error("FAILED %s", exc)
    return ok, failures


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Download audit-report PDFs from eLibrary")
    ap.add_argument("--listing", type=Path, default=config.LISTING_PATH)
    ap.add_argument("--limit", type=int, default=None, help="only the N most-recent reports")
    ap.add_argument("--force", action="store_true", help="re-download even if cached")
    args = ap.parse_args()

    entries = load_listing(args.listing)
    if args.limit is not None:
        entries = entries[: args.limit]
    logger.info("fetching %d report(s) into %s", len(entries), config.RAW_DIR)

    ok, failures = fetch_all(entries, config.RAW_DIR, force=args.force)
    logger.info("done: %d ok, %d failed", ok, len(failures))
    for accession, error in failures:
        logger.error("  %s", error)


if __name__ == "__main__":
    main()
