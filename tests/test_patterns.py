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


def test_finding_theme_text_scans_recommendations():
    """State M&O audit findings have generic functional-area titles (e.g. 'Gas
    Operations') with the real pattern in the recommendation text. finding_theme_text
    must include the recs so those patterns surface — regression for the 'only 1
    theme on the State PUC Audits tab' fix (2026-06-08)."""
    f = Finding(
        index=1,
        title="Gas Operations",  # generic title — matches no theme on its own
        summary=None,
        recommendations=[
            Recommendation(number=1, text="Decrease the inventory of outstanding Class A leaks and reduce corrosion."),
            Recommendation(number=2, text="Establish physical security standards at company facilities."),
        ],
    )
    assert patterns._themes_for("Gas Operations") == []  # title alone -> nothing
    themes = patterns._themes_for(patterns.finding_theme_text(f, include_recs=True))
    assert "Gas safety & pipeline integrity" in themes   # from "Class A leak"/"corros"
    assert "Cybersecurity & physical security" in themes  # from "physical security"
    # an "inventory of … leaks" is a leak backlog, NOT materials inventory —
    # regression for the 2026-06-10 keyword calibration (bare "inventory" removed)
    assert "Inventory, materials & fleet" not in themes
    # FERC mode (include_recs=False): rec text is NOT scanned, so a generic title
    # yields no theme — this is what keeps FERC findings from picking up incidental
    # rec words (e.g. 'train staff') as workforce/operations patterns.
    assert patterns._themes_for(patterns.finding_theme_text(f, include_recs=False)) == []


def test_theme_rules_reject_known_false_positive_contexts():
    """Regression for the 2026-06-10 keyword calibration (validated against every
    keyword hit in the 294-report corpus). Each pair: a context that previously
    mis-tagged the theme must stay untagged; a real finding phrase must still match."""
    # FERC wholesale formula-rate billing / tax-receivable account names are NOT
    # retail customer service ("billing" matched ~50 wholesale findings).
    assert "Customer service & billing" not in patterns._themes_for(
        "several errors led to overbillings to wholesale transmission customers")
    assert "Customer service & billing" not in patterns._themes_for(
        "recorded income tax receivables in account 143, other accounts receivable")
    assert "Customer service & billing" in patterns._themes_for(
        "analyze and improve the billing process to reduce billing lag")
    # Financial collateral postings are NOT OASIS/informational postings.
    assert "Informational postings" not in patterns._themes_for(
        "long-term debt related to energy procurement margin and collateral postings")
    assert "Informational postings" in patterns._themes_for(
        "Posting of Transmission Service Metrics")
    # "Reliability of information" and the account name "561.5, reliability planning"
    # are NOT service reliability; generation-outage reporting to PJM isn't either.
    assert "Service reliability & vegetation management" not in patterns._themes_for(
        "deficient reporting affected the reliability of information in the Form No. 1"
    ) and "Service reliability & vegetation management" not in patterns._themes_for(
        "account 561.5, reliability planning and standards development")
    assert "Service reliability & vegetation management" in patterns._themes_for(
        "improve electric reliability performance by addressing the top outage causes")
    # The FERC account name "419, interest and dividend income" is NOT dividend policy.
    assert "Dividend policy & capital management" not in patterns._themes_for(
        "recorded equity AFUDC in account 419, interest and dividend income")
    assert "Dividend policy & capital management" in patterns._themes_for(
        "revise the dividend policy to provide advance notice to the commission")
    # A utility's own (company/BPU) annual report citation is NOT FERC form reporting.
    assert "Form reporting (Form No. 1/2/6, Page 700)" not in patterns._themes_for(
        "response to OC-0255: 2020 PSEG BPU annual report, page 4")
    assert "Form reporting (Form No. 1/2/6, Page 700)" in patterns._themes_for(
        "misreported amounts in its FERC Form No. 1")


def test_rate_case_prudence_theme_rules():
    """The 2026-06-10 fuel/storm themes: rate-case & prudence vocabulary must tag,
    and the known near-miss contexts must not."""
    fuel = "Fuel & purchased-power cost recovery"
    storm = "Storm cost recovery & securitization"
    assert fuel in patterns._themes_for("examination of the fuel adjustment clause of Kentucky Utilities")
    assert fuel in patterns._themes_for("Classification of Purchased Power Costs")
    assert fuel in patterns._themes_for("energy balancing account audit for Rocky Mountain Power")
    assert fuel in patterns._themes_for("ERRA compliance review of utility-owned generation operations")
    # "erra" must never match bare — "Sierra" contains the substring
    assert fuel not in patterns._themes_for("Sierra Pacific Resources settlement terms")
    assert storm in patterns._themes_for("storm protection plan cost recovery clause")
    assert storm in patterns._themes_for("normalize storm damage expenses and securitization charges")
    # an incidental weather mention is NOT a storm-cost matter
    assert storm not in patterns._themes_for("winter storm uri was a severe winter and ice storm")


