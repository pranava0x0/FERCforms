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


# --- Zero-finding recovery (pipeline/structure.py recover_zero_finding_specs) -------
# Synthetic fixtures, one per real FERC report format the recovery handles. These run
# in any checkout (no PDF needed) and lock the parsing logic; the snapshot test below
# guards the real reports when their text.json is present.

def test_stated_finding_count_phrasings():
    f = structure._stated_finding_count
    assert f("Audit staff identified two areas of noncompliance.") == 2
    assert f("Audit staff identified two findings of noncompliance.") == 2
    assert f("Audit staff found three areas of non-compliance.") == 3
    assert f("The enclosed audit report contains one finding of noncompliance.") == 1
    assert f("Audit staff's five compliance findings are detailed below.") == 5
    assert f("Audit staff's compliance finding is summarized below.") == 1  # singular => 1
    assert f("SDG&E accepts the 11 findings and 55 recommendations.") == 11
    assert f("The audit identified no findings of noncompliance.") == 0
    assert f("A report that never states a count.") is None


def test_recover_exec_summary_numbered():
    """Modern Exec-Summary 'N. Title – summary' list (e.g. National Grid FA16-2)."""
    text = (
        "C. Summary of Compliance Findings\n"
        "Below is a summary of audit staff's findings. Audit staff identified two "
        "areas of noncompliance.\n"
        "1. Depreciation Expense – The company used improper composite depreciation\nrates.\n"
        "2. Cost Allocation Methodologies – The company did not follow its documented\nmethods.\n"
        "D. Summary of Recommendations\n"
        "Audit staff's recommendations to remedy the findings are summarized below.\n"
        "1. Recalculate depreciation.\n"
    )
    specs = structure.recover_zero_finding_specs(text)
    assert [t for t, _s, _o in specs] == ["Depreciation Expense", "Cost Allocation Methodologies"]
    assert specs[0][1].startswith("The company used improper composite depreciation")


def test_recover_exec_summary_bulleted():
    """Bulleted '• Title – summary' Exec-Summary list (e.g. WEC FA21-2)."""
    text = (
        "C. Summary of Compliance Findings\n"
        "Audit staff's compliance findings are summarized below. Audit staff found "
        "three areas of noncompliance:\n"
        "• Merger-Related Capital Expenditures – improperly accounted for capital costs.\n"
        "• Accounting for Reserves – overstated reserve balances.\n"
        "• Misclassification of Administrative Costs – booked to the wrong account.\n"
        "D. Summary of Recommendations\n"
    )
    specs = structure.recover_zero_finding_specs(text)
    assert len(specs) == 3
    assert specs[0][0] == "Merger-Related Capital Expenditures"


def test_recover_body_section_separates_findings_from_recs():
    """Body 'IV. Finding(s) and Recommendations': only the numbered items that carry a
    'Pertinent Guidance' block are findings — the interleaved numbered recommendations
    (which never cite guidance) are excluded (e.g. Entergy FA15-13, Kinder Morgan)."""
    text = (
        "The enclosed audit report contains two findings of noncompliance.\n"
        "IV. Findings and Recommendations\n"
        "1.\nMerger-Related Costs\n"
        "The company recorded merger costs in O&M accounts rather than Account 426.5.\n"
        "Pertinent Guidance\n"
        "Under Commission precedent, merger costs are nonoperational.\n"
        "Recommendation\n"
        "1. Reclassify the costs to Account 426.5.\n"
        "2. File a refund report.\n"
        "2.\nDepreciation Rates\n"
        "The company applied unapproved depreciation rates to plant accounts.\n"
        "Pertinent Guidance\n"
        "18 C.F.R. Part 101 governs depreciation.\n"
        "Recommendation\n"
        "1. Recompute depreciation.\n"
    )
    specs = structure.recover_zero_finding_specs(text)
    assert [t for t, _s, _o in specs] == ["Merger-Related Costs", "Depreciation Rates"]
    assert specs[0][1].startswith("The company recorded merger costs")


