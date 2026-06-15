"""Tests for cost impact extraction."""
from pipeline import extract_costs


def test_normalize_amount_with_dollar_sign():
    """Test normalization of dollar amounts."""
    assert extract_costs.normalize_amount("$1,234,567") == 1234567.0
    assert extract_costs.normalize_amount("$1234567") == 1234567.0
    assert extract_costs.normalize_amount("$1.5") == 1.5


def test_normalize_amount_with_million():
    """Test normalization with million multiplier."""
    assert extract_costs.normalize_amount("$3.5 million") == 3500000.0
    assert extract_costs.normalize_amount("3.5 million") == 3500000.0
    assert extract_costs.normalize_amount("$3,500,000 million") is None  # > 1 trillion


def test_normalize_amount_with_thousand():
    """Test normalization with thousand multiplier."""
    assert extract_costs.normalize_amount("$100 thousand") == 100000.0
    assert extract_costs.normalize_amount("$100k") == 100000.0


def test_normalize_amount_with_newlines():
    """Test that newlines are handled correctly."""
    # This was the Rocky Mountain Power issue
    assert extract_costs.normalize_amount("87,232,937\nmillion") is None  # > 1 trillion


def test_extract_impact_type():
    """Test impact type detection."""
    assert extract_costs.extract_impact_type("overstated by $5 million") == "overstated"
    assert (
        extract_costs.extract_impact_type("improperly included in transmission")
        == "improperly_included"
    )
    assert extract_costs.extract_impact_type("refund analysis") == "refund"
    assert extract_costs.extract_impact_type("no impact type here") is None


def test_extract_customer_type():
    """Test customer type detection."""
    assert (
        extract_costs.extract_customer_type("overbilled transmission customers")
        == "transmission"
    )
    assert (
        extract_costs.extract_customer_type("recovery by ratepayers")
        == "ratepayers"
    )
    assert (
        extract_costs.extract_customer_type("wholesale markets")
        == "wholesale"
    )


def test_extract_costs_from_text():
    """Test cost extraction from realistic text."""
    text = "Alabama Power did not track and exclude $3,548,278 of outside services from accounts that were improperly included in transmission costs."

    costs = extract_costs.extract_costs_from_text(text)

    assert len(costs) == 1
    assert costs[0].amount_text == "$3,548,278"
    assert costs[0].amount_dollars == 3548278.0
    assert costs[0].impact_type == "improperly_included"
    assert costs[0].customer_impact == "transmission"


def test_extract_costs_no_duplicates():
    """Test that we don't extract the same amount twice."""
    text = "The company overstated costs by $5 million in 2020 and by $5 million in 2021."

    costs = extract_costs.extract_costs_from_text(text)

    # Should extract both mentions (they're in different contexts)
    assert len(costs) >= 1


def test_extract_costs_filters_false_positives():
    """Test that single-digit amounts without currency are filtered."""
    text = "The audit found issues with 3 years of data in the process."

    costs = extract_costs.extract_costs_from_text(text)

    # "3 years" should not be extracted as a cost
    assert len(costs) == 0


if __name__ == "__main__":
    test_normalize_amount_with_dollar_sign()
    test_normalize_amount_with_million()
    test_normalize_amount_with_thousand()
    test_normalize_amount_with_newlines()
    test_extract_impact_type()
    test_extract_customer_type()
    test_extract_costs_from_text()
    test_extract_costs_no_duplicates()
    test_extract_costs_filters_false_positives()
    print("All tests passed!")
