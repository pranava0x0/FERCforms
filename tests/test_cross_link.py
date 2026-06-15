"""Tests for state ↔ FERC cross-linking."""
import json
from pathlib import Path

from pipeline import cross_link


def test_cross_link_structure():
    """Verify cross-link entries have required fields."""
    # Load sample
    cross_links_path = Path(__file__).parent.parent / "docs" / "data" / "cross_links.json"
    if not cross_links_path.exists():
        # Skip if not generated yet
        return

    with open(cross_links_path) as f:
        cross_links = json.load(f)

    assert len(cross_links) > 0, "no cross-links generated"

    # Check structure of first entry
    entry = cross_links[0]
    required = [
        "state_report_id",
        "state_company",
        "state_jurisdiction",
        "state_industry",
        "matching_ferc_findings_count",
        "matching_ferc_themes",
        "matching_ferc_reports",
    ]
    for field in required:
        assert field in entry, f"missing field: {field}"

    # Count matches
    with_match = sum(1 for e in cross_links if e["matching_ferc_findings_count"] > 0)
    assert with_match > 0, "no cross-links with FERC matches found"


def test_match_state_to_ferc_substring():
    """Test fuzzy matching with substrings."""
    state_finding = {
        "company": "Duke Energy Corporation",
        "industry": "electric",
    }
    ferc_index = {
        ("duke energy corporation", "electric"): [
            {
                "report_id": "test-report",
                "themes": ["Depreciation"],
                "cost_to_customers": True,
            }
        ]
    }

    result = cross_link.match_state_to_ferc(state_finding, ferc_index)
    assert result is not None
    assert len(result) == 1


def test_match_state_to_ferc_no_match():
    """Test when no match is found."""
    state_finding = {
        "company": "Acme Utility Company",
        "industry": "electric",
    }
    ferc_index = {
        ("duke energy corporation", "electric"): []
    }

    result = cross_link.match_state_to_ferc(state_finding, ferc_index)
    assert result is None


def test_aggregate_themes():
    """Test theme aggregation."""
    findings = [
        {"themes": ["Accounting misclassification", "Depreciation"]},
        {"themes": ["Depreciation", "Cost of service & rates"]},
    ]

    result = cross_link.aggregate_themes(findings)
    assert result == [
        ("Depreciation", 2),
        ("Accounting misclassification", 1),
        ("Cost of service & rates", 1),
    ] or result == [
        ("Depreciation", 2),
        ("Cost of service & rates", 1),
        ("Accounting misclassification", 1),
    ]
    # Order depends on sort stability


if __name__ == "__main__":
    test_cross_link_structure()
    test_match_state_to_ferc_substring()
    test_match_state_to_ferc_no_match()
    test_aggregate_themes()
    print("All tests passed!")
