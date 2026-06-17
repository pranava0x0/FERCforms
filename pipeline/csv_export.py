"""Export findings and recommendations to CSV for analysis."""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Optional

from pipeline import config
from pipeline.models import AuditReport

logger = logging.getLogger(__name__)


def export_findings_csv(output_path: Optional[Path] = None) -> Path:
    """Export all findings and recommendations to a CSV file.

    One row per recommendation (findings may have multiple recs).
    Columns: report_id, company, collection, jurisdiction, doc_type, finding_title,
             rec_number, rec_text, source_page_url, captured_at

    Args:
        output_path: where to write the CSV. Defaults to docs/data/findings.csv

    Returns:
        Path to the written CSV file.
    """
    if output_path is None:
        output_path = config.SITE_DATA_DIR / "findings.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "report_id",
        "company",
        "collection",
        "jurisdiction",
        "doc_type",
        "industry",
        "finding_index",
        "finding_title",
        "finding_summary",
        "rec_number",
        "rec_text",
        "source_page_url",
        "captured_at",
    ]

    count = 0
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()

        for report_path in sorted(config.PROCESSED_DIR.glob("*/report.json")):
            try:
                report_data = json.loads(report_path.read_text(encoding="utf-8"))
                report = AuditReport.model_validate(report_data)
            except Exception as e:
                logger.warning("failed to load %s: %s", report_path, e)
                continue

            if not report.findings:
                continue

            for finding in report.findings:
                # If no recommendations, write one row per finding
                if not finding.recommendations:
                    writer.writerow(
                        {
                            "report_id": report.id,
                            "company": report.company or "",
                            "collection": report.collection,
                            "jurisdiction": report.jurisdiction,
                            "doc_type": report.doc_type or "",
                            "industry": report.industry or "",
                            "finding_index": finding.index,
                            "finding_title": finding.title or "",
                            "finding_summary": finding.summary or "",
                            "rec_number": "",
                            "rec_text": "",
                            "source_page_url": report.source_page_url or "",
                            "captured_at": report.captured_at or "",
                        }
                    )
                    count += 1
                else:
                    # Write one row per recommendation
                    for rec in finding.recommendations:
                        writer.writerow(
                            {
                                "report_id": report.id,
                                "company": report.company or "",
                                "collection": report.collection,
                                "jurisdiction": report.jurisdiction,
                                "doc_type": report.doc_type or "",
                                "industry": report.industry or "",
                                "finding_index": finding.index,
                                "finding_title": finding.title or "",
                                "finding_summary": finding.summary or "",
                                "rec_number": rec.number or "",
                                "rec_text": rec.text or "",
                                "source_page_url": report.source_page_url or "",
                                "captured_at": report.captured_at or "",
                            }
                        )
                        count += 1

    logger.info("exported %d recommendations to %s", count, output_path)
    return output_path


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    output = export_findings_csv()
    print(f"✓ Exported to {output}")
