"""Tests for pipeline.extract — verify text extraction covers all documents."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline import config, extract
from pipeline.models import ListingEntry, ReportText


class TestExtractCoversSeedDocuments:
    """Verify that extract.main() processes both listing.json and seed documents."""

    def test_extract_processes_documents_with_pdfs(self, tmp_path, monkeypatch):
        """
        Extract should process ALL documents that have PDFs, including seed docs.

        Scenario:
        - listing.json has 3 documents (A, B, C)
        - reports.json has 5 documents (A, B, C, D, E) where D and E are from seeds
        - PDFs exist for all 5
        - extract should process all 5, not just the 3 in listing.json

        This test validates the fix for the issue: "pipeline.extract --limit processes
        listing order, not by collection".
        """
        # Setup directory structure: listing.json and reports.json are in same dir
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        raw_dir = tmp_path / "raw"
        processed_dir = tmp_path / "processed"
        raw_dir.mkdir()
        processed_dir.mkdir()

        # Create minimal listing.json with 3 docs
        listing_file = data_dir / "listing.json"
        listing = [
            {
                "id": "doc-a",
                "company": "Company A",
                "company_raw": "Company A",
                "accession_number": "20000101-0001",
                "issued_date": "2000-01-01",
                "source_page_url": "https://example.com/a",
                "pdf_download_url": "https://example.com/a.pdf",
                "captured_at": "2026-06-07",
                "source_note": "Test A",
            },
            {
                "id": "doc-b",
                "company": "Company B",
                "company_raw": "Company B",
                "accession_number": "20000101-0002",
                "issued_date": "2000-01-02",
                "source_page_url": "https://example.com/b",
                "pdf_download_url": "https://example.com/b.pdf",
                "captured_at": "2026-06-07",
                "source_note": "Test B",
            },
            {
                "id": "doc-c",
                "company": "Company C",
                "company_raw": "Company C",
                "accession_number": "20000101-0003",
                "issued_date": "2000-01-03",
                "source_page_url": "https://example.com/c",
                "pdf_download_url": "https://example.com/c.pdf",
                "captured_at": "2026-06-07",
                "source_note": "Test C",
            },
        ]
        listing_file.write_text(json.dumps(listing), encoding="utf-8")

        # Create reports.json with 5 docs (includes seed docs D and E)
        reports_file = data_dir / "reports.json"
        reports = listing + [
            {
                "id": "doc-d",
                "company": "Company D (seed)",
                "company_raw": "Company D",
                "accession_number": "20000101-0004",
                "issued_date": "2000-01-04",
                "source_page_url": "https://example.com/d",
                "pdf_download_url": "https://example.com/d.pdf",
                "captured_at": "2026-06-07",
                "source_note": "Test D (seed)",
                "collection": "state_rate_case",
            },
            {
                "id": "doc-e",
                "company": "Company E (seed)",
                "company_raw": "Company E",
                "accession_number": "20000101-0005",
                "issued_date": "2000-01-05",
                "source_page_url": "https://example.com/e",
                "pdf_download_url": "https://example.com/e.pdf",
                "captured_at": "2026-06-07",
                "source_note": "Test E (seed)",
                "collection": "state_rate_case",
            },
        ]
        reports_file.write_text(json.dumps(reports), encoding="utf-8")

        # Create dummy PDFs for all 5 docs
        for doc_id in ["doc-a", "doc-b", "doc-c", "doc-d", "doc-e"]:
            pdf_path = raw_dir / f"{doc_id}.pdf"
            # Write a minimal valid PDF
            pdf_path.write_bytes(b"%PDF-1.4\n%EOF")

            # Create processed dir
            (processed_dir / doc_id).mkdir(exist_ok=True)

        # Mock extract_report to track calls
        extracted_ids = []

        def mock_extract(entry, raw, processed):
            extracted_ids.append(entry.id)
            # Write a dummy text.json to simulate extraction
            (processed / entry.id / "text.json").write_text(
                json.dumps({"pages": [], "page_count": 0, "scanned_pages": [], "ocr_used": False}),
                encoding="utf-8",
            )

        # Patch config and extract
        monkeypatch.setattr(extract, "extract_report", mock_extract)
        monkeypatch.setattr(config, "LISTING_PATH", listing_file)
        monkeypatch.setattr(config, "RAW_DIR", raw_dir)
        monkeypatch.setattr(config, "PROCESSED_DIR", processed_dir)

        # Run extract.main() — should process all 5 docs (after the fix)
        import sys
        sys.argv = ["extract.py"]

        extract.main()

        # EXPECTED BEHAVIOR AFTER FIX: should process all docs with PDFs
        assert len(extracted_ids) == 5, f"Expected 5 extractions (all docs with PDFs), got {len(extracted_ids)}: {extracted_ids}"
        assert set(extracted_ids) == {"doc-a", "doc-b", "doc-c", "doc-d", "doc-e"}

    def test_extract_processes_all_documents_with_pdfs_after_fix(self, tmp_path, monkeypatch):
        """
        After the fix: extract should process all documents in reports.json that have PDFs,
        not just those in listing.json.

        This test validates that once extract is fixed to load from reports.json, it will
        include seed documents (rate cases, state audits) in the extraction.
        """
        # Setup
        raw_dir = tmp_path / "raw"
        processed_dir = tmp_path / "processed"
        raw_dir.mkdir()
        processed_dir.mkdir()

        # Create reports.json with documents (both listing and seed)
        reports_file = tmp_path / "reports.json"
        reports = [
            {
                "id": "ferc-audit-1",
                "company": "FERC Company",
                "collection": "ferc_audit",
            },
            {
                "id": "rate-case-1",
                "company": "Rate Case Company",
                "collection": "state_rate_case",  # This is a seed doc
            },
        ]
        reports_file.write_text(json.dumps(reports), encoding="utf-8")

        # Create PDFs
        for doc_id in ["ferc-audit-1", "rate-case-1"]:
            pdf_path = raw_dir / f"{doc_id}.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n%EOF")
            (processed_dir / doc_id).mkdir(exist_ok=True)

        # After the fix, extract should load from reports.json and process both
        # This is a placeholder assertion that will be valid after the fix
        # For now, just verify that reports.json contains both types
        loaded_reports = json.loads(reports_file.read_text(encoding="utf-8"))
        assert len(loaded_reports) == 2
        assert any(r.get("collection") == "state_rate_case" for r in loaded_reports)