def test_descriptor_themes_reference_records_only():
    """Reference records (structured=False) are theme-tagged from doc_type +
    source_note; machine-parsed reports are not (a FERC audit with 0 parsed
    findings must stay untagged). summarize() counts descriptor tags toward a
    theme's report_count but never its finding_count."""
    base = dict(
        id="ref", company="Co", company_raw="Co", issued_date=date(2025, 1, 1),
        source_page_url="u", pdf_download_url="u", captured_at=date(2026, 1, 1),
        page_count=0, industry="electric", finding_count=0, findings=[],
        doc_type="fuel adjustment clause order",
        source_note="Final order in the FAC examination.",
    )
    ref = AuditReport(**base, collection="state_rate_case", structured=False)
    parsed = AuditReport(**{**base, "id": "ferc"}, collection="ferc_audit", structured=True)
    fuel = "Fuel & purchased-power cost recovery"
    assert patterns.descriptor_themes(ref) == [fuel]
    assert patterns.descriptor_themes(parsed) == []

    s = patterns.summarize([ref, parsed])
    stat = next(t for t in s.themes if t.theme == fuel)
    assert stat.report_count == 1 and stat.finding_count == 0


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


# ---------- A5 theme drill-down aggregates ----------
def _co_report(rid: str, company: str, year: int, titles: list[str]) -> AuditReport:
    r = _report(rid, "electric", year, [Finding(index=i + 1, title=t, summary="") for i, t in enumerate(titles)])
    return r.model_copy(update={"company": company, "company_raw": company})


def test_theme_by_year_counts_reports_once_not_findings():
    """The sparkline is reports-per-year. A report restating one theme across
    several findings must count ONCE, or the panel overstates prevalence — the
    exact "systemic vs one-off" question A5 exists to answer."""
    s = patterns.summarize([
        _co_report("a", "Alpha Co", 2024, ["Depreciation Rates", "Depreciation Study", "Depreciation Expense"]),
        _co_report("b", "Beta Co", 2024, ["Depreciation Rates"]),
        _co_report("c", "Gamma Co", 2023, ["Depreciation Rates"]),
    ])
    dep = next(t for t in s.themes if t.theme == "Depreciation")
    assert dep.by_year == {"2023": 1, "2024": 2}   # NOT {"2024": 4} — reports, not findings
    assert dep.finding_count == 5                   # findings ARE still counted per finding (3+1+1)
    assert dep.report_count == 3


def test_theme_by_year_sums_to_report_count():
    """Internal consistency: the sparkline must reconcile with the headline count
    the panel prints beside it (every report here carries an issued_date)."""
    s = patterns.summarize([
        _co_report("a", "Alpha Co", 2024, ["Depreciation Rates"]),
        _co_report("b", "Beta Co", 2023, ["Depreciation Study", "Lobbying Expenses"]),
        _co_report("c", "Gamma Co", 2022, ["Depreciation Rates"]),
    ])
    for t in s.themes:
        assert sum(t.by_year.values()) == t.report_count, f"{t.theme}: by_year != report_count"


def test_theme_top_companies_ranked_and_capped():
    s = patterns.summarize(
        [_co_report(f"a{i}", "Repeat Co", 2020 + i, ["Depreciation Rates"]) for i in range(3)]
        + [_co_report(f"b{i}", f"One-Off {i} Co", 2024, ["Depreciation Rates"]) for i in range(6)]
    )
    dep = next(t for t in s.themes if t.theme == "Depreciation")
    assert dep.top_companies[0] == {"company": "Repeat Co", "report_count": 3}
    assert len(dep.top_companies) == 5  # top 5 only
    assert sum(c["report_count"] for c in dep.top_companies) <= dep.report_count


def test_theme_by_year_skips_reports_without_an_issued_date():
    """A null issued_date must not become a phantom year bucket (or a crash)."""
    r = _co_report("a", "Alpha Co", 2024, ["Depreciation Rates"]).model_copy(update={"issued_date": None})
    s = patterns.summarize([r])
    dep = next(t for t in s.themes if t.theme == "Depreciation")
    assert dep.by_year == {}
    assert dep.report_count == 1
    assert dep.top_companies == [{"company": "Alpha Co", "report_count": 1}]
