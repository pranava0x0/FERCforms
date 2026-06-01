"""Tests for the generic source-ingestion path (pipeline/sources.py).

Covers the metadata-only structuring used for prudence / state-PUC documents:
the FERC executive-summary parser doesn't fit them, so they're captured with
their source and full provenance but NOT machine-extracted into findings
(see the module docstring + the multi-source policy).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline import config, sources
from pipeline.models import SourceSeed


def _seed(**over) -> SourceSeed:
    base = dict(
        id="2024-07-11_ppl_pa-mo-audit",
        company="PPL Electric Utilities Corporation",
        collection="state_audit",
        jurisdiction="PA",
        source="PA PUC Bureau of Audits",
        doc_type="management & operations audit",
        industry="electric",
        pdf_url="https://www.puc.pa.gov/pcdocs/1837310.pdf",
        source_page_url="https://www.puc.pa.gov/press-release/2024/x",
        issued_date=date(2024, 7, 11),
        docket="D-2023-3039488",
        captured_at=date(2026, 6, 1),
        source_note="note",
    )
    base.update(over)
    return SourceSeed(**base)


def test_structure_seed_is_metadata_only():
    """A seed becomes an AuditReport carrying its provenance, with NO findings and
    structured=False so the UI shows the honest 'Listed for reference' state."""
    r = sources.structure_seed(_seed(), page_count=65, scanned_pages=[])
    assert r.collection == "state_audit"
    assert r.jurisdiction == "PA"
    assert r.source == "PA PUC Bureau of Audits"
    assert r.doc_type == "management & operations audit"
    assert r.industry == "electric"
    assert r.page_count == 65
    assert r.structured is False
    assert r.finding_count == 0 and r.findings == []
    # Provenance preserved end-to-end.
    assert r.pdf_download_url.endswith("1837310.pdf")
    assert r.issued_date == date(2024, 7, 11)


def test_source_seed_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        _seed(bogus_field="x")


def test_source_seed_defaults():
    s = _seed(doc_type=None, industry=None, docket=None)
    assert s.parse is False           # metadata-only by default
    assert s.archived_via is None


def test_pa_seed_file_validates():
    """The committed PA seed must parse cleanly (every record a valid SourceSeed),
    so a typo can't silently drop a document from the corpus."""
    path = config.SEEDS_DIR / "pa_puc.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    seeds = [SourceSeed.model_validate(d) for d in data]
    assert len(seeds) >= 3
    assert all(s.collection == "state_audit" and s.jurisdiction == "PA" for s in seeds)
    # ids are unique (they're also the on-disk processed dir + raw filename).
    assert len({s.id for s in seeds}) == len(seeds)
