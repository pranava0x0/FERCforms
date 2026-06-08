"""Tests for the PA M&O Exhibit I-2 findings parser (pipeline/state_structure.py).

The synthetic fixture is the always-on gate (exercises the line state machine end to
end); the real-report block is a no-regression snapshot that skips when the PA text
isn't extracted locally (text.json is gitignored), mirroring test_structure.py.
"""
from __future__ import annotations

import json
import re
from datetime import date

import pytest

from pipeline import config, state_structure
from pipeline.models import PageText, ReportText, SourceSeed

# Synthetic Exhibit I-2: 4 chapters incl. a "None" area, multi-line rec text, a
# split timeframe column ("12-24"/"Months"), and a repeated page-break header run
# (Exhibit I-2 … Benefits) mid-table that must be skipped without dropping a rec.
_EXHIBIT = """Exhibit I-2
Summary of Recommendations
Rec.
No.
Recommendation
Page
No.
Initiation
Time Frame
Benefits
Chapter III – Executive Management and Organizational Structure
III-1
Conduct routine employee surveys to ensure
corporate culture aligns with company goals.
16
0-6 Months
Medium
Chapter IV – Corporate Governance
None
Chapter V – Cost Allocations and Affiliated Interests
V-1
Compare the internal cost of services to market
rates on a periodic basis.
29
12-24
Months
Medium
Exhibit I-2
Page 2 of 2
- 7 -
Some Utility Company
Management and Operations Audit
Summary of Recommendations
Rec.
No.
Recommendation
Page
No.
Initiation
Time Frame
Benefits
V-2
Develop refresher training to employees.
29
0-6 Months
Low
Chapter VI – Financial Management
VI-1
Create a formal dividend policy and notify the
PUC prior to paying dividends.
36
0-6 Months
Low
- 8 -
II.
BACKGROUND
"""


def _seed(parse: bool = True) -> SourceSeed:
    return SourceSeed(
        id="2024-01-01_some-utility_pa-mo-audit",
        company="Some Utility Company",
        collection="state_audit",
        jurisdiction="PA",
        source="PA PUC Bureau of Audits",
        doc_type="management & operations audit",
        industry="electric",
        pdf_url="https://www.puc.pa.gov/pcdocs/9999999.pdf",
        source_page_url="https://www.puc.pa.gov/press-release/2024/x",
        issued_date=date(2024, 1, 1),
        captured_at=date(2026, 6, 1),
        parse=parse,
    )


def test_parse_exhibit_i2_chapters_and_verbatim_recs():
    chapters = state_structure.parse_exhibit_i2(_EXHIBIT)
    titles = [t for t, _ in chapters]
    assert titles == [
        "Executive Management and Organizational Structure",
        "Corporate Governance",
        "Cost Allocations and Affiliated Interests",
        "Financial Management",
    ]
    by_title = dict(chapters)
    assert by_title["Corporate Governance"] == []  # "None" area -> no recs
    # each rec is (verbatim text, source_page): multi-line text joined verbatim, the
    # "Page No." column captured, trailing timeframe/benefit columns dropped
    assert by_title["Executive Management and Organizational Structure"] == [
        ("Conduct routine employee surveys to ensure corporate culture aligns with company goals.", 16)
    ]
    # the page-break header between V-1 and V-2 must not drop V-2; both cite page 29
    # (V-1's "12-24"/"Months" split timeframe must NOT be mistaken for the page no.)
    assert by_title["Cost Allocations and Affiliated Interests"] == [
        ("Compare the internal cost of services to market rates on a periodic basis.", 29),
        ("Develop refresher training to employees.", 29),
    ]


def test_structure_mo_audit_maps_findings_and_numbers_recs():
    pages = [PageText(page=1, char_count=len(_EXHIBIT), is_image_only=False, extractor="pymupdf", text=_EXHIBIT)]
    report = state_structure.structure_mo_audit(_seed(), pages, scanned_pages=[])
    assert report is not None
    assert report.structured is True
    assert report.finding_count == 3  # "None" chapter is not a finding
    assert [f.title for f in report.findings] == [
        "Executive Management and Organizational Structure",
        "Cost Allocations and Affiliated Interests",
        "Financial Management",
    ]
    # recommendations numbered sequentially across the report, verbatim, no column leakage
    recs = [r for f in report.findings for r in f.recommendations]
    assert [r.number for r in recs] == [1, 2, 3, 4]
    assert all(r.text and not re.search(r"^(Low|Medium|High)$|Months$|^\d+$", r.text) for r in recs)
    # the Exhibit I-2 "Page No." column is captured per rec (printed body page)
    assert [r.source_page for r in recs] == [16, 29, 29, 36]
    assert report.collection == "state_audit" and report.jurisdiction == "PA"


