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
    "scope": "FERC utility audits — electric, gas & oil",
    "reports_total_listed": 71,
    "by_industry_identified": {"electric": 53, "oil": 10, "gas": 7},
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
        by_industry={"electric": 1},
        by_year={"2025": 1},
        by_function={"transmission": 1},
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
    assert s.startswith("# FERC Audit Explorer")  # required H1
    assert "\n> " in s                            # blockquote summary
    assert "data/reports.json" in s               # links to machine-readable data
    assert "llms-full.txt" in s
    assert "of 71 listed" in s                    # uses the real meta counts
    assert "(53 electric, 10 oil, 7 gas identified)" in s
    assert "Acme Electric Co" in s and "AFUDC Error" in s
    assert "AFUDC / cost of capital" in s          # themes listed


def test_index_renders_theme_descriptions():
    """Theme descriptions must flow into llms.txt (the site<->llms.txt integration).
    Guards that editing THEME_DESCRIPTIONS reaches the machine-readable index."""
    p = _patterns()
    p.themes[0].description = "Mis-stated AFUDC explanation."
    s = llmstxt.build_index([_report()], p, _META)
    assert "Mis-stated AFUDC explanation." in s


def test_full_has_verbatim_findings_and_recs():
    s = llmstxt.build_full([_report()], _patterns(), _META)
    assert "## Acme Electric Co" in s
    assert "Docket: FA00-0-000" in s
    assert "Audit type: financial" in s
    assert "### Finding 1: AFUDC Error" in s
    assert "Acme overstated AFUDC." in s           # verbatim summary
    assert "1. Recalculate AFUDC." in s            # numbered recommendation
    assert "(source p." not in s                   # FERC rec has no page -> no citation


def test_full_cites_rec_source_page_when_present():
    r = _report()
    r.findings[0].recommendations[0].source_page = 29
    s = llmstxt.build_full([r], _patterns(), _META)
    assert "1. Recalculate AFUDC. (source p. 29)" in s


def test_write_llms_creates_all_three_files(tmp_path):
    llmstxt.write_llms(tmp_path, [_report()], _patterns(), _META)
    assert (tmp_path / "llms.txt").read_text(encoding="utf-8").startswith("# FERC Audit Explorer")
    assert "full structured corpus" in (tmp_path / "llms-full.txt").read_text(encoding="utf-8")
    ctx = (tmp_path / "llms-ctx.txt").read_text(encoding="utf-8")
    assert ctx.startswith('<project title="FERC Audit Explorer"')


def test_ctx_is_xml_shaped_with_verbatim_docs():
    s = llmstxt.build_ctx([_report(), _metadata_only_state_report()], _patterns(), _META)
    # spec shape: a <project> root wrapping <doc> elements inside <docs>
    assert s.startswith('<project title="FERC Audit Explorer" summary="') and s.rstrip().endswith("</project>")
    assert "<docs>" in s and "</docs>" in s
    assert '<doc title="Acme Electric Co"' in s and 'collection="FERC Audits"' in s
    assert "Finding 1: AFUDC Error" in s and "Acme overstated AFUDC." in s  # verbatim content inlined
    assert "1. Recalculate AFUDC." in s
    # metadata-only record carries its source note, not findings
    assert '<doc title="El Paso Electric Company"' in s
    assert "Listed for reference" in s and "Direct Testimony of X on behalf of OPUC" in s
    # llms-ctx.txt omits the Optional section (no inlined external links by default)
    assert "<optional>" not in s


def test_ctx_escapes_xml_special_chars_and_includes_optional_when_asked():
    r = _report()
    r.company = "Baltimore Gas & Electric <Co>"
    s = llmstxt.build_ctx([r], _patterns(), _META, include_optional=True)
    assert 'title="Baltimore Gas &amp; Electric &lt;Co&gt;"' in s  # attribute escaped, not raw
    assert "<optional>" in s and 'source="index.html"' in s


def _metadata_only_state_report() -> AuditReport:
    return AuditReport(
        collection="state_audit",
        jurisdiction="TX",
        source="Public Utility Commission of Texas",
        doc_type="direct testimony",
        id="s1",
        company="El Paso Electric Company",
        company_raw="El Paso Electric Company",
        docket="57149",
        issued_date=date(2025, 3, 25),
        source_page_url="https://interchange.puc.texas.gov/x",
        pdf_download_url="https://interchange.puc.texas.gov/x.pdf",
        captured_at=date(2026, 6, 1),
        source_note="Direct Testimony of X on behalf of OPUC in the fuel-cost reconciliation.",
        page_count=52,
        industry="electric",
        finding_count=0,
        findings=[],
        structured=False,
    )


def test_index_groups_collections_and_lists_metadata_only_honestly():
    s = llmstxt.build_index([_report(), _metadata_only_state_report()], _patterns(), _META)
    assert "## FERC Audits" in s and "## State PUC Audits" in s     # per-collection sections
    # metadata-only doc: NOT framed as a 0-finding audit — listed with its doc type + jurisdiction
    assert "TX · direct testimony" in s
    assert "listed for reference" in s
    # grounded insight line surfaces jurisdiction counts (mechanical, no editorializing)
    assert "jurisdictions: TX (1)" in s


def test_full_gives_metadata_only_docs_their_source_note():
    s = llmstxt.build_full([_metadata_only_state_report()], _patterns(), _META)
    assert "## El Paso Electric Company" in s
    assert "Collection: State PUC Audits" in s
    assert "listed for reference (not machine-parsed into findings)" in s
    assert "Direct Testimony of X on behalf of OPUC" in s          # verbatim source note carried through
