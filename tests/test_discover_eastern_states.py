"""Eastern discovery keeps observed government links and rejects redirects away."""
from pathlib import Path
import sys

import pytest

from pipeline import discover_eastern_states as eastern
from pipeline import discover_ca


def test_tx_filing_rows_and_ny_guids_are_observed() -> None:
    tx = '''<table><tr><td><a href="/search/documents/?controlNumber=56211&amp;itemNumber=518">518</a></td><td>ORDER</td></tr></table>'''
    rows = eastern.html_links('TX', tx, 'https://interchange.puc.texas.gov/search/filings/?ControlNumber=56211')
    assert len(rows) == 1
    assert rows[0]['label'] == '518 ORDER'
    ny = '<a href="/search/Home/ViewDoc/Find?id=%7B2087A998-0000-C22F-BBDD-FA9090F43FAC%7D&amp;ext=.pdf">Rate order</a>'
    rows = eastern.html_links('NY', ny, 'https://documents.dps.ny.gov/search/Home/DocumentSearch2/')
    assert len(rows) == 1
    assert rows[0]['url'].startswith('https://documents.dps.ny.gov/public/Common/ViewDoc.aspx?DocRefId=')
    assert eastern.html_links('NY', '<a href="https://example.com/x.pdf">Bad</a>', 'https://documents.dps.ny.gov/') == []


def test_official_state_hosts_only() -> None:
    eastern.check_url('PA', 'https://www.puc.pa.gov/pcdocs/1814749.pdf')
    for url in ('http://www.puc.pa.gov/pcdocs/1814749.pdf',
                'https://fakepuc.pa.gov/pcdocs/1814749.pdf',
                'https://www.puc.pa.gov.example.com/pcdocs/1814749.pdf'):
        with pytest.raises(ValueError):
            eastern.check_url('PA', url)


def test_unsafe_redirect_never_requested(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        is_redirect = True
        headers = {'Location': 'https://example.com/not-a-pdf'}
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def raise_for_status(self): return None
    class Session:
        urls = []
        def get(self, url, **kwargs):
            self.urls.append(url)
            return Response()
    monkeypatch.setattr(discover_ca.time, 'sleep', lambda _: None)
    session = Session()
    with pytest.raises(ValueError, match='Not an official'):
        eastern.fetch(session, 'PA', 'https://www.puc.pa.gov/pcdocs/a.pdf', tmp_path / 'a.pdf')
    assert session.urls == ['https://www.puc.pa.gov/pcdocs/a.pdf']
    assert not (tmp_path / 'a.pdf').exists()


def test_tampered_pdf_cache_redownloads_but_clean_cache_preserves_date(tmp_path: Path,
                                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / 'candidate.pdf'
    path.write_bytes(b'%PDF-original')
    prior = {'pdf_sha256': eastern.digest(path), 'resolved_url': 'https://www.puc.pa.gov/pcdocs/a.pdf',
             'downloaded_at': '2026-09-24T00:00:00+00:00'}
    eastern.save(path.with_suffix('.json'), prior)
    calls = []
    def fake_fetch(session, state, url, target, cap=eastern.MAX_BYTES):
        calls.append(url)
        target.write_bytes(b'%PDF-replacement')
        return url
    monkeypatch.setattr(eastern, 'fetch', fake_fetch)
    url = prior['resolved_url']
    assert eastern.cached_pdf(None, 'PA', url, path) == prior
    assert calls == []
    path.write_bytes(b'%PDF-tampered')
    changed = eastern.cached_pdf(None, 'PA', url, path)
    assert calls == [url]
    assert changed['pdf_sha256'] == eastern.digest(path)
    assert changed['downloaded_at'] != prior['downloaded_at']


def test_cli_exits_nonzero_on_candidate_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'argv', ['discover_eastern_states', 'PA', '--document-url',
                                     'https://www.puc.pa.gov/pcdocs/a.pdf', '--output', str(tmp_path / 'receipt.json')])
    monkeypatch.setattr(eastern, 'discover', lambda *args, **kwargs: {
        'candidates': [], 'already_held': 0, 'failures': [{'error': 'HTTP 403'}]})
    with pytest.raises(SystemExit) as exc:
        eastern.main()
    assert exc.value.code == 1


def test_ny_download_button_keeps_document_title():
    html = '<a href="/search/Home/DownloadDoc/Find?id=%7B2087A998-0000-C22F-BBDD-FA9090F43FAC%7D&amp;ext=.pdf&amp;docTitle=Order%20Adopting%20Terms">Download</a>'
    rows = eastern.html_links('NY', html, 'https://documents.dps.ny.gov/search/Home/DocumentSearch2/')
    assert rows[0]['label'] == 'Order Adopting Terms'
