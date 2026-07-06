"""Offline unit tests for pipeline/amounts.py — dollar parsing, sentence-bounded
quote extraction, and page location. No network."""
from __future__ import annotations

import pytest

from pipeline import amounts
from pipeline.models import Finding, PageText, Recommendation


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("$536,555", 536555.0),
        ("$1,152,358", 1152358.0),
        ("$82,195", 82195.0),
        ("$16.36 million", 16_360_000.0),
        ("$16.36million", 16_360_000.0),
        ("$2 billion", 2_000_000_000.0),
        ("$500 thousand", 500_000.0),
        ("$100", 100.0),
        ("$3.45", 3.45),
    ],
)
def test_parse_dollar_amount(raw, expected):
    assert amounts.parse_dollar_amount(raw) == expected


def test_first_dollar_mention_returns_containing_sentence_not_a_char_window():
    text = (
        "PSCo has a long history of proper accounting. "
        "PSCo improperly recorded $82,195 in compromise settlement payments relating to "
        "claims of alleged employee discrimination in Account 920. "
        "This is a separate unrelated sentence about something else."
    )
    hit = amounts._first_dollar_mention(text)
    assert hit is not None
    assert hit.raw == "$82,195"
    assert hit.amount_usd == 82195.0
    # The quote must be the WHOLE sentence, not a blind +/-N char slice — it should
    # start and end at real sentence punctuation, and must not spill into neighbors.
    assert hit.quote.startswith("PSCo improperly recorded $82,195")
    assert "employee discrimination in Account 920." in hit.quote
    assert "separate unrelated sentence" not in hit.quote
    assert "long history of proper accounting" not in hit.quote


def test_first_dollar_mention_none_when_no_dollar_figure():
    assert amounts._first_dollar_mention("No dollar figures in this sentence at all.") is None
    assert amounts._first_dollar_mention(None) is None
    assert amounts._first_dollar_mention("") is None


def test_find_primary_dollar_mention_prefers_summary_over_recommendations():
    f = Finding(
        index=1,
        title="Test finding",
        summary="The company overbilled customers $536,555 due to a tariff error.",
        recommendations=[Recommendation(number=1, text="Refund the $1,000,000 immediately.")],
    )
    hit = amounts.find_primary_dollar_mention(f)
    assert hit.raw == "$536,555"


def test_find_primary_dollar_mention_falls_back_to_recommendations():
    f = Finding(
        index=1,
        title="Test finding",
        summary="The company failed to follow its own tariff procedures.",
        recommendations=[
            Recommendation(number=1, text="No monetary impact for this item."),
            Recommendation(number=2, text="Refund the $1,000,000 overcollection to ratepayers."),
        ],
    )
    hit = amounts.find_primary_dollar_mention(f)
    assert hit.raw == "$1,000,000"
    assert hit.amount_usd == 1_000_000.0


def test_find_primary_dollar_mention_none_when_no_figures_anywhere():
    f = Finding(
        index=1,
        title="Test finding",
        summary="A purely qualitative finding with no dollar figures.",
        recommendations=[Recommendation(number=1, text="Update the procedure manual.")],
    )
    assert amounts.find_primary_dollar_mention(f) is None


def test_locate_page_finds_exact_sentence_match():
    mention = amounts.DollarMention(
        raw="$82,195",
        quote="PSCo improperly recorded $82,195 in compromise settlement payments.",
        amount_usd=82195.0,
    )
    pages = [
        PageText(page=1, char_count=10, is_image_only=False, extractor="pymupdf", text="Cover page, nothing relevant here."),
        PageText(
            page=7, char_count=200, is_image_only=False, extractor="pymupdf",
            text="Some preamble.\nPSCo improperly recorded $82,195 in compromise\nsettlement payments.\nMore text follows.",
        ),
    ]
    assert amounts.locate_page(mention, pages) == 7


def test_locate_page_falls_back_to_bare_dollar_figure_when_sentence_reflows():
    # A page-break/line-wrap can reflow the sentence differently than the committed
    # quote (extra whitespace collapses fine via _normalize, but if the sentence
    # genuinely differs we still credit the page if the bare figure is found).
    mention = amounts.DollarMention(
        raw="$536,555",
        quote="NDPL billed shippers, resulting in an overcollection of $536,555 for the period.",
        amount_usd=536555.0,
    )
    pages = [
        PageText(page=1, char_count=10, is_image_only=False, extractor="pymupdf", text="irrelevant"),
        PageText(
            page=12, char_count=50, is_image_only=False, extractor="pymupdf",
            text="...resulted in an overcollection totaling $536,555 across all shippers...",
        ),
    ]
    assert amounts.locate_page(mention, pages) == 12


def test_locate_page_none_when_not_found_anywhere():
    mention = amounts.DollarMention(raw="$1,234", quote="Nobody mentions $1,234 anywhere.", amount_usd=1234.0)
    pages = [PageText(page=1, char_count=10, is_image_only=False, extractor="pymupdf", text="completely unrelated text")]
    assert amounts.locate_page(mention, pages) is None
