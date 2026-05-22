"""Tests for llms.txt / llms-full.txt generation (pipeline/llmstxt.py)."""
from __future__ import annotations

from datetime import date

from pipeline import llmstxt
from pipeline.models import (
    AuditReport,
    Finding,
    PatternsSummary,
    Recommendation,
    ThemeStat,
)

_META = {
    "generated_at": "2026-05-22",
    "scope": "FERC Form 1 (electric) audits",
    "reports_total_listed": 71,
    "electric_identified": 39,
    "reports_structured": 1,
}


def _report() -> AuditReport:
    return AuditReport(
        id="r1",
        company="Acme Electric Co",
        company_raw="Acme Electric Co (FA00-0)",
        docket="FA00-0",
        docket_full="FA00-0-000",
        issued_date=date(2025, 1, 2),
        source_page_url="https://elibrary.ferc.gov/x",
        pdf_download_url="https://elibrary.ferc.gov/dl",
        captured_at=date(2026, 2, 3),
        page_count=10,
        industry="electric",
        audit_type="financial",
        forms=["1"],
        finding_count=1,
        findings=[
            Finding(
                index=1,
                title="AFUDC Error",
                summary="Acme overstated AFUDC.",
                recommendations=[Recommendation(number=1, text="Recalculate AFUDC.")],
            )
        ],
    )


def _patterns() -> PatternsSummary:
    return PatternsSummary(
        report_count=1,
        finding_count=1,
        other_matter_count=0,
        recommendation_count=1,
        by_industry={"gas": 1},
        by_year={"2025": 1},
        themes=[
            ThemeStat(
                theme="AFUDC / cost of capital",
                keywords=["afudc"],
                finding_count=1,
                report_count=1,
                example_titles=["AFUDC Error"],
            )
        ],
        top_titles=[{"title": "AFUDC Error", "count": 1}],
        generated_at=date(2026, 5, 22),
    )


def test_index_is_spec_shaped():
    s = llmstxt.build_index([_report()], _patterns(), _META)
    assert s.startswith("# FERC Form 1 Audit Explorer")  # required H1
    assert "\n> " in s                            # blockquote summary
    assert "data/reports.json" in s               # links to machine-readable data
    assert "llms-full.txt" in s
    assert "39 electric audits identified of 71" in s   # uses the real meta counts
    assert "Acme Electric Co" in s and "AFUDC Error" in s
    assert "AFUDC / cost of capital" in s          # themes listed


def test_full_has_verbatim_findings_and_recs():
    s = llmstxt.build_full([_report()], _patterns(), _META)
    assert "## Acme Electric Co" in s
    assert "Docket: FA00-0-000" in s
    assert "Audit type: financial" in s
    assert "### Finding 1: AFUDC Error" in s
    assert "Acme overstated AFUDC." in s           # verbatim summary
    assert "1. Recalculate AFUDC." in s            # numbered recommendation


def test_write_llms_creates_both_files(tmp_path):
    llmstxt.write_llms(tmp_path, [_report()], _patterns(), _META)
    assert (tmp_path / "llms.txt").read_text(encoding="utf-8").startswith("# FERC Form 1 Audit Explorer")
    assert "full structured corpus" in (tmp_path / "llms-full.txt").read_text(encoding="utf-8")
