"""Classify each downloaded report PDF by FERC form -> industry (cheap page scan).

Lets the pipeline scope to Form 1 / electric without fully structuring every
report: read only the first few pages of each PDF, detect the form, map to
industry. Output: data/processed/classification.json (keyed by report id, in
listing order = newest first). Idempotent; per-PDF errors are logged, not fatal.
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from pipeline import config, forms
from pipeline.models import ListingEntry

logger = logging.getLogger(__name__)

PAGES_TO_SCAN = 8  # form/statute/USofA signals appear in the cover + scope sections


def classify_pdf(path: Path) -> tuple[list[str], Optional[str]]:
    parts: list[str] = []
    with fitz.open(path) as doc:
        for i in range(min(PAGES_TO_SCAN, doc.page_count)):
            parts.append(doc[i].get_text("text") or "")
    text = "\n".join(parts)
    return forms.detect_forms(text), forms.primary_industry(text)


def load_listing(path: Path) -> list[ListingEntry]:
    return [ListingEntry.model_validate(d) for d in json.loads(Path(path).read_text(encoding="utf-8"))]


def classify_corpus(listing: list[ListingEntry], raw_dir: Path) -> dict:
    out: dict[str, dict] = {}
    for entry in listing:
        pdf = raw_dir / f"{entry.accession_number}.pdf"
        if not pdf.exists():
            continue
        try:
            forms_found, industry = classify_pdf(pdf)
        except Exception as exc:  # noqa: BLE001
            logger.warning("classify failed for %s: %s", entry.id, exc)
            continue
        out[entry.id] = {
            "accession": entry.accession_number,
            "company": entry.company,
            "docket": entry.docket,
            "issued_date": entry.issued_date.isoformat() if entry.issued_date else None,
            "audit_type": forms.audit_type_from_docket(entry.docket),
            "forms": forms_found,
            "industry": industry,
        }
    return out


def electric_ids(classification: dict) -> list[str]:
    """Report ids classified as electric (Form 1), in classification order."""
    return [rid for rid, c in classification.items() if c.get("industry") == "electric"]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Classify downloaded PDFs by FERC form/industry")
    ap.add_argument("--listing", type=Path, default=config.LISTING_PATH)
    ap.add_argument("--out", type=Path, default=config.PROCESSED_DIR / "classification.json")
    args = ap.parse_args()

    listing = load_listing(args.listing)
    classification = classify_corpus(listing, config.RAW_DIR)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(classification, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    by_industry = Counter(c["industry"] or "unknown" for c in classification.values())
    by_type = Counter(c["audit_type"] or "unknown" for c in classification.values())
    logger.info("classified %d/%d PDFs", len(classification), len(listing))
    logger.info("by industry: %s", dict(by_industry))
    logger.info("by audit type: %s", dict(by_type))
    logger.info("electric (Form 1): %d", len(electric_ids(classification)))


if __name__ == "__main__":
    main()
