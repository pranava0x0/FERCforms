"""Tests for FERC form / industry / audit-type detection (pipeline/forms.py)."""
from __future__ import annotations

from pipeline import forms


def test_detect_forms():
    assert forms.detect_forms("FERC Form No. 1 and FERC Form No. 60") == ["1", "60"]
    assert forms.detect_forms("FERC Form No.2 here") == ["2"]
    assert forms.detect_forms("no forms mentioned") == []


def test_primary_industry_electric_financial():
    text = "compliance with FERC Form No. 1 under the Federal Power Act, 18 C.F.R. Part 101"
    assert forms.primary_industry(text) == "electric"


def test_primary_industry_electric_performance_without_form():
    # A performance audit that never cites the form — statute/OATT/ISO signals carry it.
    text = "audit of the Open Access Transmission Tariff of an independent system operator (ISO)"
    assert forms.primary_industry(text) == "electric"


def test_primary_industry_gas():
    text = "the FERC Gas Tariff under the Natural Gas Act; FERC Form No. 2 reporting"
    assert forms.primary_industry(text) == "gas"


def test_primary_industry_oil():
    text = "oil pipeline subject to the Interstate Commerce Act, FERC Form No. 6, Part 352"
    assert forms.primary_industry(text) == "oil"


def test_primary_industry_none():
    assert forms.primary_industry("nothing industry-identifying here") is None


def test_audit_type_from_docket():
    assert forms.audit_type_from_docket("FA23-8") == "financial"
    assert forms.audit_type_from_docket("PA22-7") == "performance"
    assert forms.audit_type_from_docket("XY00-0") is None
    assert forms.audit_type_from_docket(None) is None
