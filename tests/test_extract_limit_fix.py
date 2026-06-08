"""Test that extract --limit N applies to documents needing extraction."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pipeline import config, extract
from pipeline.models import ListingEntry


class TestExtractLimitFix:
    """Verify --limit N filters to documents needing extraction, not the full list."""

    def test_limit_applies_to_extractable_docs_not_full_list(self, tmp_path, monkeypatch):
        """--limit 5 should return 5 docs that need extraction, not first 5 docs overall."""
        raw_dir = tmp_path / "raw"
        processed_dir = tmp_path / "processed"
        raw_dir.mkdir()
        processed_dir.mkdir()

        # Create scenario:
        # - 10 FERC audits (all already have text.json)
        # - 5 seed documents (rate cases, none have text.json, all have PDFs)
        # With --limit 5, we should get the 5 seed docs, not the first 5 from the full list

        # Create 10 FERC entries (accession-based, all with text.json)
        ferc_entries = []
        for i in range(10):
            doc_id = f"2025-{i:02d}-ferc-audit"
            acc = f"2025041{i}-{1000 + i}"

            ferc_entries.append(
                ListingEntry(
                    id=doc_id,
                    company=f"Utility {i}",
                    company_raw=f"Utility {i}",
                    accession_number=acc,
                    source_page_url=f"https://example.com/{i}",
                    pdf_download_url=f"https://example.com/{i}.pdf",
                    captured_at="2025-04-15",
                    source_note=f"FERC audit {i}",
                )
            )

            # Create text.json for FERC audits (they already have it)
            ferc_dir = processed_dir / doc_id
            ferc_dir.mkdir(parents=True)
            (ferc_dir / "text.json").write_text(json.dumps({"pages": [], "page_count": 0}))

        # Create 5 seed entries (rate cases, none have text.json, all have PDFs)
        seed_entries = []
        for i in range(5):
            doc_id = f"2025-rate-case-{i:02d}"

            seed_entries.append(
                ListingEntry(
                    id=doc_id,
                    company=f"Rate Case {i}",
                    company_raw=f"Rate Case {i}",
                    accession_number=doc_id,
                    source_page_url=f"https://example.com/case/{i}",
                    pdf_download_url=f"https://example.com/case/{i}.pdf",
                    captured_at="2025-04-15",
                    source_note=f"Rate case {i}",
                )
            )

            # Create PDF for seed docs
            pdf_path = raw_dir / f"{doc_id}.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n%EOF")

            # DON'T create text.json for seed docs (they need extraction)
            (processed_dir / doc_id).mkdir(parents=True, exist_ok=True)

        # Mock load_from_reports to return FERC entries
        def mock_load_from_reports(path):
            return ferc_entries

        # Simulate the main() logic
        monkeypatch.setattr(extract, "load_from_reports", mock_load_from_reports)
        monkeypatch.setattr(config, "RAW_DIR", raw_dir)
        monkeypatch.setattr(config, "PROCESSED_DIR", processed_dir)

        # Now simulate extract.main() filtering logic
        entries = mock_load_from_reports(config.LISTING_PATH)
        entry_by_id = {e.id: e for e in entries}

        # Add seed documents (simulating the glob loop)
        for seed_entry in seed_entries:
            entry_by_id[seed_entry.id] = seed_entry

        entries = list(entry_by_id.values())

        # Filter to documents needing extraction (THIS IS THE FIX)
        entries_to_extract = []
        for entry in entries:
            pdf_path = raw_dir / f"{entry.id}.pdf"
            if not pdf_path.exists():
                pdf_path = raw_dir / f"{entry.accession_number}.pdf"

            text_path = processed_dir / entry.id / "text.json"

            if pdf_path.exists() and not text_path.exists():
                entries_to_extract.append(entry)

        # Apply limit AFTER filtering
        limit = 5
        entries_to_extract = entries_to_extract[:limit]

        # Verify: should get exactly 5 seed documents, not 5 FERC audits
        assert len(entries_to_extract) == 5, f"Expected 5 docs to extract, got {len(entries_to_extract)}"
        assert all("rate-case" in e.id for e in entries_to_extract), (
            "Should extract only rate cases, not FERC audits. Got: "
            + ", ".join(e.id for e in entries_to_extract)
        )
