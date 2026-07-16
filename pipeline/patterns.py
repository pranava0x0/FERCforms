"""Mine cross-report patterns from structured audit reports.

Aggregates every data/processed/<id>/report.json into corpus stats and themes.
Theming is **transparent keyword tagging** — not LLM/subjective classification
(see AGENTS.md). Each theme lists the keywords that triggered it and real
example titles, so a reader can audit every assignment. Finding titles are also
counted verbatim. Output: data/processed/patterns.json.
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from datetime import date
from pathlib import Path

from pipeline import config
from pipeline.models import AuditReport, PatternsSummary, ThemeStat

logger = logging.getLogger(__name__)

# (theme label, keyword substrings). A finding matches if any keyword is a
# substring of its lowercased "title + summary". Findings can match multiple
# themes. Keep keywords specific enough to audit by eye.
THEME_RULES: list[tuple[str, list[str]]] = [
    ("Accounting misclassification", ["misclassif", "incorrectly recorded", "improperly recorded", "improperly included", "incorrectly included"]),
    ("AFUDC / cost of capital", ["allowance for funds used during construction", "afudc"]),
    ("Tariff administration & oversight", ["tariff"]),
    # NOTE: bare "posting" was tightened 2026-06-10 — it matched financial
    # "collateral postings" (an SCE AFUDC finding) and an SAP "reconciliation
    # posting" (PSE&G audit). The compounds below cover every real OASIS/
    # informational-posting finding in the corpus.
    ("Informational postings", ["informational posting", "posting of", "outage postings", "postings for monthly"]),
    ("Depreciation", ["depreciation"]),
    ("Affiliate / intercompany transactions", ["affiliate", "intercompany", "inter-company"]),
    ("Membership dues & industry associations", ["membership dues", "industry association"]),
    ("Below-the-line costs (lobbying, charitable, etc.)", ["lobbying", "charitable", "below-the-line", "nonoperating", "non-operating"]),
    # NOTE: bare "reporting" was removed 2026-06-08 — once recommendation text is
    # scanned it over-matched state-audit "financial reporting"/"reporting systems"
    # language and mislabeled them as FERC Form-1 issues. Keep FERC-specific anchors.
    # "annual report" removed 2026-06-10: its only corpus hit was a PSE&G footnote
    # citing the company's BPU annual report — FERC contexts are covered by "form no.".
    ("Form reporting (Form No. 1/2/6, Page 700)", ["form no.", "page 700"]),
    ("Property & plant records", ["property unit", "carrier property", "noncarrier property", "plant in service", "property record"]),
    ("Creditworthiness", ["creditworthiness"]),
    ("Capitalization vs. expense", ["capitaliz"]),
    ("Cost of service & rates", ["cost of service", "cost-of-service", "rate base", "rate of return", "return on equity", "rate design"]),
    # --- State management & operations audit themes (PA Bureau of Audits, NY/NJ
    # focused & management audits, etc.). These audits carry generic functional-area
    # finding titles ("Gas Operations") with the substance in the recommendation
    # text, so theme-matching scans recommendations too (see finding_theme_text).
    # Keyword sets calibrated by eye against the real recommendation corpus.
    ("Cybersecurity & physical security", ["cyber", "physical security"]),
    ("Emergency preparedness & business continuity", ["emergency prepared", "business continu", "emergency response", "emergency management", "mutual assist"]),
    ("Workforce, training & succession planning", ["succession", "span of control", "spans of control", "training", "workforce plan", "learning management"]),
    ("Internal audit & internal controls", ["internal audit", "internal control", "delegation of authority", "code of business conduct", "compliance program"]),
    ("Information technology & systems", ["information technology", "customer information system", "it budget", "it project", "it backlog", "it governance"]),
    # NOTE: bare "billing" was tightened 2026-06-10 — ~50 of its 72 corpus hits were
    # FERC *wholesale formula-rate* language ("overbillings to wholesale transmission
    # customers", "joint owner billing"), not retail customer service. The compounds
    # below keep every real retail billing finding (M&O audit recs say "billing and
    # collections", "billing process", "billing adjustments", "metering and billing").
    # "accounts receivable" also removed: it matched FERC *tax*-receivable findings
    # via the account names (143, other accounts receivable) — never retail service.
    ("Customer service & billing", ["customer service", "billing and collections", "metering and billing", "billing process", "billing adjustment", "billing accuracy", "billing lag", "call center", "meter reading", "customer experience"]),
    # NOTE: bare "inventory" tightened 2026-06-10 — it matched metaphorical backlogs
    # ("inventory of outstanding Class A leaks", a gas-safety matter). Compounds keep
    # all real materials/fuel inventory findings.
    ("Inventory, materials & fleet", ["inventory accuracy", "inventory turnover", "inventory tracking", "inventory balance", "physical inventory", "inventory optimization", "inventory accounting", "inventory count", "supplies inventory", "materials management", "fleet management", "vehicle replacement"]),
    # NOTE: bare "reliability"/"outage" tightened 2026-06-10 — they matched
    # "reliability of information reported" (a Form-1 finding), the FERC account name
    # "561.5, reliability planning", and PJM *generation outage reporting* findings;
    # this theme is distribution/service reliability (SAIDI/CAIDI, storm, vegetation).
    ("Service reliability & vegetation management", ["vegetation", "electric reliability", "service reliability", "reliability performance", "reliability metric", "reliability program", "reliability report", "saidi", "caidi", "outage cause", "outages caused", "emergency outage", "outage management", "outage response"]),
    ("Gas safety & pipeline integrity", ["class a leak", "main leak", "cathodic", "corros", "damage prevention", "pipeline integrity", "leak management"]),
    # NOTE: bare "dividend" tightened 2026-06-10 — it matched the FERC account *name*
    # "419, interest and dividend income" in AFUDC-misclassification findings.
    ("Dividend policy & capital management", ["dividend policy", "dividend payment", "dividend payout"]),
    # --- Rate-case / prudence-review themes (added 2026-06-10). Those collections
    # are dominated by fuel/purchased-power and storm cost-recovery vocabulary the
    # audit-centric rules above never matched — the Prudence Reviews tab showed 0
    # themes. Compounds calibrated against every corpus hit; "erra" is never used
    # bare ("Sierra" contains the substring).
    ("Fuel & purchased-power cost recovery", [
        "fuel cost", "fuel adjustment", "fuel factor", "fuel clause", "fuel reconciliation",
        "fuel expense", "fuel recovery", "fuel procurement", "fuel rider", "fuel forecast",
        "fuel contract", "fuel storage", "fuel retention", "fuel retainage", "fuel mechanism",
        "auxiliary fuel", "purchased power", "purchased-power", "power cost adjustment",
        "power cost update", "net power cost", "deferred energy", "energy balancing account",
        "energy resource recovery account", "erra compliance", "erra reasonableness",
        "gas cost recovery", "gas cost adjustment", "energy cost recovery",
    ]),
    ("Storm cost recovery & securitization", [
        "storm cost", "storm protection plan", "storm restoration", "storm damage",
        "storm rider", "storm expense", "storm recovery", "storm deferral", "storm revenue",
        "storm reserve", "securitization",
    ]),
]

# Plain-English explanation of each theme, shown on the site's pattern cards and
# in llms.txt. Keep one concise, neutral sentence (≈≤12 words) per theme — a
# glossary for navigation, NOT a characterization of any report's findings.
# SINGLE SOURCE OF TRUTH: editing these (or THEME_RULES) means the baked output
# is stale — re-run `python -m pipeline.build` to refresh docs/data/patterns.json
# AND docs/llms.txt + llms-full.txt. A test asserts every theme has a description.
THEME_DESCRIPTIONS: dict[str, str] = {
    "Accounting misclassification": "Costs or revenues booked to the wrong FERC account.",
    "AFUDC / cost of capital": "Mis-stated AFUDC — the financing cost capitalized during construction.",
    "Tariff administration & oversight": "Not following the utility's own FERC-approved tariff.",
    "Informational postings": "Required public postings (e.g., OASIS) missing, late, or incomplete.",
    "Depreciation": "Unapproved or incorrect depreciation rates applied to plant.",
    "Affiliate / intercompany transactions": "Transactions with affiliated companies mis-priced or mis-reported.",
    "Membership dues & industry associations": "Trade-association dues (e.g., EEI) improperly charged to ratepayers.",
    "Below-the-line costs (lobbying, charitable, etc.)": "Non-recoverable costs (lobbying, charity, ads) charged to ratepayers.",
    "Form reporting (Form No. 1/2/6, Page 700)": "Errors or omissions in the annual FERC forms utilities file.",
    "Property & plant records": "Incomplete or inaccurate utility plant and property records.",
    "Creditworthiness": "Customer credit standards not applied as the tariff requires.",
    "Capitalization vs. expense": "Costs capitalized that should be expensed, or the reverse.",
    "Cost of service & rates": "Errors in rate-base or return inputs to cost-of-service rates.",
    "Cybersecurity & physical security": "Gaps in cyber defenses or physical security of facilities and systems.",
    "Emergency preparedness & business continuity": "Weak emergency response, storm readiness, or business-continuity planning.",
    "Workforce, training & succession planning": "Staffing, training, span-of-control, or leadership-succession shortcomings.",
    "Internal audit & internal controls": "Weak internal controls, compliance programs, or internal-audit coverage.",
    "Information technology & systems": "IT governance, systems, budgets, or project-management deficiencies.",
    "Customer service & billing": "Customer-service performance, billing accuracy, or call-center issues.",
    "Inventory, materials & fleet": "Inventory accuracy, materials management, or fleet/vehicle management gaps.",
    "Service reliability & vegetation management": "Electric reliability (SAIDI/CAIDI), outages, or vegetation-management programs.",
    "Gas safety & pipeline integrity": "Gas leak backlogs, corrosion control, or pipeline-integrity practices.",
    "Dividend policy & capital management": "Dividend-policy or capital-management practices flagged by auditors.",
    "Fuel & purchased-power cost recovery": "Fuel, purchased-power, and energy-cost recovery or prudence matters.",
    "Storm cost recovery & securitization": "Storm restoration costs, storm riders/reserves, or securitization.",
}


# The "ratepayer harm" axis (BACKLOG policy review, 2026-06-01): the subset of
# themes whose finding type, by its nature, means costs were over-recovered from
# or wrongly charged to customers. Deliberately CONSERVATIVE — only classes whose
# *direction* is unambiguous overcharge. Excludes ambiguous-direction themes
# (capitalization vs expense, generic misclassification) and process / records /
# reporting / transparency themes. Must stay a subset of THEME_RULES labels (a
# test enforces this); editing it means re-running `python -m pipeline.build`.
RATEPAYER_HARM_THEMES: frozenset[str] = frozenset({
    "Below-the-line costs (lobbying, charitable, etc.)",
    "Membership dues & industry associations",
    "Affiliate / intercompany transactions",
    "Depreciation",
    "AFUDC / cost of capital",
    "Cost of service & rates",
})


def _themes_for(text: str) -> list[str]:
    low = text.lower()
    return [theme for theme, kws in THEME_RULES if any(k in low for k in kws)]


def finding_theme_text(finding, *, include_recs: bool = True) -> str:
    """The text a finding is theme-matched against. Single source of truth — used by
    both summarize() and pipeline.build's per-finding tagging so the corpus stats and
    the per-record tags can never drift apart.

    `include_recs` is collection-dependent (callers pass `r.collection != "ferc_audit"`):
      - State management & operations audits carry GENERIC functional-area titles
        ('Gas Operations', 'Customer Service') with the substance in the recs, so the
        recommendation text MUST be scanned for their patterns to surface at all.
      - FERC audit findings already have descriptive titles/summaries; scanning their
        recs adds noise — e.g. an accounting-misclassification finding whose rec says
        'train staff on proper classification' would wrongly tag as a workforce/training
        pattern. So for FERC we match title+summary only (verified 2026-06-08: scanning
        FERC recs inflated 'Workforce, training' from a handful to 227 findings)."""
    parts = [finding.title, finding.summary or ""]
    if include_recs:
        parts += [r.text for r in finding.recommendations]
    return " ".join(parts)


def descriptor_themes(report: "AuditReport") -> list[str]:
    """Theme tags for *reference* records (structured=False) derived from their
    displayed descriptors — `doc_type` + `source_note` (both rendered on the card,
    so every tag stays auditable by eye). Reference records carry no machine-parsed
    findings, so without this the Prudence Reviews / State Rate Cases tabs surfaced
    no themes at all (added 2026-06-10). Machine-parsed reports (structured=True)
    return [] — their themes come from finding text only, and a FERC audit whose
    parser found 0 findings stays untagged rather than themed from our own prose.
    Never feeds the ratepayer-harm flag — that stays finding-derived."""
    if report.structured:
        return []
    return _themes_for(" ".join(filter(None, [report.doc_type or "", report.source_note or ""])))


def is_ratepayer_harm(themes: list[str]) -> bool:
    """True if any theme is in the curated ratepayer-harm set (over-recovery /
    costs wrongly charged to customers). See RATEPAYER_HARM_THEMES."""
    return any(t in RATEPAYER_HARM_THEMES for t in themes)


def load_reports(processed_dir: Path) -> list[AuditReport]:
    reports: list[AuditReport] = []
    for path in sorted(processed_dir.glob("*/report.json")):
        try:
            reports.append(AuditReport.model_validate_json(path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            logger.error("skip %s: %s", path, exc)
    return reports


def summarize(reports: list[AuditReport]) -> PatternsSummary:
    by_industry: Counter[str] = Counter()
    by_year: Counter[str] = Counter()
    by_function: Counter[str] = Counter()
    title_counts: Counter[str] = Counter()
    theme_findings: Counter[str] = Counter()
    theme_reports: dict[str, set[str]] = {theme: set() for theme, _ in THEME_RULES}
    theme_examples: dict[str, list[str]] = {theme: [] for theme, _ in THEME_RULES}
    # A5 drill-down: per-theme year + company tallies, counted once per REPORT.
    theme_years: dict[str, Counter[str]] = {theme: Counter() for theme, _ in THEME_RULES}
    theme_companies: dict[str, Counter[str]] = {theme: Counter() for theme, _ in THEME_RULES}
    keyword_lookup = {theme: kws for theme, kws in THEME_RULES}

    finding_count = other_count = rec_count = 0
    for r in reports:
        by_industry[r.industry or "unknown"] += 1
        if r.issued_date:
            by_year[str(r.issued_date.year)] += 1
        for fn in r.functions:
            by_function[fn] += 1
        # Themes this REPORT carries — collected first, then tallied once, so a
        # report restating one theme across several findings counts once.
        report_themes: set[str] = set()
        for f in r.findings:
            rec_count += len(f.recommendations)
            if f.is_other_matter:
                other_count += 1
            else:
                finding_count += 1
                title_counts[f.title] += 1
            for theme in _themes_for(finding_theme_text(f, include_recs=r.collection != "ferc_audit")):
                theme_findings[theme] += 1   # per-finding, unlike the tallies below
                report_themes.add(theme)
                if f.title not in theme_examples[theme] and len(theme_examples[theme]) < 4:
                    theme_examples[theme].append(f.title)
        # Reference records (structured=False) also count toward a theme's report
        # tally via their displayed descriptors — finding_count stays finding-only.
        report_themes.update(descriptor_themes(r))
        for theme in report_themes:
            theme_reports[theme].add(r.id)
            if r.issued_date:
                theme_years[theme][str(r.issued_date.year)] += 1
            theme_companies[theme][r.company] += 1

    themes = [
        ThemeStat(
            theme=theme,
            description=THEME_DESCRIPTIONS.get(theme, ""),
            keywords=keyword_lookup[theme],
            finding_count=theme_findings[theme],
            report_count=len(theme_reports[theme]),
            example_titles=theme_examples[theme],
            by_year=dict(sorted(theme_years[theme].items())),
            top_companies=[
                {"company": c, "report_count": n} for c, n in theme_companies[theme].most_common(5)
            ],
        )
        for theme, _ in THEME_RULES
        if theme_findings[theme] > 0 or theme_reports[theme]
    ]
    themes.sort(key=lambda t: (t.report_count, t.finding_count), reverse=True)

    top_titles = [{"title": t, "count": c} for t, c in title_counts.most_common(25)]

    return PatternsSummary(
        report_count=len(reports),
        finding_count=finding_count,
        other_matter_count=other_count,
        recommendation_count=rec_count,
        by_industry=dict(by_industry.most_common()),
        by_year=dict(sorted(by_year.items())),
        by_function=dict(by_function.most_common()),
        themes=themes,
        top_titles=top_titles,
        generated_at=date.today(),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Mine cross-report patterns")
    ap.add_argument("--out", type=Path, default=config.PROCESSED_DIR / "patterns.json")
    args = ap.parse_args()

    reports = load_reports(config.PROCESSED_DIR)
    if not reports:
        logger.warning("no structured reports found in %s (run structure first)", config.PROCESSED_DIR)
        return
    summary = summarize(reports)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    logger.info(
        "patterns: %d reports, %d findings, %d themes -> %s",
        summary.report_count, summary.finding_count, len(summary.themes), args.out,
    )


if __name__ == "__main__":
    main()
