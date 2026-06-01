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
    ("Informational postings", ["informational posting", "posting"]),
    ("Depreciation", ["depreciation"]),
    ("Affiliate / intercompany transactions", ["affiliate", "intercompany", "inter-company"]),
    ("Membership dues & industry associations", ["membership dues", "industry association"]),
    ("Below-the-line costs (lobbying, charitable, etc.)", ["lobbying", "charitable", "below-the-line", "nonoperating", "non-operating"]),
    ("Form reporting (Form No. 1/2/6, Page 700)", ["form no.", "page 700", "annual report", "reporting"]),
    ("Property & plant records", ["property unit", "carrier property", "noncarrier property", "plant in service", "property record"]),
    ("Creditworthiness", ["creditworthiness"]),
    ("Capitalization vs. expense", ["capitaliz"]),
    ("Cost of service & rates", ["cost of service", "cost-of-service", "rate base", "rate of return", "return on equity"]),
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
    keyword_lookup = {theme: kws for theme, kws in THEME_RULES}

    finding_count = other_count = rec_count = 0
    for r in reports:
        by_industry[r.industry or "unknown"] += 1
        if r.issued_date:
            by_year[str(r.issued_date.year)] += 1
        for fn in r.functions:
            by_function[fn] += 1
        for f in r.findings:
            rec_count += len(f.recommendations)
            if f.is_other_matter:
                other_count += 1
            else:
                finding_count += 1
                title_counts[f.title] += 1
            for theme in _themes_for(f.title + " " + (f.summary or "")):
                theme_findings[theme] += 1
                theme_reports[theme].add(r.id)
                if f.title not in theme_examples[theme] and len(theme_examples[theme]) < 4:
                    theme_examples[theme].append(f.title)

    themes = [
        ThemeStat(
            theme=theme,
            description=THEME_DESCRIPTIONS.get(theme, ""),
            keywords=keyword_lookup[theme],
            finding_count=theme_findings[theme],
            report_count=len(theme_reports[theme]),
            example_titles=theme_examples[theme],
        )
        for theme, _ in THEME_RULES
        if theme_findings[theme] > 0
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
