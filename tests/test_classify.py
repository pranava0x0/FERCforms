"""Tests for corpus classification selection (pipeline/classify.py).

PDF scanning is exercised by the live `classify` CLI; here we cover the pure
selection logic.
"""
from __future__ import annotations

from pipeline import classify


def test_electric_ids_filters_and_preserves_order():
    classification = {
        "a": {"industry": "electric"},
        "b": {"industry": "gas"},
        "c": {"industry": "electric"},
        "d": {"industry": None},
        "e": {"industry": "oil"},
    }
    assert classify.electric_ids(classification) == ["a", "c"]


def test_electric_ids_empty():
    assert classify.electric_ids({}) == []
    assert classify.electric_ids({"a": {"industry": "gas"}}) == []
