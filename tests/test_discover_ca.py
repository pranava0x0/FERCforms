"""Discovery must not promote unrelated links, changed bytes or stale reports."""
from pathlib import Path
import json

import fitz
import pytest

from pipeline import discover_ca as ca


def test_audit_links_scope_year_and_deduplication() -> None:
    html = '''<a href="/-/reports/energy/2026/new.pdf">Energy</a>
    <a href="/-/reports/energy/2026/NEW.PDF#page=1">Duplicate</a>
    <a href="/-/reports/water/2026/new.pdf">Water</a>
    <a href="/-/reports/energy/2025/old.pdf">Old</a>
    <a href="https://example.com/new.pdf">Not a source</a>'''
    rows = ca.links(html, ca.AUDITS, 'audit', 2026)
    assert len(rows) == 1
    assert '/energy/2026/' in rows[0]['url']


def test_reference_and_rate_case_links_exclude_unrelated_documents() -> None:
    html = '''<a href="/reports/2026-q2">2026 Q2 Electric Rates Report</a>
    <a href="/reports/other">Broadband pricing</a>
    <a href="/decision.pdf">Track 4 Decision - D.23-11-096</a>
    <a href="/appendix.pdf">Appendix B</a>
    <a href="/fact.pdf">Fact sheet</a>'''
    assert len(ca.links(html, ca.REFERENCES, 'reference')) == 1
    assert [r['label'] for r in ca.links(html, ca.RATE_CASES, 'rate-case')] == ['Track 4 Decision - D.23-11-096']


class Response:
    def __init__(self, headers: dict, chunks: list[bytes], redirect: bool = False) -> None:
        self.headers, self.chunks, self.is_redirect = headers, chunks, redirect

    def __enter__(self) -> 'Response':
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def raise_for_status(self) -> None:
        pass

    def iter_content(self, size: int) -> list[bytes]:
        return self.chunks


class Session:
    def __init__(self, response: Response) -> None:
        self.response, self.urls = response, []

    def get(self, url: str, **kwargs: object) -> Response:
        self.urls.append(url)
        return self.response


def test_redirect_outside_cpuc_is_not_requested(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ca.time, 'sleep', lambda _: None)
    session = Session(Response({'Location': 'https://example.com/wrong.pdf'}, [], True))
    with pytest.raises(ValueError, match='Not a CPUC'):
        ca.download(session, 'https://docs.cpuc.ca.gov/a.pdf', tmp_path / 'a.pdf', 100)
    assert session.urls == ['https://docs.cpuc.ca.gov/a.pdf']


def test_oversize_stream_does_not_replace_existing_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ca.time, 'sleep', lambda _: None)
    dest = tmp_path / 'a.pdf'
    dest.write_bytes(b'original')
    session = Session(Response({}, [b'12345', b'67890']))
    with pytest.raises(ValueError, match='byte/time'):
        ca.download(session, 'https://docs.cpuc.ca.gov/a.pdf', dest, 8)
    assert dest.read_bytes() == b'original'
    assert not dest.with_suffix('.pdf.part').exists()


def test_ingest_preserves_existing_report_and_checks_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw, processed = tmp_path / 'raw', tmp_path / 'processed'
    monkeypatch.setattr(ca.config, 'RAW_DIR', raw)
    monkeypatch.setattr(ca.config, 'PROCESSED_DIR', processed)
    url = 'https://www.cpuc.ca.gov/review.pdf'
    key = ca.hashlib.sha256(ca.canonical(url).encode()).hexdigest()
    cache = raw / 'ca_discovery' / f'{key}.pdf'
    cache.parent.mkdir(parents=True)
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), 'Reviewed utility audit source caption ' * 3)
        pdf.save(cache)
    seed = {'id': 'ca-test', 'company': 'Example Utility', 'collection': 'state_audit',
            'jurisdiction': 'CA', 'source': 'CPUC', 'doc_type': 'audit', 'pdf_url': url,
            'source_page_url': ca.AUDITS, 'captured_at': '2026-09-24', 'source_note': 'Verified caption.',
            'parse': False, 'fetch': True}
    seeds, receipt = tmp_path / 'seed.json', tmp_path / 'receipt.json'
    ca.write_json(seeds, [seed])
    data = {'kind': 'audit', 'candidates': [{'url': url, 'source_page_url': ca.AUDITS,
            'pdf_sha256': ca.digest(cache), 'page_count': 1}]}
    ca.write_json(receipt, data)
    ca.ingest(seeds, receipt)
    report = processed / 'ca-test' / 'report.json'
    before = report.read_bytes()
    ca.ingest(seeds, receipt)
    assert report.read_bytes() == before
    seed['company'] = 'Different Utility'
    ca.write_json(seeds, [seed])
    with pytest.raises(ValueError, match='Refusing to overwrite'):
        ca.ingest(seeds, receipt)
    assert report.read_bytes() == before
    cache.write_bytes(b'changed source')
    with pytest.raises(ValueError, match='differs from reviewed receipt'):
        ca.ingest(seeds, receipt)