# National Fuel Gas variant: chapters as "III Title" (no "Chapter", no dash) and rec
# labels as "IV – 1" (spaces + en-dash). Same table, different typographic convention.
_EXHIBIT_NFG_VARIANT = """Exhibit I-3
Summary of Recommendations
Rec.
No.
Recommendation
Page
No.
Initiation
Time Frame
Benefits
III Executive Management and Organizational Structure
None
IV Corporate Governance
IV – 1
Expand the Board of Directors' expertise in key
skills outside the natural gas industry.
22
12 – 18 Months
Medium
V Affiliated Interests and Cost Allocations
V – 1
Update the affiliated interest agreement(s) to
include a description of emergency transfers.
29
6 – 9 Months
Low
II.
BACKGROUND
"""


def test_parse_handles_nfg_variant_nodash_chapters_and_endash_labels():
    """National Fuel Gas's M&O audit uses 'III Title' chapters (no 'Chapter'/dash) and
    'IV – 1' rec labels (spaced en-dash), and puts the Summary in Exhibit I-3 (its I-2
    is Quantifiable Savings). The parser must handle this without a 'Chapter' prefix."""
    chapters = state_structure.parse_exhibit_i2(_EXHIBIT_NFG_VARIANT)
    by_title = dict(chapters)
    assert "Executive Management and Organizational Structure" in by_title
    assert by_title["Executive Management and Organizational Structure"] == []  # "None"
    assert by_title["Corporate Governance"] == [
        ("Expand the Board of Directors' expertise in key skills outside the natural gas industry.", 22)
    ]
    assert by_title["Affiliated Interests and Cost Allocations"] == [
        ("Update the affiliated interest agreement(s) to include a description of emergency transfers.", 29)
    ]


def test_non_mo_format_returns_none():
    """A document without an Exhibit I-2 yields None (caller falls back to metadata-only)."""
    pages = [PageText(page=1, char_count=20, is_image_only=False, extractor="pymupdf", text="A legal order, no table.")]
    assert state_structure.structure_mo_audit(_seed(), pages, scanned_pages=[]) is None


# --- No-regression snapshot over the 3 real PA M&O audits (skips if not ingested) ---
@pytest.mark.parametrize(
    "rid, min_findings, min_recs",
    [
        ("2024-07-11_ppl-electric-utilities_pa-mo-audit", 8, 19),
        ("2022-06-16_firstenergy-pennsylvania-companies_pa-mo-audit", 11, 26),
        ("2023-03-02_philadelphia-gas-works_pa-mo-audit", 11, 32),
        ("2022-08-25_peco-energy_pa-mo-audit", 7, 22),
        ("2024-11-07_national-fuel-gas-distribution_pa-mo-audit", 11, 23),
        ("2019-07_duquesne-light-company_pa-mo-audit", 10, 18),
        ("2019-10_ugi-utilities_pa-mo-audit", 13, 45),
        ("2020-07-16_columbia-gas-of-pennsylvania_pa-mo-audit", 8, 18),
    ],
)
def test_real_pa_mo_audits_regression(rid, min_findings, min_recs):
    text_path = config.PROCESSED_DIR / rid / "text.json"
    if not text_path.exists():
        pytest.skip(f"{rid} not ingested locally (run: pipeline.sources --seed data/seeds/pa_puc.json)")
    seeds = {s["id"]: SourceSeed.model_validate(s) for s in json.loads((config.SEEDS_DIR / "pa_puc.json").read_text())}
    text = ReportText.model_validate_json(text_path.read_text(encoding="utf-8"))
    report = state_structure.structure_mo_audit(seeds[rid], text.pages, text.scanned_pages)
    assert report is not None
    assert report.finding_count >= min_findings
    assert sum(len(f.recommendations) for f in report.findings) >= min_recs
    assert all(f.title for f in report.findings)                       # every finding titled
    recs = [r for f in report.findings for r in f.recommendations]
    assert all(r.text for r in recs)                                   # every rec non-empty
    # every PA M&O rec carries its Exhibit I-2 "Page No." (a positive printed page)
    assert all(isinstance(r.source_page, int) and r.source_page > 0 for r in recs)
