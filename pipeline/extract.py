"""Extract per-page text from downloaded report PDFs.

pdfplumber is the primary extractor; PyMuPDF (fitz) is the fallback for pages it
mishandles. A page that clears neither text threshold is flagged image-only
(scanned) for a future OCR pass — v1 does not OCR (see BACKLOG.md). Per-page
errors are logged and skipped, never fatal.
"""
from __future__ import annotations

import argparse
import json
import logging
import warnings
from pathlib import Path
from typing import Optional

import pdfplumber

from pipeline import config
from pipeline.models import ListingEntry, PageText, ReportText

logger = logging.getLogger(__name__)

# pdfplumber/pdfminer are chatty about recoverable PDF quirks; quiet the noise.
logging.getLogger("pdfminer").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")


def _pymupdf_page_text(pdf_path: Path, page_index: int) -> str:
    """Fallback extractor for a single page (0-based index)."""
    import fitz  # PyMuPDF

    with fitz.open(pdf_path) as doc:
        return doc[page_index].get_text("text") or ""


def extract_pages(pdf_path: Path) -> list[PageText]:
    pages: list[PageText] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text, extractor = "", "none"
            try:
                text = page.extract_text() or ""
                extractor = "pdfplumber"
            except Exception as exc:  # noqa: BLE001 — never let one page abort
                logger.warning("pdfplumber failed on %s p%d: %s", pdf_path.name, i + 1, exc)

            if len(text.strip()) < config.MIN_TEXT_CHARS_PER_PAGE:
                try:
                    alt = _pymupdf_page_text(pdf_path, i)
                    if len(alt.strip()) > len(text.strip()):
                        text, extractor = alt, "pymupdf"
                except Exception as exc:  # noqa: BLE001
                    logger.warning("pymupdf failed on %s p%d: %s", pdf_path.name, i + 1, exc)

            stripped = text.strip()
            image_only = len(stripped) < config.MIN_TEXT_CHARS_PER_PAGE
            pages.append(
                PageText(
                    page=i + 1,
                    char_count=len(stripped),
                    is_image_only=image_only,
                    extractor=extractor if not image_only else "none",
                    text=text,
                )
            )
    return pages


def extract_report(entry: ListingEntry, raw_dir: Path, out_dir: Path) -> ReportText:
    pdf_path = raw_dir / f"{entry.accession_number}.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"missing PDF for {entry.accession_number}: {pdf_path}")

    pages = extract_pages(pdf_path)
    scanned = [p.page for p in pages if p.is_image_only]
    report = ReportText(
        id=entry.id,
        accession_number=entry.accession_number,
        page_count=len(pages),
        scanned_pages=scanned,
        ocr_used=False,
        pages=pages,
    )

    report_dir = out_dir / entry.id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "text.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    logger.info(
        "extracted %s: %d pages, %d image-only", entry.id, report.page_count, len(scanned)
    )
    return report


def load_listing(path: Path) -> list[ListingEntry]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ListingEntry.model_validate(d) for d in data]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Extract per-page text from report PDFs")
    ap.add_argument("--listing", type=Path, default=config.LISTING_PATH)
    ap.add_argument("--limit", type=int, default=None, help="only the N most-recent reports")
    ap.add_argument(
        "--electric-only",
        action="store_true",
        help="restrict to Form 1 / electric reports (uses classification.json)",
    )
    args = ap.parse_args()

    entries = load_listing(args.listing)
    if args.electric_only:
        classification_path = config.PROCESSED_DIR / "classification.json"
        if not classification_path.exists():
            logger.error("classification.json missing — run `python -m pipeline.classify` first")
            return
        classification = json.loads(classification_path.read_text(encoding="utf-8"))
        electric = {rid for rid, c in classification.items() if c.get("industry") == "electric"}
        entries = [e for e in entries if e.id in electric]
    if args.limit is not None:
        entries = entries[: args.limit]

    ok = 0
    for entry in entries:
        try:
            extract_report(entry, config.RAW_DIR, config.PROCESSED_DIR)
            ok += 1
        except (FileNotFoundError, Exception) as exc:  # noqa: BLE001
            logger.error("extract failed for %s: %s", entry.id, exc)
    logger.info("extracted %d/%d reports", ok, len(entries))


if __name__ == "__main__":
    main()
