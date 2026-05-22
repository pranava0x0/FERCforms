"""Tests for the report structurer (pipeline/structure.py)."""
from __future__ import annotations

import json
from datetime import date

import pytest

from pipeline import config, structure
from pipeline.models import ListingEntry, PageText, ReportText

_COVER = """FEDERAL ENERGY REGULATORY COMMISSION
Office of Enforcement
Docket No. PA99-1-000
March 5, 2024
Dear Ms. Smith:
The Division of Audits and Accounting has completed an audit.
The audit covered the period January 1, 2021 to December 31, 2022.
The audit evaluated compliance with the FERC Form No. 1 reporting requirements.
"""

_BODY = """Some Company Docket No. PA99-1-000
C. Summary of Noncompliance Findings
Audit staff identified two areas of noncompliance, summarized below:
1. Alpha Topic – The company recorded wrong thing A that
continued onto a second line.
2. Beta Topic – The company misclassified thing B.
D. Recommendations
Audit staff's recommendations to remedy the audit report findings are listed below.
Alpha Topic
1. Fix thing A properly and consistently.
2. Train staff on A.
Beta Topic
3. Reclassify thing B.
E. Compliance and Implementation of Recommendations
Submit a plan within 30 days.
"""


def _report_text() -> ReportText:
    return ReportText(
        id="2024-03-05_some-company_pa99-1",
        accession_number="20240305-0001",
        page_count=2,
        scanned_pages=[],
        ocr_used=False,
        pages=[
            PageText(page=1, char_count=len(_COVER), is_image_only=False, extractor="pdfplumber", text=_COVER),
            PageText(page=2, char_count=len(_BODY), is_image_only=False, extractor="pdfplumber", text=_BODY),
        ],
    )


def _entry() -> ListingEntry:
    return ListingEntry(
        id="2024-03-05_some-company_pa99-1",
        company="Some Company",
        company_raw="Some Company (PA99-1)",
        docket="PA99-1",
        accession_number="20240305-0001",
        issued_date=date(2024, 3, 5),
        source_page_url="https://elibrary.ferc.gov/eLibrary/filelist?accession_number=20240305-0001",
        pdf_download_url="https://elibrary.ferc.gov/eLibraryWebAPI/api/File/DownloadPDF?accesssionNumber=20240305-0001",
        captured_at=date(2026, 2, 3),
    )


def test_metadata_extraction():
    meta = structure._metadata(_COVER, _COVER + _BODY)
    assert meta["docket_full"] == "PA99-1-000"
    assert meta["audit_period"] == "January 1, 2021 to December 31, 2022"
    assert meta["forms"] == ["1"]
    assert meta["industry"] == "electric"


def test_parse_numbered_findings_splits_title_and_summary():
    section = (
        "intro line:\n"
        "1. Alpha Topic – did A across\ntwo lines.\n"
        "2. Beta Topic – did B.\n"
    )
    items = structure._parse_numbered_findings(section)
    assert [(n, t) for n, t, _ in items] == [(1, "Alpha Topic"), (2, "Beta Topic")]
    assert items[0][2] == "did A across two lines."  # whitespace collapsed


def test_parse_recommendations_groups_by_title():
    section = (
        "Audit staff's recommendations are listed below.\n"
        "Alpha Topic\n1. Fix A.\n2. Train on A.\nBeta Topic\n3. Reclassify B.\n"
    )
    recs = structure._parse_recommendations(section, ["Alpha Topic", "Beta Topic"])
    assert [r["number"] for r in recs] == [1, 2, 3]
    assert recs[0]["group"] == "Alpha Topic"
    assert recs[2]["group"] == "Beta Topic"


def test_clean_strips_headers_and_page_numbers():
    raw = "Some Co Docket No. PA99-1-000\nReal content line\n7\n1. A numbered item"
    cleaned = structure._clean(raw, "PA99-1-000")
    assert "Docket No." not in cleaned
    assert "Real content line" in cleaned
    assert "\n7\n" not in f"\n{cleaned}\n"
    assert "1. A numbered item" in cleaned  # numbered items survive


def test_recommendations_section_is_letter_agnostic():
    # "D. Recommendations" (no Other Matter) must be found just like "E.".
    assert structure._recommendations_section(_BODY) is not None
    assert "Fix thing A" in structure._recommendations_section(_BODY)


