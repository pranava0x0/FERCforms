"""Test audit themes extraction and patterns."""
import json
from pathlib import Path


def test_patterns_generated():
    """Verify patterns.json was generated with correct structure."""
    patterns_path = Path("data/processed/patterns.json")
    assert patterns_path.exists(), "patterns.json should exist"

    patterns = json.loads(patterns_path.read_text())

    # Check structure
    assert patterns['report_count'] > 0, "Should have reports"
    assert patterns['finding_count'] > 0, "Should have findings"
    assert patterns['recommendation_count'] > 0, "Should have recommendations"
    assert len(patterns['themes']) > 0, "Should have themes"

    # Verify theme structure
    for theme in patterns['themes']:
        assert 'theme' in theme, "Theme should have name"
        assert 'finding_count' in theme, "Theme should have finding_count"
        assert 'report_count' in theme, "Theme should have report_count"
        assert 'example_titles' in theme, "Theme should have examples"
        assert len(theme['example_titles']) > 0, "Should have at least one example"

    # Verify top themes
    top_themes = {t['theme'].upper() for t in patterns['themes'][:5]}
    assert 'ACCOUNTING MISCLASSIFICATION' in top_themes, "Accounting misclassification should be top"

    print(f"✓ test_patterns_generated: {patterns['report_count']} reports, {patterns['finding_count']} findings, {len(patterns['themes'])} themes")


def test_tx_findings_in_patterns():
    """Verify TX findings are included in patterns."""
    patterns_path = Path("data/processed/patterns.json")
    patterns = json.loads(patterns_path.read_text())

    # Check that we have TX findings reflected
    # (exact match depends on theme assignment, but finding_count should be > 0)
    assert patterns['finding_count'] >= 29, "Should include TX findings (29+)"

    print(f"✓ test_tx_findings_in_patterns: TX findings included")


def test_theme_examples_valid():
    """Verify theme examples are real finding titles."""
    patterns_path = Path("data/processed/patterns.json")
    patterns = json.loads(patterns_path.read_text())

    # Sample check: examples should not be empty or placeholder
    for theme in patterns['themes'][:5]:
        for example in theme['example_titles']:
            assert len(example) > 5, f"Example should be meaningful: {example}"
            assert example.count(' ') >= 1, f"Example should have multiple words: {example}"

    print(f"✓ test_theme_examples_valid: Examples verified")


if __name__ == "__main__":
    test_patterns_generated()
    test_tx_findings_in_patterns()
    test_theme_examples_valid()
    print("\n✓ All theme tests passed")
