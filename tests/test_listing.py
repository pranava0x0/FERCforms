"""Tests for the audit-listing parser (pipeline/listing.py)."""
from __future__ import annotations

from datetime import date

import pytest

from pipeline.listing import (
    DEFAULT_SNAPSHOT,
    SNAPSHOT_CAPTURED,
    _accession_to_date,
    _slugify,
    parse_listing,
)


@pytest.fixture(scope="module")
def entries():
    html = DEFAULT_SNAPSHOT.read_text(encoding="utf-8", errors="replace")
    return parse_listing(html, SNAPSHOT_CAPTURED)


def test_parses_expected_count(entries):
    # 71 audit reports linked on the 2026-02-03 snapshot.
    assert len(entries) == 71


def test_all_have_required_fields(entries):
    for e in entries:
        assert e.accession_number
        assert e.company
        assert e.pdf_download_url.endswith(e.accession_number)
        assert "DownloadPDF" in e.pdf_download_url
        assert e.captured_at == SNAPSHOT_CAPTURED


def test_provenance_note_populated(entries):
    # Every live-sourced record states its ferc.gov origin; none claim a Wayback
    # snapshot (only the FY2014-2018 backfill sets archived_via).
    for e in entries:
        assert "ferc.gov/audits" in e.source_note
        assert e.captured_at.isoformat() in e.source_note
        assert e.archived_via is None


def test_sorted_newest_first(entries):
    dated = [e.issued_date for e in entries if e.issued_date]
    assert dated == sorted(dated, reverse=True)


def test_two_most_recent(entries):
    assert entries[0].accession_number == "20250929-3000"  # Kern River
    assert entries[1].accession_number == "20250925-3005"  # Medallion


def test_known_entry_parsed(entries):
    by_acc = {e.accession_number: e for e in entries}
    miso = by_acc.get("20250410-3014")
    assert miso is not None
    assert miso.docket == "PA21-2"
    assert miso.issued_date == date(2025, 4, 10)
    assert "Midcontinent" in miso.company


def test_accession_to_date_edges():
    assert _accession_to_date("20250410-3014") == date(2025, 4, 10)
    assert _accession_to_date("notanaccession") is None
    assert _accession_to_date("99999999-0000") is None  # invalid calendar date


def test_dedupe_by_accession():
    html = (
        '<a href="https://elibrary.ferc.gov/eLibrary/filelist?accession_number=20200101-0001">Foo Co (PA20-1)</a>'
        '<a href="https://elibrary.ferc.gov/eLibrary/filelist?accession_number=20200101-0001">Foo Co (PA20-1)</a>'
    )
    out = parse_listing(html, date(2026, 1, 1))
    assert len(out) == 1


def test_anchor_without_docket_falls_back():
    html = '<a href="https://elibrary.ferc.gov/eLibrary/filelist?accession_number=20200202-0002">Some Company With No Docket</a>'
    out = parse_listing(html, date(2026, 1, 1))
    assert len(out) == 1
    assert out[0].docket is None
    assert out[0].company == "Some Company With No Docket"


def test_slugify():
    assert _slugify("Duke Energy Progress, LLC") == "duke-energy-progress-llc"
    assert _slugify("  A & B  ") == "a-b"
