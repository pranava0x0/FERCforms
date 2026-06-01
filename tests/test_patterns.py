"""Tests for cross-report pattern mining (pipeline/patterns.py)."""
from __future__ import annotations

from datetime import date

from pipeline import patterns
from pipeline.models import AuditReport, Finding, Recommendation


def _report(
    rid: str, industry: str, year: int, findings: list[Finding], functions=()
) -> AuditReport:
    return AuditReport(
        id=rid,
        company="Co",
        company_raw="Co",
        issued_date=date(year, 1, 1),
        source_page_url="u",
        pdf_download_url="u",
        captured_at=date(2026, 1, 1),
        page_count=1,
        industry=industry,
        functions=list(functions),
        finding_count=sum(1 for f in findings if not f.is_other_matter),
        findings=findings,
    )


def test_themes_for_matches_and_misses():
    assert "Depreciation" in patterns._themes_for("Depreciation Rates and Study")
    assert "AFUDC / cost of capital" in patterns._themes_for(
        "Allowance for Funds Used During Construction"
    )
    assert "Accounting misclassification" in patterns._themes_for(
        "Crude Oil Accounting Misclassifications — improperly recorded amounts"
    )
    assert patterns._themes_for("a wholly unrelated phrase") == []


def test_summarize_counts_and_themes():
    r1 = _report(
        "a", "electric", 2025,
        [Finding(index=1, title="Depreciation Rates", summary="x",
                 recommendations=[Recommendation(number=1, text="r")])],
        functions=["transmission", "distribution"],
    )
    r2 = _report(
        "b", "electric", 2024,
        [
            Finding(index=1, title="Depreciation Study", summary="y"),
            Finding(index=2, title="Creditworthiness Standards", summary="z", is_other_matter=True),
        ],
        functions=["transmission"],
    )
    s = patterns.summarize([r1, r2])
    assert s.report_count == 2
    assert s.finding_count == 2          # other-matter excluded
    assert s.other_matter_count == 1
    assert s.recommendation_count == 1
    assert s.by_industry == {"electric": 2}
    assert s.by_year == {"2024": 1, "2025": 1}
    assert s.by_function == {"transmission": 2, "distribution": 1}

    dep = next(t for t in s.themes if t.theme == "Depreciation")
    assert dep.report_count == 2 and dep.finding_count == 2
    assert dep.keywords  # keywords are surfaced for transparency
    assert dep.description  # plain-English explanation is attached


def test_ratepayer_harm_themes_are_declared_themes():
    """The ratepayer-harm axis must be a subset of THEME_RULES labels (single
    source). Guards against a typo'd or stale entry silently never matching."""
    labels = {theme for theme, _ in patterns.THEME_RULES}
    assert patterns.RATEPAYER_HARM_THEMES
    assert patterns.RATEPAYER_HARM_THEMES <= labels


def test_is_ratepayer_harm():
    assert patterns.is_ratepayer_harm(["Depreciation"]) is True
    assert patterns.is_ratepayer_harm(["Property & plant records"]) is False
    assert patterns.is_ratepayer_harm([]) is False


def test_every_theme_has_a_description():
    """Each theme rule must carry a plain-English description (shown on the site
    and in llms.txt). Guards against adding a THEME_RULES entry without one."""
    for theme, _kws in patterns.THEME_RULES:
        assert patterns.THEME_DESCRIPTIONS.get(theme), f"missing description for theme: {theme}"


def test_summarize_empty():
    s = patterns.summarize([])
    assert s.report_count == 0 and s.themes == [] and s.finding_count == 0
