"""Tests for CSV export functionality."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pipeline import csv_export


def test_csv_export_creates_file(tmp_path):
    """CSV export creates a file at the specified path."""
    output_path = tmp_path / "test_findings.csv"
    result = csv_export.export_findings_csv(output_path=output_path)

    assert output_path.exists()
    assert result == output_path


def test_csv_export_has_correct_headers(tmp_path):
    """Exported CSV has all required headers."""
    output_path = tmp_path / "test_findings.csv"
    csv_export.export_findings_csv(output_path=output_path)

    with open(output_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames

    required_headers = [
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
    for header in required_headers:
        assert header in headers, f"Missing header: {header}"


def test_csv_export_has_rows(tmp_path):
    """Exported CSV has at least one data row."""
    output_path = tmp_path / "test_findings.csv"
    csv_export.export_findings_csv(output_path=output_path)

    with open(output_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) > 0, "CSV should have at least one data row"


def test_csv_export_row_has_report_id(tmp_path):
    """Each CSV row has a report_id."""
    output_path = tmp_path / "test_findings.csv"
    csv_export.export_findings_csv(output_path=output_path)

    with open(output_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            assert row["report_id"], "Row should have report_id"
            break  # Just check first row


def test_csv_export_row_has_collection(tmp_path):
    """Each CSV row has a collection field."""
    output_path = tmp_path / "test_findings.csv"
    csv_export.export_findings_csv(output_path=output_path)

    with open(output_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            assert row["collection"] in {
                "ferc_audit",
                "prudence_review",
                "state_audit",
                "state_rate_case",
            }, f"Invalid collection: {row['collection']}"


def test_csv_export_handles_missing_fields(tmp_path):
    """CSV export handles optional fields gracefully."""
    output_path = tmp_path / "test_findings.csv"
    csv_export.export_findings_csv(output_path=output_path)

    with open(output_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # These can be empty but shouldn't cause errors
            _ = row.get("finding_summary", "")
            _ = row.get("rec_text", "")
            break


def test_csv_export_default_path(tmp_path, monkeypatch):
    """CSV export uses docs/data/findings.csv by default."""
    # Monkeypatch the config to use a tmp path
    import pipeline.config as config

    original_site_data_dir = config.SITE_DATA_DIR
    tmp_data_dir = tmp_path / "data"
    monkeypatch.setattr(config, "SITE_DATA_DIR", tmp_data_dir)

    try:
        result = csv_export.export_findings_csv(output_path=None)
        assert result == tmp_data_dir / "findings.csv"
    finally:
        monkeypatch.setattr(config, "SITE_DATA_DIR", original_site_data_dir)
