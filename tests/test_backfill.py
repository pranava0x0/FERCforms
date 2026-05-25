"""Tests for the FY2014-2018 Wayback backfill (pipeline/backfill.py)."""
from __future__ import annotations

from datetime import date

from pipeline import backfill
from pipeline.models import ListingEntry

# One ferc.gov row to keep, plus rows that must each be skipped for a distinct
# reason: non-ferc.gov host (origin guard), already-live docket, no accession.
_HTML = """
<html><body>
<a href="https://elibrary.ferc.gov/idmws/common/opennat.asp?fileID=111">FA14-2 Entergy Corporation</a>
<a href="https://evil.example.com/idmws/common/opennat.asp?fileID=222">FA14-9 Sketchy Pipeline Co</a>
<a href="https://elibrary.ferc.gov/idmws/common/opennat.asp?fileID=333">FA17-1 Already Live Company</a>
<a href="https://elibrary.ferc.gov/idmws/common/opennat.asp?fileID=444">PA15-99 No Accession Co</a>
<a href="https://elibrary.ferc.gov/idmws/common/opennat.asp?fileID=555">FA15-12 – Plantation Pipe Line Company</a>
</body></html>
"""

_ACCESSIONS = {
    "FA14-2": "20150730-3041",
    "FA14-9": "20140101-3000",   # has an accession, but host is non-ferc.gov -> still skipped
    "FA17-1": "20190101-3000",   # but docket is already live -> skipped
    "FA15-12": "20161223-3023",
}


def _entries():
    return backfill.build_backfill_entries(_HTML, _ACCESSIONS, current_dockets={"FA17-1"})


def test_origin_guard_and_filters():
    entries = _entries()
    dockets = {e.docket for e in entries}
    # Only the two clean ferc.gov, non-live, accession-resolved rows survive.
    assert dockets == {"FA14-2", "FA15-12"}


def test_non_ferc_host_skipped():
    # FA14-9 has a valid accession but a non-ferc.gov host: the origin guard wins.
    assert all(e.docket != "FA14-9" for e in _entries())


def test_provenance_fields_set():
    entry = next(e for e in _entries() if e.docket == "FA14-2")
    assert entry.accession_number == "20150730-3041"
    assert entry.issued_date == date(2015, 7, 30)          # derived from accession
    assert entry.captured_at == backfill.WAYBACK_CAPTURED
    assert entry.archived_via == backfill.WAYBACK_URL
    assert "Wayback" in entry.source_note and "ferc.gov" in entry.source_note
    assert entry.source_page_url.endswith("accession_number=20150730-3041&optimized=false")


def test_endash_company_name_cleaned():
    entry = next(e for e in _entries() if e.docket == "FA15-12")
    assert entry.company == "Plantation Pipe Line Company"  # leading en-dash stripped


def test_merge_dedupes_by_accession_and_sorts():
    existing = [
        {"accession_number": "20250929-3000", "issued_date": "2025-09-29", "docket": "FA23-10"},
        {"accession_number": "20150730-3041", "issued_date": "2015-07-30", "docket": "FA14-2"},
    ]
    backfilled = _entries()  # includes FA14-2 (already in existing) + FA15-12 (new)
    merged = backfill.merge_into_listing(existing, backfilled)
    accs = [d["accession_number"] for d in merged]
    assert accs.count("20150730-3041") == 1                 # not duplicated
    assert "20161223-3023" in accs                          # FA15-12 added
    assert accs == sorted(accs, key=lambda a: next(d["issued_date"] for d in merged if d["accession_number"] == a), reverse=True)


def test_overlap_defaults_to_ferc_gov_live():
    """A docket already on the live page is never re-added from Wayback — the live
    ferc.gov entry wins. (The 8 real overlaps were verified to resolve to the
    identical eLibrary accession; see data/sources/overlap_verification_*.json.)"""
    # FA17-1 is in current_dockets (i.e., listed live), so it must be excluded.
    entries = backfill.build_backfill_entries(_HTML, _ACCESSIONS, current_dockets={"FA17-1"})
    assert all(e.docket != "FA17-1" for e in entries)
    # And if a backfill accession somehow collides with a live one, merge keeps live.
    existing = [{"accession_number": "20150730-3041", "issued_date": "2015-07-30", "docket": "FA14-2"}]
    merged = backfill.merge_into_listing(existing, _entries())
    fa14_2 = [d for d in merged if d["accession_number"] == "20150730-3041"]
    assert len(fa14_2) == 1 and fa14_2[0] is existing[0]  # the original (live) dict is kept


def test_is_ferc_host():
    assert backfill._is_ferc_host("https://elibrary.ferc.gov/x")
    assert backfill._is_ferc_host("https://www.ferc.gov/x")
    assert not backfill._is_ferc_host("https://evil.example.com/x")
    assert not backfill._is_ferc_host("https://ferc.gov.evil.com/x")
