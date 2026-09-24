"""State discovery must preserve source identity and require reviewed bytes."""
import json
from pathlib import Path

import fitz
import pytest

from pipeline import discover_state_portals as portals
from pipeline.sources import SourceSeed


def test_state_selectors_exclude_docx_and_collapse_repeated_oregon_links():
    ga = '''<a href="https://services.psc.ga.gov/api/v1/External/Public/Get/Document/DownloadFile/1/2">Order.docx</a>
    <a href="https://services.psc.ga.gov/api/v1/External/Public/Get/Document/DownloadFile/1/3">1.pdf</a>'''
    assert len(portals.document_links(ga, 'https://psc.ga.gov/', 'GA')) == 1
    ore = '<a href="orders.asp?OrderNumber=24-447">24-447</a><a href="orders.asp?OrderNumber=24-447"></a>'
    assert len(portals.document_links(ore, 'https://apps.puc.state.or.us/edockets/docket.asp', 'OR')) == 1
    with pytest.raises(ValueError, match='Unexpected'):
        portals.document_links('<a href="https://evil.gov/auditsearch/Reports/x.pdf">Audit</a>', 'https://ohioauditor.gov/', 'OH')


def test_redirect_cannot_escape_state(tmp_path, monkeypatch):
    from tests.test_discover_ca import Session, Response
    from pipeline import discover_ca
    monkeypatch.setattr(discover_ca.time, 'sleep', lambda _: None)
    session = Session(Response({'Location': 'https://example.gov/a.pdf'}, [], True))
    with pytest.raises(ValueError, match='Unexpected'):
        portals.download(session, 'https://psc.ga.gov/a.pdf', tmp_path/'a.pdf', 100, lambda u: portals.validate('GA', u))
    assert session.urls == ['https://psc.ga.gov/a.pdf']


def test_reviewed_ingestion_is_idempotent_and_refuses_mutation(tmp_path, monkeypatch):
    data = tmp_path/'data'
    raw = data/'raw'
    processed = data/'processed'
    raw.mkdir(parents=True)
    for key, value in [('DATA_DIR', data), ('RAW_DIR', raw), ('PROCESSED_DIR', processed)]:
        monkeypatch.setattr(portals.config, key, value)
    pdf = raw/'source.pdf'
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((72,72), 'Utility review source caption for fixture ' * 3)
        doc.save(pdf)
    seed = SourceSeed(id='or-case', company='PacifiCorp', collection='state_rate_case', jurisdiction='OR',
                      source='Oregon PUC', doc_type='Order', pdf_url='https://apps.puc.state.or.us/orders/test.pdf',
                      source_page_url='https://apps.puc.state.or.us/edockets/test', captured_at='2026-09-24',
                      source_note='Caption reviewed.', parse=False, fetch=True).model_dump(mode='json')
    record = {'url':seed['pdf_url'], 'source_page_url':seed['source_page_url'], 'cache_path':'data/raw/source.pdf',
              'pdf_sha256':portals.digest(pdf), 'page_count':1, 'reviewed_metadata':seed.copy()}
    seeds, receipt = tmp_path/'seed.json', tmp_path/'receipt.json'
    portals.write_json(seeds,[seed]); portals.write_json(receipt,{'jurisdiction':'OR','candidates':[record]})
    portals.ingest(seeds,receipt)
    report = processed/'or-case'/'report.json'
    before = report.read_bytes()
    portals.ingest(seeds,receipt)
    assert report.read_bytes() == before
    seed['company']='Wrong utility'
    portals.write_json(seeds,[seed])
    with pytest.raises(ValueError, match='reviewed metadata'):
        portals.ingest(seeds,receipt)
    assert report.read_bytes() == before
    portals.write_json(seeds,[record['reviewed_metadata']])
    pdf.write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash differs'):
        portals.ingest(seeds,receipt)
