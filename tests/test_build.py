"""Tests for site-meta baking (pipeline/build.py).

Regression guard for the clean-checkout metadata drift: build must derive
industry counts from the committed structured reports, never from the gitignored
classification.json (absent in a fresh clone).
"""
from __future__ import annotations

from datetime import date

from pipeline import build
from pipeline.models import AuditReport, Finding


def _report(rid: str, industry: str | None, findings: list[Finding] | None = None) -> AuditReport:
    return AuditReport(
        id=rid,
        company="X",
        company_raw="X",
        source_page_url="https://elibrary.ferc.gov/x",
        pdf_download_url="https://elibrary.ferc.gov/dl",
        captured_at=date(2026, 2, 3),
        page_count=1,
        industry=industry,
        finding_count=sum(1 for f in (findings or []) if not f.is_other_matter),
        findings=findings or [],
    )


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


def test_industry_counts_nonempty_for_nonempty_corpus():
    # The bug Codex caught: a clean build (no classification.json) must not write
    # empty industry counts. build_meta never reads that file, so a non-empty
    # corpus always yields non-empty counts.
    meta = build.build_meta([_report("a", "oil")], listing=[])
    assert meta["by_industry_identified"] == {"oil": 1}
    assert meta["listing_captured_at"] is None
