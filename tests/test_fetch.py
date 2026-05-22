"""Tests for the eLibrary fetcher (pipeline/fetch.py) — no network.

Network behavior is exercised by the live `fetch` CLI; here we cover the pure
logic: URL construction, caching, and the listing round-trip, using fakes.
"""
from __future__ import annotations

import json
from datetime import date

from pipeline import config, fetch
from pipeline.models import ListingEntry


def _entry(acc: str = "20250929-3000") -> ListingEntry:
    return ListingEntry(
        id="x",
        company="X Co",
        company_raw="X Co (PA00-0)",
        docket="PA00-0",
        accession_number=acc,
        issued_date=date(2025, 9, 29),
        source_page_url=f"https://elibrary.ferc.gov/eLibrary/filelist?accession_number={acc}",
        pdf_download_url=f"https://elibrary.ferc.gov/eLibraryWebAPI/api/File/DownloadPDF?accesssionNumber={acc}",
        captured_at=date(2026, 2, 3),
    )


class _FakeResp:
    def __init__(self, content=b"%PDF-" + b"1" * 5000, status=200, ctype="application/pdf"):
        self.content = content
        self.status_code = status
        self.headers = {"content-type": ctype}

    def raise_for_status(self):
        pass


class _FakeSession:
    def __init__(self):
        self.cookies = {}
        self.calls = {"get": 0, "post": 0}

    def get(self, *a, **k):
        self.calls["get"] += 1
        self.cookies = {"TS": "seeded"}
        return _FakeResp()

    def post(self, *a, **k):
        self.calls["post"] += 1
        return _FakeResp()


def test_filelist_url():
    url = fetch._filelist_url("20250929-3000")
    assert url.startswith("https://elibrary.ferc.gov/eLibrary/filelist")
    assert "accession_number=20250929-3000" in url


def test_download_uses_cache(tmp_path):
    entry = _entry()
    dest = tmp_path / f"{entry.accession_number}.pdf"
    dest.write_bytes(b"%PDF-" + b"0" * 2000)  # valid-sized cache
    # session=None would raise if the network were touched — cache must short-circuit.
    assert fetch.download_pdf(None, entry, tmp_path) == dest


def test_tiny_cache_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REQUEST_DELAY_SECONDS", 0)
    entry = _entry()
    dest = tmp_path / f"{entry.accession_number}.pdf"
    dest.write_bytes(b"%PDF-")  # truncated (< 1 KB) — not a usable cache
    session = _FakeSession()
    out = fetch.download_pdf(session, entry, tmp_path)
    assert out.read_bytes().startswith(b"%PDF-")
    assert out.stat().st_size > 1024
    assert session.calls["post"] == 1


def test_retry_then_succeed(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REQUEST_DELAY_SECONDS", 0)
    monkeypatch.setattr(config, "BACKOFF_BASE_SECONDS", 0)
    entry = _entry()

    class FlakySession(_FakeSession):
        def post(self, *a, **k):
            self.calls["post"] += 1
            if self.calls["post"] == 1:
                return _FakeResp(content=b"<html>rejected", ctype="text/html")
            return _FakeResp()

    session = FlakySession()
    out = fetch.download_pdf(session, entry, tmp_path)
    assert out.exists()
    assert session.calls["post"] == 2  # first rejected, second ok


def test_load_listing_roundtrip(tmp_path):
    entry = _entry()
    path = tmp_path / "listing.json"
    path.write_text(json.dumps([json.loads(entry.model_dump_json())]))
    out = fetch.load_listing(path)
    assert len(out) == 1
    assert out[0].accession_number == entry.accession_number
