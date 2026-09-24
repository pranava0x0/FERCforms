"""Reviewed refresh records must retain their evidence and document roles."""
import json
from pathlib import Path
from collections import Counter

from pipeline.sources import load_seed

ROOT = Path(__file__).resolve().parents[1]


def test_seven_state_refresh_has_reviewed_evidence_and_no_fabricated_findings():
    seeds = [s for p in (ROOT/'data/seeds').glob('*_expansion_20260924.json') for s in load_seed(p)]
    assert Counter(s.jurisdiction for s in seeds) == {'VA':1, 'TX':2, 'PA':3, 'NY':1, 'OH':1, 'GA':3, 'OR':3}
    candidates = {}
    for pattern in ('eastern-*.json', '*-expansion-20260924.json', 'or-*-20260924.json'):
        for path in (ROOT/'data/sources').glob(pattern):
            for record in json.loads(path.read_text())['candidates']:
                candidates[record['url']] = record
    for seed in seeds:
        record = candidates[seed.pdf_url]
        assert record['reviewed_metadata'] == seed.model_dump(mode='json')
        assert len(record['pdf_sha256']) == 64
        assert len(record['caption_pages']) == 3
        report = json.loads((ROOT/'data/processed'/seed.id/'report.json').read_text())
        assert report['page_count'] == record['page_count'] > 0
        assert report['findings'] == []
        assert report['structured'] is False
        assert report['collection'] == seed.collection
    audit = next(s for s in seeds if 'management-efficiency-investigation' in s.id)
    assert audit.collection == 'state_audit' and audit.issued_date is None
    assert next(s for s in seeds if 'ohio-puco' in s.id).collection == 'state_reference'
    ppl = next(s for s in seeds if 'ppl-electric' in s.id)
    assert str(ppl.issued_date) == '2026-04-17'
    assert 'recommended' in ppl.doc_type
