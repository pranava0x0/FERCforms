"""Tests for extract_report PDF filename lookup."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline import config, extract
from pipeline.models import ListingEntry, PageText, ReportText


class TestExtractPdfLookup:
    """Verify extract_report finds PDFs by both ID and accession_number."""

    def test_extract_prefers_id_pdf_over_accession(self, tmp_path, monkeypatch):
        """extract_report should try {id}.pdf before {accession_number}.pdf."""
        raw_dir = tmp_path / "raw"
        processed_dir = tmp_path / "processed"
        raw_dir.mkdir()
        processed_dir.mkdir()

        # Create both filenames - ID-based (seed docs) and accession-based (FERC audits)
        id_pdf = raw_dir / "my-rate-case-2025.pdf"
        accession_pdf = raw_dir / "20250415-1234.pdf"

        id_pdf.write_bytes(b"%PDF-1.4\n%EOF")
        accession_pdf.write_bytes(b"%PDF-1.4\n%EOF")

        # Create processed dir for report
        (processed_dir / "my-rate-case-2025").mkdir()

        # Entry with both ID and accession_number
        entry = ListingEntry(
            id="my-rate-case-2025",
            company="Test Utility",
            company_raw="Test Utility",
            accession_number="20250415-1234",
            source_page_url="https://example.com",
            pdf_download_url="https://example.com/pdf",
            captured_at="2025-04-15",
            source_note="test",
        )

        # Mock extract_pages to track which PDF was used
        extracted_pdfs = []

        def mock_extract(pdf_path):
            extracted_pdfs.append(str(pdf_path.name))
            # Return minimal ReportText
            return [PageText(page=1, char_count=0, is_image_only=False, extractor="test", text="")]

        monkeypatch.setattr(extract, "extract_pages", mock_extract)

        # Run extraction
        extract.extract_report(entry, raw_dir, processed_dir)

        # Should use ID-based filename, not accession
        assert len(extracted_pdfs) == 1
        assert extracted_pdfs[0] == "my-rate-case-2025.pdf", "Should prefer {id}.pdf"

    def test_extract_falls_back_to_accession_if_id_missing(self, tmp_path, monkeypatch):
        """If {id}.pdf doesn't exist, fall back to {accession_number}.pdf."""
        raw_dir = tmp_path / "raw"
        processed_dir = tmp_path / "processed"
        raw_dir.mkdir()
        processed_dir.mkdir()

        # Only create accession-based PDF (no ID-based)
        accession_pdf = raw_dir / "20250415-1234.pdf"
        accession_pdf.write_bytes(b"%PDF-1.4\n%EOF")

        (processed_dir / "my-rate-case-2025").mkdir()

        entry = ListingEntry(
            id="my-rate-case-2025",
            company="Test Utility",
            company_raw="Test Utility",
            accession_number="20250415-1234",
            source_page_url="https://example.com",
            pdf_download_url="https://example.com/pdf",
            captured_at="2025-04-15",
            source_note="test",
        )

        extracted_pdfs = []

        def mock_extract(pdf_path):
            extracted_pdfs.append(str(pdf_path.name))
            return [PageText(page=1, char_count=0, is_image_only=False, extractor="test", text="")]

        monkeypatch.setattr(extract, "extract_pages", mock_extract)

        extract.extract_report(entry, raw_dir, processed_dir)

        # Should fall back to accession_number.pdf
        assert len(extracted_pdfs) == 1
        assert extracted_pdfs[0] == "20250415-1234.pdf", "Should fall back to {accession_number}.pdf"

    def test_extract_raises_if_no_pdf_found(self, tmp_path):
        """extract_report raises FileNotFoundError if neither PDF exists."""
        raw_dir = tmp_path / "raw"
        processed_dir = tmp_path / "processed"
        raw_dir.mkdir()
        processed_dir.mkdir()
        (processed_dir / "my-rate-case-2025").mkdir()

        entry = ListingEntry(
            id="my-rate-case-2025",
            company="Test Utility",
            company_raw="Test Utility",
            accession_number="20250415-1234",
            source_page_url="https://example.com",
            pdf_download_url="https://example.com/pdf",
            captured_at="2025-04-15",
            source_note="test",
        )

        with pytest.raises(FileNotFoundError) as exc_info:
            extract.extract_report(entry, raw_dir, processed_dir)

        assert "missing pdf" in str(exc_info.value).lower()