def test_structure_report_end_to_end():
    report = structure.structure_report(_entry(), _report_text())
    assert report.finding_count == 2
    assert [f.title for f in report.findings] == ["Alpha Topic", "Beta Topic"]
    assert report.findings[0].summary.startswith("The company recorded wrong thing A")
    # recommendations linked to the right finding
    assert [r.number for r in report.findings[0].recommendations] == [1, 2]
    assert [r.number for r in report.findings[1].recommendations] == [3]
    assert report.industry == "electric"
    assert report.audit_type == "non-financial"  # PA docket
    assert report.docket_full == "PA99-1-000"


_TOC_COVER = """FEDERAL ENERGY REGULATORY COMMISSION
Docket No. FA00-0-000
March 5, 2024
The audit covered the period January 1, 2021 to December 31, 2022.
compliance with the FERC Form No. 1 reporting requirements and the Federal Power Act.
"""

# A report with NO exec-summary "Summary of Noncompliance Findings" list — findings
# are only in the TOC + body. This is the format that regressed to 0 findings.
_TOC_BODY = (
    "Some Electric Co Docket No. FA00-0-000\n"
    "IV. Findings and Recommendations ................................. 10\n"
    "1. Accounting for Lobbying Costs ................................. 10\n"
    "2. Depreciation Rates ........................................... 14\n"
    "V. Company Response ............................................. 20\n"
    "\n"
    "IV. Findings and Recommendations\n"
    "1. Accounting for Lobbying Costs\n"
    "The company improperly recorded lobbying costs in Account 426 that overstated recoverable expenses.\n"
    "Pertinent Guidance\n"
    "18 C.F.R. Part 101.\n"
    "2. Depreciation Rates\n"
    "The company used unapproved depreciation rates for several plant accounts.\n"
    "Pertinent Guidance\n"
)


def test_structure_report_toc_fallback():
    """Reports without an exec-summary findings list parse via the TOC (regression)."""
    entry = ListingEntry(
        id="2024-03-05_some-electric-co_fa00-0",
        company="Some Electric Co",
        company_raw="Some Electric Co (FA00-0)",
        docket="FA00-0",
        accession_number="20240305-0000",
        issued_date=date(2024, 3, 5),
        source_page_url="https://elibrary.ferc.gov/eLibrary/filelist?accession_number=20240305-0000",
        pdf_download_url="https://elibrary.ferc.gov/eLibraryWebAPI/api/File/DownloadPDF?accesssionNumber=20240305-0000",
        captured_at=date(2026, 2, 3),
    )
    text = ReportText(
        id=entry.id,
        accession_number=entry.accession_number,
        page_count=2,
        scanned_pages=[],
        ocr_used=False,
        pages=[
            PageText(page=1, char_count=len(_TOC_COVER), is_image_only=False, extractor="pdfplumber", text=_TOC_COVER),
            PageText(page=2, char_count=len(_TOC_BODY), is_image_only=False, extractor="pdfplumber", text=_TOC_BODY),
        ],
    )
    report = structure.structure_report(entry, text)
    assert report.finding_count == 2
    assert [f.title for f in report.findings] == ["Accounting for Lobbying Costs", "Depreciation Rates"]
    assert report.findings[0].summary.startswith("The company improperly recorded lobbying costs")
    assert report.audit_type == "financial"


@pytest.mark.parametrize(
    "rid, audit_type, min_findings, min_recs",
    [
        # The two in-scope electric reports (Form 1). Header phrasing differs
        # between them, so this guards the multi-header parsing.
        ("2025-09-18_pacific-gas-and-electric-company_fa23-8", "financial", 8, 30),
        ("2025-09-08_talen-energy_pa22-7", "non-financial", 3, 6),
    ],
)
def test_real_reports_regression(rid, audit_type, min_findings, min_recs):
    text_path = config.PROCESSED_DIR / rid / "text.json"
    if not text_path.exists():
        pytest.skip(f"{rid} not extracted locally (run: extract --electric-only --limit 2)")
    listing = json.loads(config.LISTING_PATH.read_text())
    entry = next(ListingEntry.model_validate(d) for d in listing if d["id"] == rid)
    text = ReportText.model_validate_json(text_path.read_text(encoding="utf-8"))
    report = structure.structure_report(entry, text)
    assert report.industry == "electric"
    assert report.audit_type == audit_type
    assert report.finding_count >= min_findings
    assert sum(len(f.recommendations) for f in report.findings) >= min_recs
    assert all(f.title for f in report.findings)  # every finding has a title
