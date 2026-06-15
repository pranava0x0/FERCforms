"""Extract dollar-impact information from audit findings.

Cost impacts appear in finding summaries and recommendations:
  - "$3,548,278 of outside services...improperly included"
  - "overstated...by approximately $7.6 million"
  - "refund analysis...calculation of refunds"

Extracts:
  - Amount (in dollars or millions)
  - Impact type (overstated, improperly included, refund, recovery, adjustment)
  - Customer type (transmission, distribution, wholesale, ratepayers, etc.)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pipeline import config

logger = logging.getLogger(__name__)


@dataclass
class CostImpact:
    """An extracted cost impact from a finding."""

    amount_text: str  # original text: "$3.5 million" or "$3,548,278"
    amount_dollars: Optional[float]  # normalized: 3548278.0 or 3500000.0
    impact_type: str  # "overstated", "improperly_included", "refund", "adjustment", etc.
    customer_impact: Optional[str]  # "transmission", "ratepayers", "wholesale", etc.
    source: str  # "summary" or "recommendation"


# Patterns for extracting costs
# Matches: $1,234,567 or $1.5 million or 123 million dollars
AMOUNT_PATTERN = re.compile(
    r"\$?[\d,]+(?:\.\d+)?\s*(?:million|thousand|M|K)?|\$[\d,]+(?:\.\d+)?",
    re.IGNORECASE,
)

# Impact types (ordered by confidence)
IMPACT_PATTERNS = {
    "overstated": r"overstat|excess",
    "improperly_included": r"improperly\s+(?:includ|account|record|bill|charg)",
    "overstated_revenue": r"overbill|overcharg",
    "refund": r"refund",
    "recovery": r"recover",
    "adjustment": r"adjust",
    "questioned": r"question",
    "disallow": r"disallow|not allow",
}

# Customer types
CUSTOMER_PATTERNS = {
    "transmission": r"transmission",
    "distribution": r"distribution",
    "wholesale": r"wholesale",
    "ratepayers": r"ratepa|customers|consumer",
}


def normalize_amount(text: str) -> Optional[float]:
    """Convert amount text to dollars.

    Examples:
      "$3,548,278" → 3548278.0
      "$3.5 million" → 3500000.0
      "7.6 million" → 7600000.0
    """
    # Remove whitespace (including newlines)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)  # normalize internal whitespace

    # Check for million/thousand multipliers
    multiplier = 1.0
    if "million" in text.lower():
        multiplier = 1_000_000.0
        text = re.sub(r"\s*(?:million|m)\b", "", text, flags=re.I)
    elif "thousand" in text.lower() or re.search(r"k\b", text, re.I):
        multiplier = 1_000.0
        text = re.sub(r"\s*(?:thousand|k)\b", "", text, flags=re.I)

    # Extract numeric value
    text = text.strip("$").replace(",", "").strip()

    # Sanity check: amount should be < 1 trillion (anything bigger is likely a mistake)
    try:
        value = float(text)
        result = value * multiplier
        if result > 1_000_000_000_000:  # > 1 trillion
            return None
        return result
    except ValueError:
        return None


def extract_impact_type(text: str) -> Optional[str]:
    """Identify the cost impact type."""
    text_lower = text.lower()

    for impact_type, pattern in IMPACT_PATTERNS.items():
        if re.search(pattern, text_lower):
            return impact_type

    return None


def extract_customer_type(text: str) -> Optional[str]:
    """Identify which customers were impacted."""
    text_lower = text.lower()

    for customer_type, pattern in CUSTOMER_PATTERNS.items():
        if re.search(pattern, text_lower):
            return customer_type

    return None


def extract_costs_from_text(text: str, source: str = "summary") -> list[CostImpact]:
    """Extract all cost impacts from a text block.

    Args:
        text: Finding summary or recommendation text
        source: "summary" or "recommendation"

    Returns:
        List of CostImpact objects (may be empty)
    """
    if not text:
        return []

    costs = []

    # Find all amount mentions
    for amount_match in AMOUNT_PATTERN.finditer(text):
        amount_text = amount_match.group(0).strip()

        # Skip obviously invalid patterns (punctuation, single digits without currency)
        if amount_text in (",", ".", " ", "") or (
            len(amount_text) == 1 and not amount_text.startswith("$")
        ):
            continue

        # Get context around the amount (up to 150 chars before and after)
        start = max(0, amount_match.start() - 150)
        end = min(len(text), amount_match.end() + 150)
        context = text[start:end]

        # Determine impact type from context
        impact_type = extract_impact_type(context)
        if not impact_type:
            continue  # Skip amounts without clear impact context

        # Normalize amount
        amount_dollars = normalize_amount(amount_text)
        if amount_dollars is None:
            continue  # Skip amounts that couldn't be normalized

        # Skip suspiciously small amounts (probably false positives)
        if amount_dollars < 100 and not ("$" in amount_text or "million" in amount_text.lower()):
            continue

        # Determine customer type
        customer_type = extract_customer_type(context)

        costs.append(
            CostImpact(
                amount_text=amount_text,
                amount_dollars=amount_dollars,
                impact_type=impact_type,
                customer_impact=customer_type,
                source=source,
            )
        )

    return costs


def enrich_findings(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add cost_impacts field to all findings."""
    enriched = 0

    for report in reports:
        if not report.get("findings"):
            continue

        for finding in report["findings"]:
            costs = []

            # Extract from summary
            summary = finding.get("summary")
            if summary:
                costs.extend(extract_costs_from_text(summary, source="summary"))

            # Extract from recommendations
            for rec in finding.get("recommendations", []):
                rec_text = rec.get("text")
                if rec_text:
                    costs.extend(
                        extract_costs_from_text(rec_text, source="recommendation")
                    )

            if costs:
                # Store as list of dicts (JSON-serializable)
                finding["cost_impacts"] = [
                    {
                        "amount_text": c.amount_text,
                        "amount_dollars": c.amount_dollars,
                        "impact_type": c.impact_type,
                        "customer_impact": c.customer_impact,
                        "source": c.source,
                    }
                    for c in costs
                ]
                enriched += 1

    logger.info(f"enriched {enriched} findings with cost impacts")
    return reports


def main():
    reports_path = config.DOCS_DIR / "data" / "reports.json"
    backup_path = config.DOCS_DIR / "data" / "reports_pre_cost_extraction.json"

    logger.info(f"loading reports from {reports_path}")
    with open(reports_path) as f:
        reports = json.load(f)

    # Backup original
    logger.info(f"backing up to {backup_path}")
    with open(backup_path, "w") as f:
        json.dump(reports, f)

    # Enrich with cost impacts
    logger.info(f"extracting cost impacts from {len(reports)} reports")
    reports = enrich_findings(reports)

    # Write back
    logger.info(f"writing enriched reports to {reports_path}")
    with open(reports_path, "w") as f:
        json.dump(reports, f)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    main()
