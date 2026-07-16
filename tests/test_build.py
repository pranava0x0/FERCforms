"""Tests for site-meta baking (pipeline/build.py).

Regression guard for the clean-checkout metadata drift: build must derive
industry counts from the committed structured reports, never from the gitignored
classification.json (absent in a fresh clone).
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from pipeline import build
from pipeline.models import AuditReport, Finding


def _report(
    rid: str,
    industry: str | None,
    findings: list[Finding] | None = None,
    collection: str = "ferc_audit",
) -> AuditReport:
    return AuditReport(
        id=rid,
        company="X",
        company_raw="X",
        source_page_url="https://elibrary.ferc.gov/x",
        pdf_download_url="https://elibrary.ferc.gov/dl",
        captured_at=date(2026, 2, 3),
        page_count=1,
        industry=industry,
        collection=collection,
        finding_count=sum(1 for f in (findings or []) if not f.is_other_matter),
        findings=findings or [],
    )


def test_audit_report_defaults_keep_ferc_corpus_valid():
    """New multi-source fields default to the original FERC-audit identity, so the
    120 committed report.json files validate without a rewrite."""
    r = _report("a", "electric")
    assert r.collection == "ferc_audit"
    assert r.jurisdiction == "FERC"
    assert r.source == ""
    assert r.structured is True


def test_meta_by_collection_counts_every_canonical_collection():
    reports = [_report("a", "electric"), _report("b", "gas", collection="state_audit")]
    meta = build.build_meta(reports, listing=[])
    # Every canonical collection present (even at 0) so no tab is missing.
    assert meta["by_collection"] == {
        "ferc_audit": 1,
        "prudence_review": 0,
        "state_audit": 1,
        "state_rate_case": 0,
        "state_reference": 0,
    }
    assert set(meta["by_collection"]) == set(build.COLLECTION_KEYS)


def test_collection_keys_match_frontend():
    """The site's COLLECTIONS (docs/js/app.js) must use the SAME keys as the
    pipeline, or a tab would render against a collection the build never emits."""
    app_js = (Path(__file__).resolve().parent.parent / "docs" / "js" / "app.js").read_text(encoding="utf-8")
    block = app_js.split("const COLLECTIONS = [", 1)[1].split("];", 1)[0]
    js_keys = re.findall(r'key:\s*"([a-z_]+)"', block)
    assert js_keys == build.COLLECTION_KEYS


def test_by_industry_computed_from_reports():
    reports = [_report("a", "electric"), _report("b", "electric"), _report("c", "gas"), _report("d", None)]
    meta = build.build_meta(reports, listing=[{"captured_at": "2026-02-03"}])
    assert meta["by_industry_identified"] == {"electric": 2, "gas": 1, "unknown": 1}
    assert meta["reports_structured"] == 4
    assert meta["reports_total_listed"] == 1
    assert meta["listing_captured_at"] == "2026-02-03"


def test_bake_tags_findings_with_themes_and_ratepayer_harm():
    """Every finding gets `themes` + a `cost_to_customers` flag; the report-level
    flag is the OR across findings. Lobbying = ratepayer harm; plant records is not."""
    r = _report(
        "a", "electric",
        findings=[
            Finding(index=1, title="Accounting for Lobbying Expenses", summary=""),
            Finding(index=2, title="Property Unit Listing", summary=""),
        ],
    )
    [d] = build.bake_report_dicts([r])
    lobby, plant = d["findings"]
    assert "Below-the-line costs (lobbying, charitable, etc.)" in lobby["themes"]
    assert lobby["cost_to_customers"] is True
    assert plant["cost_to_customers"] is False
    assert d["cost_to_customers"] is True       # OR across findings
    assert d["themes"]                           # report-level union present


def test_bake_no_findings_is_not_ratepayer_harm():
    [d] = build.bake_report_dicts([_report("b", "gas", findings=[])])
    assert d["cost_to_customers"] is False
    assert d["themes"] == []


def test_bake_reference_record_gets_descriptor_themes_but_no_harm_flag():
    """Reference records (structured=False) bake report-level themes from their
    displayed descriptors (doc_type + source_note) so the Prudence Reviews /
    State Rate Cases tabs can facet — but a descriptor tag must never set the
    ratepayer-harm badge (that stays finding-derived)."""
    r = _report("ref", "electric", findings=[], collection="prudence_review").model_copy(
        update={
            "structured": False,
            "doc_type": "affiliate-transactions audit & fuel adjustment clause order",
            "source_note": "Order in the FAC fuel cost review.",
        }
    )
    [d] = build.bake_report_dicts([r])
    assert "Fuel & purchased-power cost recovery" in d["themes"]
    # "affiliate" is a RATEPAYER_HARM theme — present as a descriptor tag, but the
    # harm flag must stay off without a flagged finding.
    assert "Affiliate / intercompany transactions" in d["themes"]
    assert d["cost_to_customers"] is False


def test_industry_counts_nonempty_for_nonempty_corpus():
    # The bug Codex caught: a clean build (no classification.json) must not write
    # empty industry counts. build_meta never reads that file, so a non-empty
    # corpus always yields non-empty counts.
    meta = build.build_meta([_report("a", "oil")], listing=[])
    assert meta["by_industry_identified"] == {"oil": 1}
    assert meta["listing_captured_at"] is None


def test_split_reports_round_trips():
    """The index/detail split must be LOSSLESS — merge_split is split_reports'
    exact inverse. reports.json stays the single source of truth; the runtime
    payloads are only a repackaging of it (spec B2)."""
    dicts = build.bake_report_dicts([
        _report("a", "electric", findings=[Finding(index=1, title="Lobbying", summary="s")]),
        _report("b", "gas", collection="state_audit"),
    ])
    index, details = build.split_reports(dicts)
    assert build.merge_split(index, details) == dicts


def test_split_index_carries_only_card_fields_plus_rollups():
    """The index must not smuggle finding bodies back into the first paint — that
    is the entire point of the split (F5)."""
    dicts = build.bake_report_dicts([_report("a", "electric", findings=[Finding(index=1, title="X", summary="body")])])
    index, details = build.split_reports(dicts)
    assert set(index[0]) == set(build.CARD_FIELDS) | set(build.DERIVED_INDEX_FIELDS)
    assert "findings" not in index[0]
    assert "findings" in details["ferc_audit"]["a"]


def test_split_rollups_count_recs_and_take_max_amount():
    """rec_count sums recommendations; amount_max is the LARGEST cited figure —
    never a sum, which would invent a number no report states."""
    from pipeline.models import Recommendation

    r = _report(
        "a", "electric",
        findings=[
            Finding(index=1, title="A", summary="", amount_usd=3_500_000.0,
                    recommendations=[Recommendation(number=1, text="do x"), Recommendation(number=2, text="do y")]),
            Finding(index=2, title="B", summary="", amount_usd=120_000.0,
                    recommendations=[Recommendation(number=1, text="do z")]),
        ],
    )
    [entry], _ = build.split_reports(build.bake_report_dicts([r]))
    assert entry["rec_count"] == 3
    assert entry["amount_max"] == 3_500_000.0


def test_split_rollups_absent_when_no_findings():
    [entry], _ = build.split_reports(build.bake_report_dicts([_report("b", "gas", findings=[])]))
    assert entry["rec_count"] == 0
    assert entry["amount_max"] is None


def test_committed_corpus_split_round_trips():
    """Corpus-wide parity guard: the real baked reports.json must survive the
    split/merge round-trip, so the shipped index+detail files can always be
    reconstructed into the documented full download."""
    import json

    from pipeline import config

    path = config.SITE_DATA_DIR / "reports.json"
    if not path.exists():
        import pytest

        pytest.skip("reports.json not baked in this checkout")
    dicts = json.loads(path.read_text(encoding="utf-8"))
    index, details = build.split_reports(dicts)
    assert build.merge_split(index, details) == dicts


def test_card_fields_match_frontend():
    """docs/js/app.js must declare the SAME card fields as the bake. If the site
    reads a field the index doesn't carry, collapsed cards silently render
    `undefined` (the field now lives in the lazily-fetched detail file)."""
    app_js = (Path(__file__).resolve().parent.parent / "docs" / "js" / "app.js").read_text(encoding="utf-8")
    block = app_js.split("const CARD_FIELDS = [", 1)[1].split("];", 1)[0]
    js_fields = re.findall(r'"([a-z_]+)"', block)
    assert js_fields == build.CARD_FIELDS


def test_committed_reports_carry_full_schema_and_named_source():
    """Every committed report.json must EXPLICITLY carry the provenance fields
    (collection/jurisdiction/source/structured) on disk — not lean on model
    defaults — and name a government source. Regression for the 120 FERC
    report.json that predated the multi-source fields (source was "" and the
    fields were absent on disk; only materialized by defaults at build time)."""
    import json

    from pipeline import config

    paths = sorted(config.PROCESSED_DIR.glob("*/report.json"))
    assert paths, "no processed report.json found"
    for p in paths:
        raw = json.loads(p.read_text(encoding="utf-8"))
        for field in ("collection", "jurisdiction", "source", "structured"):
            assert field in raw, f"{p.parent.name}: report.json missing {field!r} on disk"
        assert raw["source"].strip(), f"{p.parent.name}: empty source (issuer not named)"
        if raw["collection"] == "ferc_audit":
            assert "FERC" in raw["source"], f"{p.parent.name}: FERC audit source not named"