def test_recover_inline_list_order_format():
    """A Commission order summarizing an audit's findings inline (Dominion FA15-16)."""
    text = (
        "The Audit Report identified three areas of noncompliance: "
        "(1) Calculation of Allowance for Funds Used During Construction (AFUDC); "
        "(2) Allocation of Overhead Costs to Construction Work In Progress (CWIP); "
        "and (3) Accounting for Lobbying Expenses. The Audit Report made recommendations."
    )
    specs = structure.recover_zero_finding_specs(text)
    assert [t for t, _s, _o in specs] == [
        "Calculation of Allowance for Funds Used During Construction (AFUDC)",
        "Allocation of Overhead Costs to Construction Work In Progress (CWIP)",
        "Accounting for Lobbying Expenses",
    ]


def test_recover_gate_rejects_count_mismatch():
    """The stated-count gate rejects a partial parse rather than emit wrong findings."""
    text = (
        "Audit staff identified three areas of noncompliance.\n"
        "C. Summary of Compliance Findings\n"
        "1. Only One Topic – we could only parse this one.\n"
        "D. Summary of Recommendations\n"
    )
    assert structure.recover_zero_finding_specs(text) == []  # 1 parsed != 3 stated


def test_recover_returns_empty_when_genuinely_clean():
    """A report that states it found nothing recovers nothing (stays 0 — correct)."""
    assert structure.recover_zero_finding_specs("The audit identified no areas of noncompliance.") == []
    assert structure.recover_zero_finding_specs("A report with no count statement at all.") == []


_SNAPSHOT_PATH = __import__("pathlib").Path(__file__).parent / "fixtures" / "structure_snapshot_validated.json"


def test_committed_ferc_finding_counts_match_snapshot():
    """No-regression guard: every FERC audit's committed report.json finding_count must
    equal the snapshot. The snapshot is the per-report count of record — regenerate it
    deliberately (from docs/data/reports.json) only when a parser change is intended, so
    an *accidental* change to a committed report.json (e.g. a careless full re-structure,
    which can drift validated reports via PDF-extraction nondeterminism) fails loudly.
    Covers both the 94 long-validated reports and the 14 recovered 2026-06-23."""
    snapshot = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    baked = {r["id"]: r for r in json.loads((config.SITE_DATA_DIR / "reports.json").read_text(encoding="utf-8"))}
    drift = []
    for rid, expected in snapshot.items():
        got = baked.get(rid, {}).get("finding_count")
        if got != expected:
            drift.append(f"{rid}: snapshot {expected} != baked {got}")
    assert not drift, "FERC finding-count drift vs snapshot:\n" + "\n".join(drift)


def test_recovered_reports_have_expected_findings():
    """The 14 reports recovered 2026-06-23 (were 0) now carry their stated finding count.
    Reads the committed/baked corpus, so it runs in any checkout (no PDF needed)."""
    expected = {
        "2014-10-24_cargill_fa14-6": 1,
        "2015-06-04_kinder-morgan_fa14-10": 4,
        "2016-04-19_entergy-services-inc_fa15-13": 1,
        "2016-10-14_dynegy-inc_pa15-3": 1,
        "2017-08-29_pacificorp_fa16-4": 9,
        "2018-04-18_midcontinent-independent-system-operator-inc_pa16-5": 1,
        "2018-06-11_idaho-power-company_pa17-7": 10,
        "2018-08-24_kansas-city-power-light-company_pa17-4": 2,
        "2018-09-14_california-independent-system-operator-corporati_pa17-3": 5,
        "2019-11-15_national-grid-usa_fa16-2": 7,
        "2020-07-02_midamerican-energy-company_fa19-2": 1,
        "2020-07-30_san-diego-gas-electric-company_fa19-3": 11,
        "2020-12-17_dominion-energy-transmission-inc_fa15-16": 6,
        "2023-02-10_wec-business-services-llc_fa21-2": 8,
    }
    baked = {r["id"]: r for r in json.loads((config.SITE_DATA_DIR / "reports.json").read_text(encoding="utf-8"))}
    for rid, n in expected.items():
        rpt = baked.get(rid)
        assert rpt is not None, f"{rid} missing from baked corpus"
        assert rpt["finding_count"] == n, f"{rid}: expected {n} findings, got {rpt['finding_count']}"
        assert all(f["title"] for f in rpt["findings"]), f"{rid}: a finding has no title"
