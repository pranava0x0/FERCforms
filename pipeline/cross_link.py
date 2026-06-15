"""Generate state → FERC cross-link mappings.

For each state finding, identify matching FERC findings and themes.
Enables audit-my-document MVP: given a state filing, flag what to watch for.

Cross-link strategy:
1. Index FERC findings by company + industry
2. For each state finding:
   a. Match by exact company name + industry (highest confidence)
   b. If no exact match, try fuzzy company name match (cost-to-customers flag)
   c. Collect all FERC themes from matched audits
3. Generate cross_links.json: state_finding → [ferc_themes + examples]
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from pipeline import config

logger = logging.getLogger(__name__)


def load_reports(reports_path: Path) -> list[dict[str, Any]]:
    """Load all reports from reports.json."""
    with open(reports_path) as f:
        return json.load(f)


def build_ferc_index(reports: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Index FERC findings by (company, industry) for fast lookup.

    Returns: {(company, industry): [findings_with_context]}
    """
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for report in reports:
        if report.get("collection") != "ferc_audit":
            continue
        if not report.get("findings"):
            continue

        company = (report.get("company") or "").lower().strip()
        industry = (report.get("industry") or "").lower().strip()

        if not company or not industry:
            continue

        key = (company, industry)

        for finding in report["findings"]:
            index[key].append({
                "report_id": report["id"],
                "company": report.get("company"),
                "industry": industry,
                "audit_type": report.get("audit_type"),
                "issued_date": report.get("issued_date"),
                "finding_title": finding.get("title"),
                "themes": finding.get("themes", []),
                "cost_to_customers": finding.get("cost_to_customers", False),
            })

    return index


def match_state_to_ferc(
    state_finding: dict[str, Any],
    ferc_index: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]] | None:
    """Find matching FERC findings for a state finding.

    Strategy:
    1. Exact company + industry match (highest confidence)
    2. Substring match (parent/subsidiary: "FirstEnergy" ⊂ "FirstEnergy Pennsylvania")
    3. Return FERC findings that touch cost-to-customers (highest impact)
    """
    company = (state_finding.get("company") or "").lower().strip()
    industry = (state_finding.get("industry") or "").lower().strip()

    if not company or not industry:
        return None

    key = (company, industry)

    # Exact match
    if key in ferc_index:
        return ferc_index[key]

    # Fuzzy matching: substring or parent/subsidiary relationship
    for (k_company, k_industry), findings in ferc_index.items():
        if k_industry != industry:
            continue

        # Both directions: "ppl electric utilities" ⊂ "ppl electric"
        #                 or "firstenergy corporation" ⊂ "firstenergy pennsylvania"
        if company in k_company or k_company in company:
            logger.debug(f"fuzzy match: {company} ({industry}) → {k_company}")
            return findings

    return None


def aggregate_themes(findings: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Count themes across matched findings, return sorted list.

    Returns: [(theme, count), ...]
    """
    theme_counts: dict[str, int] = defaultdict(int)

    for finding in findings:
        for theme in finding.get("themes", []):
            theme_counts[theme] += 1

    return sorted(theme_counts.items(), key=lambda x: -x[1])


def build_cross_links(
    reports: list[dict[str, Any]],
    ferc_index: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Generate cross-link entries for all state findings."""
    cross_links = []

    for report in reports:
        if report.get("collection") not in ("state_audit", "state_rate_case"):
            continue
        if not report.get("findings"):
            continue

        for finding in report["findings"]:
            # Build a state finding context
            state_finding = {
                "company": report.get("company"),
                "industry": report.get("industry"),
                "jurisdiction": report.get("jurisdiction"),
                "doc_type": report.get("doc_type"),
                "issued_date": report.get("issued_date"),
                "finding_title": finding.get("title"),
                "finding_themes": finding.get("themes", []),
                "finding_cost_to_customers": finding.get("cost_to_customers", False),
            }

            # Match to FERC findings
            matched_ferc = match_state_to_ferc(state_finding, ferc_index)

            if not matched_ferc:
                # No FERC match; still record for reference
                cross_links.append({
                    "state_report_id": report["id"],
                    "state_company": report.get("company"),
                    "state_jurisdiction": report.get("jurisdiction"),
                    "state_industry": report.get("industry"),
                    "state_finding_title": finding.get("title"),
                    "state_finding_themes": finding.get("themes", []),
                    "state_cost_to_customers": finding.get("cost_to_customers", False),
                    "matching_ferc_findings_count": 0,
                    "matching_ferc_themes": [],
                    "matching_ferc_reports": [],
                })
                continue

            # Aggregate themes from matched FERC findings
            theme_counts = aggregate_themes(matched_ferc)
            top_themes = [t for t, _ in theme_counts[:5]]  # top 5 themes

            # Collect unique FERC reports
            ferc_reports = set()
            for finding in matched_ferc:
                ferc_reports.add(finding["report_id"])

            cross_links.append({
                "state_report_id": report["id"],
                "state_company": report.get("company"),
                "state_jurisdiction": report.get("jurisdiction"),
                "state_industry": report.get("industry"),
                "state_finding_title": finding.get("title"),
                "state_finding_themes": finding.get("themes", []),
                "state_cost_to_customers": finding.get("cost_to_customers", False),
                "matching_ferc_findings_count": len(matched_ferc),
                "matching_ferc_themes": top_themes,
                "matching_ferc_reports": sorted(list(ferc_reports)),
                "theme_distribution": [
                    {"theme": t, "count": c} for t, c in theme_counts
                ],
            })

    return cross_links


def main():
    reports_path = config.DOCS_DIR / "data" / "reports.json"
    cross_links_path = config.DOCS_DIR / "data" / "cross_links.json"

    logger.info(f"loading reports from {reports_path}")
    reports = load_reports(reports_path)

    logger.info(f"building FERC index")
    ferc_index = build_ferc_index(reports)
    logger.info(f"FERC index: {len(ferc_index)} (company, industry) pairs")

    logger.info(f"generating cross-links")
    cross_links = build_cross_links(reports, ferc_index)

    # Count matches
    with_match = sum(1 for cl in cross_links if cl["matching_ferc_findings_count"] > 0)
    logger.info(
        f"generated {len(cross_links)} cross-links ({with_match} with FERC matches)"
    )

    logger.info(f"writing to {cross_links_path}")
    with open(cross_links_path, "w") as f:
        json.dump(cross_links, f, indent=2)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    main()
