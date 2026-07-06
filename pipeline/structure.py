"""Structure extracted report text into AuditReport (findings + recommendations).

FERC DAA audit reports share an Executive Summary with consistent subsections:
  C. Summary of Noncompliance Findings  -> numbered "N. Title - verbatim summary"
  D. Summary of Other Matter            -> same shape (non-noncompliance items)
  E. Recommendations                    -> numbered recs grouped under each title

That summary is the most consistent, quotable source, so v1 parses it (rather
than the longer, more variable detailed sections). Metadata comes from the
cover page. Findings/recommendations text is kept verbatim — never paraphrased.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Optional

from pipeline import config, forms
from pipeline.models import AuditReport, Finding, ListingEntry, Recommendation, ReportText

logger = logging.getLogger(__name__)

# The government issuer of every FERC audit in this collection. Set explicitly so
# each record names its source (parity with the state collections, which carry
# their commission name) rather than leaving AuditReport.source defaulted to "".
FERC_AUDIT_SOURCE = "FERC Office of Enforcement, Division of Audits & Accounting"

_DOCKET_FULL_RE = re.compile(r"Docket No\.?\s*([A-Z]{2}\d{2}-\d+-\d+)")
_DATE_LINE_RE = re.compile(r"(?m)^\s*([A-Z][a-z]+ \d{1,2}, \d{4})\s*$")
_AUDIT_PERIOD_RE = re.compile(r"audit covered the period\s+(.+?)\.", re.S)


def _clean(text: str, docket_full: Optional[str]) -> str:
    """Drop running headers/footers so numbered items aren't split by page breaks."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if docket_full and "Docket No." in line and docket_full in line:
            continue
        if re.fullmatch(r"\d{1,3}", s):  # standalone page number (not "1." items)
            continue
        out.append(line)
    return "\n".join(out)


def _section(full: str, start: str, ends: list[str]) -> Optional[str]:
    """Return the body after a non-TOC `start` header, up to the earliest `end`."""
    for m in re.finditer(re.escape(start), full):
        if full[m.end() : m.end() + 50].count(".") >= 4:  # dotted leader => TOC
            continue
        rest = full[m.end() :]
        positions = [rest.find(e) for e in ends if rest.find(e) != -1]
        end = m.end() + min(positions) if positions else len(full)
        return full[m.end() : end]
    return None


def _section_any(full: str, starts: list[str], ends: list[str]) -> Optional[str]:
    """Try several header phrasings; return the first that matches (FERC varies them)."""
    for start in starts:
        sec = _section(full, start, ends)
        if sec is not None:
            return sec
    return None


def _recommendations_section(full: str) -> Optional[str]:
    """Find the Exec-Summary Recommendations body, regardless of its letter prefix.

    The subsection is "E. Recommendations" or "D. Recommendations" depending on
    whether the report has an "Other Matter" section. Anchor on the standard
    intro ("Audit staff('s) recommendations ...") and exclude the later
    "...Implementation of Recommendations" heading and TOC lines.
    """
    for m in re.finditer(r"(?<!Implementation of )Recommendations\s*\n", full):
        lookahead = full[m.end() : m.end() + 60]
        if "Audit staff" not in lookahead:
            continue
        rest = full[m.end() :]
        ends = ["Compliance and Implementation", "II. Background", "II.Background"]
        positions = [rest.find(e) for e in ends if rest.find(e) != -1]
        end = m.end() + min(positions) if positions else len(full)
        return full[m.end() : end]
    return None


def _parse_numbered_findings(section: Optional[str]) -> list[tuple[int, str, Optional[str]]]:
    if not section:
        return []
    items: list[tuple[int, str, Optional[str]]] = []
    for m in re.finditer(r"(?ms)^\s*(\d+)\.\s+(.+?)(?=^\s*\d+\.\s|\Z)", section):
        number = int(m.group(1))
        body = re.sub(r"\s+", " ", m.group(2)).strip()
        parts = re.split(r"\s[–—-]\s", body, maxsplit=1)  # en/em/hyphen dash
        if len(parts) == 2:
            title, summary = parts[0].strip(), parts[1].strip()
        else:
            title, summary = body, None
        items.append((number, title, summary))
    return items


def _parse_recommendations(
    section: Optional[str], finding_titles: list[str]
) -> list[dict]:
    """Parse E. Recommendations into [{number, group, text}], grouped by finding title."""
    if not section:
        return []
    recs: list[dict] = []
    group: Optional[str] = None
    current: Optional[dict] = None
    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            continue
        is_numbered = re.match(r"^\d+\.\s", line)
        title_match = next((t for t in finding_titles if line.startswith(t)), None)
        if title_match and not is_numbered:
            if current:
                recs.append(current)
                current = None
            group = title_match
            continue
        m = re.match(r"^(\d+)\.\s+(.*)", line)
        if m:
            if current:
                recs.append(current)
            current = {"number": int(m.group(1)), "group": group, "text": m.group(2)}
        elif current:
            current["text"] += " " + line
    if current:
        recs.append(current)
    for r in recs:
        r["text"] = re.sub(r"\s+", " ", r["text"]).strip()
    return recs


def _metadata(page1: str, full: str) -> dict:
    docket_full = (m.group(1) if (m := _DOCKET_FULL_RE.search(page1)) else None)
    period = (m.group(1).strip() if (m := _AUDIT_PERIOD_RE.search(full)) else None)
    if period:
        period = re.sub(r"\s+", " ", period)
    return {
        "docket_full": docket_full,
        "audit_period": period,
        "forms": forms.detect_forms(full),
        "industry": forms.primary_industry(full),
    }


# --- TOC-based extraction (most reports expose findings only via the Table of
# Contents "Findings and Recommendations" subsection, not an exec-summary list) ---
_TOC_FR_RE = re.compile(r"Findings and Recommendations\s*\.{2,}\s*\d+")
_TOC_OM_RE = re.compile(r"Other Matter[s]?\s*\.{2,}\s*\d+")
_TOC_END_RE = re.compile(r"(?m)^\s*(?:[IVX]{1,4}\.\s|Other Matter|Appendix|Acronyms)")
_TOC_ITEM_RE = re.compile(r"(\d+)\.\s+(.+?)\s*(?:\.{3,}|\(cid:9\))\s*\d+")  # dotted leaders or tab chars (cid:9)


def _toc_titles(full: str, start_re) -> list[str]:
    """Titles from a TOC subsection's numbered, dotted-leader entries."""
    m = start_re.search(full)
    if not m:
        return []
    rest = full[m.end():]
    end = _TOC_END_RE.search(rest)
    block = re.sub(r"\s+", " ", rest[: end.start() if end else 1600])
    return [t.strip() for _n, t in _TOC_ITEM_RE.findall(block)]


def _body_summary(full: str, title: str, docket_full: Optional[str]) -> Optional[str]:
    """Best-effort verbatim opening paragraph of a finding's body section."""
    pat = re.compile(r"\s+".join(re.escape(w) for w in title.split()))
    best = None
    for m in pat.finditer(full):
        if "\n" not in full[max(0, m.start() - 6): m.start()]:
            continue  # mid-sentence mention/citation, not a heading -> skip
        if full[m.end(): m.end() + 60].count(".") >= 4:  # dotted TOC leader -> skip
            continue
        best = m  # latest line-start, non-TOC occurrence = the body heading
    if best is None:
        return None
    chunk = _clean(full[best.end(): best.end() + 1200], docket_full)
    chunk = re.split(r"Pertinent Guidance|Recommendation|Background", chunk)[0]
    chunk = re.sub(r"\s+", " ", chunk).strip()
    chunk = re.sub(r"^[\s:.–—-]+", "", chunk)  # strip leading dash/colon
    return chunk[:600].strip() or None


# --- Zero-finding recovery (ADDITIVE: only runs when the primary path finds none) ---
#
# A corpus audit found 26/120 reports parse to 0 findings. ~half are genuinely clean
# small-entity letters (correctly 0); the rest are a parser-coverage gap across the
# evolving FERC report formats 2014-2023:
#   - multi-column Executive-Summary lists that pdfplumber scrambles out of reading
#     order (PyMuPDF linearizes them — the caller re-extracts before calling here),
#   - the "Summary of Audit Findings" header wording the primary path didn't list,
#   - bulleted (•) Exec-Summary lists vs the numbered ones the primary path handles,
#   - legacy body "IV. Finding(s) and Recommendations" sections (incl. (cid:9)/tab
#     leaders) for reports whose Exec Summary only points to the body.
#
# THE VALIDATION GATE: every FERC audit states its own count ("Audit staff identified
# N areas of noncompliance"). A recovered list is accepted ONLY if its finding count
# equals that stated N — so a partial/garbled parse is rejected (the report stays 0)
# rather than emitting wrong "verbatim" text, honoring the project's quote discipline.
# This whole path is gated on the primary parse yielding 0 real findings, so the
# validated reports never reach it and their output is unchanged by construction.

_NUM_WORDS = {
    "no": 0, "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
}
# Authoritative-count phrasings, most specific first. The audit's own sentence stating
# how many noncompliance findings it raised — the gate the recovered parse must match.
# FERC varies the wording across years ("N areas of noncompliance" / "N findings of
# noncompliance" / "audit staff's N compliance findings" / "N findings and M recs").
_STATED_COUNT_RES = [
    re.compile(r"identified\s+(\w+)\s+(?:areas?|findings?)\s+of\s+non-?compliance", re.I),
    re.compile(r"found\s+(\w+)\s+(?:areas?|findings?)\s+of\s+non-?compliance", re.I),
    re.compile(r"contains\s+(\w+)\s+findings?\s+of\s+non-?compliance", re.I),
    re.compile(r"staff['’]?s?\s+(\w+)\s+compliance\s+findings?\b", re.I),  # straight or curly apostrophe
    re.compile(r"\b(\w+)\s+findings?\s+and\s+\d+\s+recommendations?", re.I),
]
# Singular phrasing ("audit staff's compliance finding is summarized") => exactly one.
_SINGLE_FINDING_RE = re.compile(r"compliance finding is summarized", re.I)


def _word_to_int(w: str) -> Optional[int]:
    w = w.lower().strip()
    if w.isdigit():
        return int(w)
    return _NUM_WORDS.get(w)


def _stated_finding_count(full: str) -> Optional[int]:
    """The number of noncompliance findings the report states it raised, or None.

    Returns 0 when the report explicitly says it found none (so a genuinely-clean
    audit is distinguishable from one we simply failed to parse)."""
    flat = re.sub(r"\s+", " ", full)
    for rx in _STATED_COUNT_RES:
        m = rx.search(flat)
        if m and (n := _word_to_int(m.group(1))) is not None:
            return n
    if _SINGLE_FINDING_RE.search(flat):
        return 1
    if re.search(r"\b(?:no|zero)\s+(?:findings?|areas?\s+of\s+non-?compliance)\b", flat, re.I):
        return 0
    if re.search(r"did not identify any (?:findings?|areas? of non-?compliance)", flat, re.I):
        return 0
    return None


# Exec-Summary findings-list headers (a superset of the primary path's, adding the
# "Summary of Audit Findings" wording used by FY2016-2018 reports).
_RECOVERY_FINDING_HEADERS = [
    "Summary of Noncompliance Findings",
    "Summary of Findings of Noncompliance",
    "Summary of Compliance Findings",
    "Summary of Audit Findings",
    "Summary of Findings",
]
# Where the findings list ends (the recommendations list / next section).
_RECOVERY_END_ANCHORS = [
    "Summary of Recommendations",
    "recommendations to remedy",
    "Summary of Other Matter",
    "II. Background",
    "Compliance and Implementation",
]


def _is_toc_tail(tail: str) -> bool:
    """A TOC entry's text is followed by a leader (dots or tab) and a page number."""
    return tail.count(".") >= 4 or bool(re.match(r"\s*(?:\(cid:9\)|\t)\s*\d", tail))


def _split_title_summary(body: str) -> tuple[str, Optional[str]]:
    body = re.sub(r"\s+", " ", body).strip()
    parts = re.split(r"\s[–—-]\s", body, maxsplit=1)  # "Title – summary"
    if len(parts) == 2:
        return parts[0].strip(), (parts[1].strip() or None)
    return body, None


def _parse_listed_specs(block: Optional[str]) -> list[tuple[str, Optional[str], bool]]:
    """Parse a numbered OR bulleted 'Title – summary' Exec-Summary list -> specs."""
    if not block:
        return []
    raw: list[str] = [m.group(2) for m in re.finditer(r"(?ms)^\s*(\d+)\.\s+(.+?)(?=^\s*\d+\.\s|\Z)", block)]
    if not raw:  # fall back to bulleted lists (• ▪ ●)
        raw = [m.group(1) for m in re.finditer(r"(?ms)^\s*[•▪●]\s+(.+?)(?=^\s*[•▪●]\s|\Z)", block)]
    specs: list[tuple[str, Optional[str], bool]] = []
    for body in raw:
        title, summary = _split_title_summary(body)
        if 3 <= len(title) <= 140:  # drop page-number noise / stray fragments
            specs.append((title, summary, False))
    return specs


def _exec_summary_specs(full: str) -> list[tuple[str, Optional[str], bool]]:
    """Recover findings from the Exec-Summary list (non-TOC header occurrence)."""
    for header in _RECOVERY_FINDING_HEADERS:
        for m in re.finditer(re.escape(header), full):
            if _is_toc_tail(full[m.end(): m.end() + 60]):
                continue  # this is the Table-of-Contents pointer, not the body list
            rest = full[m.end():]
            ends = [rest.find(e) for e in _RECOVERY_END_ANCHORS if rest.find(e) > 0]
            block = rest[: min(ends)] if ends else rest[:4000]
            specs = _parse_listed_specs(block)
            if specs:
                return specs
    return []


_BODY_FINDINGS_HEAD_RE = re.compile(r"(?m)^\s*(?:IV|V)\.\s*\n?\s*Finding[s]?\s+and\s+Recommendations\b")
_BODY_SECTION_END_RE = re.compile(r"(?m)^\s*(?:V|VI|VII)\.\s*\n?\s*(?:Other Matter|Company Response|[A-Z][a-z]+ Response|Appendix)")


def _body_section_specs(full: str) -> list[tuple[str, Optional[str], bool]]:
    """Recover findings from the body 'IV. Finding(s) and Recommendations' section.

    Each finding is 'N. Title' (number then title on the same or next line, possibly
    with a (cid:9)/tab artifact) followed by the finding body and a 'Pertinent
    Guidance' block. The body section also contains numbered *recommendations*, which
    share the number space — so we keep a numbered item only when (a) it continues the
    1, 2, 3, … finding sequence AND (b) its span contains 'Pertinent Guidance' (every
    finding cites guidance; a recommendation never does). That discriminator cleanly
    separates findings from the recommendations interleaved with them.
    """
    heads = list(_BODY_FINDINGS_HEAD_RE.finditer(full))
    if not heads:
        return []
    start = heads[-1].end()  # the body section, not the TOC entry
    rest = full[start:]
    endm = _BODY_SECTION_END_RE.search(rest)
    # No fixed length cap: a findings section can run tens of thousands of chars
    # (PacifiCorp FA16-4's spans ~100 KB). The sequential-number + Pertinent-Guidance
    # gate stops on its own once the finding sequence ends, and the caller's
    # stated-count check rejects any over-read, so reading to the next section (or to
    # end-of-text) is safe.
    block = rest[: endm.start()] if endm else rest
    if re.match(r"\s*A\.\s*Conclusion", block):  # "A. Conclusion" => genuinely no findings
        return []
    nums = list(re.finditer(r"(?m)^[ \t]*(\d+)\.[ \t]*(.*)$", block))
    specs: list[tuple[str, Optional[str], bool]] = []
    expected = 1
    for i, m in enumerate(nums):
        if int(m.group(1)) != expected:
            continue  # keep only the 1,2,3,… sequence (skips restarting rec lists)
        nxt = nums[i + 1].start() if i + 1 < len(nums) else len(block)
        span = block[m.end():nxt]
        if "Pertinent Guidance" not in span:
            continue  # a recommendation, not a finding — don't advance `expected`
        # Title: the rest of the number's line, else the next non-empty line.
        title = re.sub(r"^(?:\(cid:9\)|\t|\s)+", "", m.group(2)).strip()
        body = span
        if not title:
            nl = re.search(r"\n([^\n]+)", span)
            if nl:
                title = re.sub(r"^(?:\(cid:9\)|\t|\s)+", "", nl.group(1)).strip()
                body = span[nl.end():]
        title = re.sub(r"\s+", " ", title).strip()
        summary = re.sub(r"\s+", " ", re.split(r"Pertinent Guidance", body)[0]).strip()[:600] or None
        if 3 <= len(title) <= 140:
            specs.append((title, summary, False))
            expected += 1
    return specs


# Commission ORDERS that review a contested audit summarize the audit's findings as an
# inline enumerated list ("six areas of noncompliance: (1) …; (2) …; and (6) …"), not
# the audit-report template's sections. Titles only (the order's prose is the body).
_INLINE_LIST_RE = re.compile(
    r"(\w+)\s+areas?\s+of\s+non-?compliance:\s*(\(1\).+?)(?:\.\s+[A-Z]|\Z)", re.S
)


def _inline_list_specs(full: str) -> list[tuple[str, Optional[str], bool]]:
    """Recover findings from an inline '(1) …; (2) …' enumerated list."""
    flat = re.sub(r"\s+", " ", full)
    m = _INLINE_LIST_RE.search(flat)
    if not m:
        return []
    specs: list[tuple[str, Optional[str], bool]] = []
    # Split on the "(n)" markers; titles may themselves contain "(AFUDC)"/"(CWIP)".
    for seg in re.split(r"\(\d+\)\s*", m.group(2)):
        title = seg.strip().strip(";. ")
        title = re.sub(r"\s*;?\s*and$", "", title).strip()   # trailing "; and" connector
        title = re.sub(r"^and\s+", "", title).strip(";. ")    # leading "and"
        if 3 <= len(title) <= 140:
            specs.append((title, None, False))
    return specs


def recover_zero_finding_specs(full: str) -> list[tuple[str, Optional[str], bool]]:
    """Best-effort findings recovery, validated against the report's stated count.

    `full` should be PyMuPDF-linearized text (cleaner for multi-column layouts).
    Returns [] unless a parse exactly matches the stated noncompliance count — the
    gate that prevents shipping a partial/garbled finding list.
    """
    stated = _stated_finding_count(full)
    if not stated:  # None (unknown) or 0 (genuinely clean) -> nothing to recover
        return []
    for parse in (_exec_summary_specs, _body_section_specs, _inline_list_specs):
        specs = parse(full)
        if sum(1 for _t, _s, om in specs if not om) == stated:
            return specs
    return []


def _pymupdf_full(entry: ListingEntry) -> Optional[str]:
    """Re-extract the report PDF with PyMuPDF (linearizes multi-column text the
    primary pdfplumber pass scrambles). Returns None if the raw PDF isn't present
    (e.g. a clean checkout), so the recovery path is a no-op rather than an error."""
    from pipeline.extract import pymupdf_pages  # local import: avoids a module cycle

    for name in (f"{entry.id}.pdf", f"{entry.accession_number}.pdf"):
        pdf_path = config.RAW_DIR / name
        if pdf_path.exists():
            try:
                text = "\n".join(p.text for p in pymupdf_pages(pdf_path))
                # Strip eLibrary's per-page footer stamp so it can't bleed into a
                # finding's verbatim summary (e.g. "...within 2 Document Accession
                # #: 20180914-3005 Filed Date: 09/14/2018").
                return _ELIBRARY_STAMP_RE.sub(" ", text)
            except Exception as exc:  # noqa: BLE001 — recovery is best-effort
                logger.warning("pymupdf re-extract failed for %s: %s", entry.id, exc)
                return None
    return None


# eLibrary stamps every downloaded page with this footer; remove it before parsing.
_ELIBRARY_STAMP_RE = re.compile(r"Document Accession #:\s*\S+\s+Filed Date:\s*\d{2}/\d{2}/\d{4}")


def structure_regulatory_order(entry: ListingEntry, text: ReportText, existing_report: Optional[dict] = None) -> AuditReport:
    """State PUC orders/decisions/investigations (CT, MD, NY, OH, IL, ...).

    These are free-form legal prose, not an enumerated findings list — there is
    no structural marker to anchor on. A prior version of this function matched
    "Finding N:" / "the Commission finds..." with a blind regex and truncated at
    a fixed 500-char boundary; on real documents that produced zero usable
    findings (the boundary almost never lands on a sentence break) while still
    carrying the same "harvest garbage from unstructured prose" risk the project
    guards against elsewhere (see CLAUDE.md "loose heuristic parsers"). Metadata-
    only, matching the prudence_review default.
    """
    if existing_report:
        return AuditReport(
            **{k: v for k, v in existing_report.items() if k not in ("findings", "finding_count")},
            findings=[],
            finding_count=0,
            structured=False,
        )

    return AuditReport(
        source="State Regulatory Commission",
        id=entry.id,
        company=entry.company,
        company_raw=entry.company_raw,
        docket=entry.docket,
        docket_full=None,
        issued_date=entry.issued_date,
        source_page_url=entry.source_page_url,
        pdf_download_url=entry.pdf_download_url,
        captured_at=entry.captured_at,
        source_note=entry.source_note,
        archived_via=entry.archived_via,
        page_count=text.page_count,
        scanned_pages=text.scanned_pages,
        ocr_used=text.ocr_used,
        audit_period=None,
        industry="electric",
        audit_type=None,
        functions=[],
        forms=[],
        collection="state_audit",
        finding_count=0,
        findings=[],
        structured=False,
    )


def structure_report(entry: ListingEntry, text: ReportText) -> AuditReport:
    # Read existing report to get collection/doc_type (set by sources.py)
    existing_report_path = config.PROCESSED_DIR / entry.id / "report.json"
    existing_report = None
    if existing_report_path.exists():
        existing_report = json.loads(existing_report_path.read_text(encoding="utf-8"))

    collection = existing_report.get("collection") if existing_report else None
    doc_type = existing_report.get("doc_type") if existing_report else None

    # State document dispatch based on collection
    if collection == "state_audit":
        if doc_type:
            # PA management audits
            if "management" in doc_type.lower():
                return structure_state_pa_audit(entry, text, existing_report)
            # Regulatory orders/decisions (CT, other PUC decisions)
            elif any(word in doc_type.lower() for word in ["investigation", "decision", "order", "erra"]):
                return structure_regulatory_order(entry, text, existing_report)
            # Default: try regulatory parser for unknown formats
            else:
                logger.debug("no parser for state audit type: %s; trying regulatory order parser", doc_type)
                return structure_regulatory_order(entry, text, existing_report)
        # Fallback
        logger.debug("no doc_type for state audit: %s", entry.id)

    if collection == "state_rate_case":
        return structure_state_rate_case(entry, text, existing_report)

    # Preserve non-FERC state collections (prudence reviews, etc.)
    if collection == "prudence_review":
        logger.debug("preserving prudence_review collection for %s", entry.id)
        # Return metadata-only report to preserve source collection type
        return AuditReport(
            collection=collection, jurisdiction=existing_report.get("jurisdiction"),
            source=existing_report.get("source"), doc_type=doc_type,
            id=entry.id, company=existing_report.get("company"), company_raw=existing_report.get("company"),
            docket=None, docket_full=None, issued_date=existing_report.get("issued_date"),
            source_page_url=existing_report.get("source_page_url"),
            pdf_download_url=existing_report.get("pdf_download_url"),
            captured_at=existing_report.get("captured_at"),
            source_note=existing_report.get("source_note"),
            archived_via=existing_report.get("archived_via"),
            industry=existing_report.get("industry"),
            page_count=len(text.pages), scanned_pages=[], ocr_used=False,
            finding_count=0, findings=[], structured=False,
        )

    # FERC audit extraction (original)
    page1 = text.pages[0].text if text.pages else ""
    full_raw = "\n".join(p.text for p in text.pages)
    meta = _metadata(page1, full_raw)
    full = _clean(full_raw, meta["docket_full"])

    # Findings: prefer the exec-summary "Summary of [Noncompliance] Findings" list
    # (title + inline verbatim summary). Most reports lack it, so fall back to the
    # TOC "Findings and Recommendations" subsection + body-paragraph summaries.
    # Reports whose section is just "A. Conclusion" legitimately have 0 findings.
    #
    # COVERAGE GAP (audited 2026-05-31, mostly closed 2026-06-23): 26/120 reports
    # parsed to 0 findings. The recovery pass below (recover_zero_finding_specs)
    # closed 14 of them (+67 findings) — multi-column Exec-Summary scrambles, the
    # "Summary of Audit Findings" variant, bulleted lists, legacy body sections, and
    # order-style inline lists — leaving 12 that genuinely have none (they state so).
    # That recovery is ADDITIVE: it runs ONLY when this primary path finds 0 real
    # findings, so the validated reports never enter it and cannot regress. Don't
    # globally swap the extractor or loosen the headers here: a naive change regressed
    # the validated path before (Cleco, MISO). PDF re-extraction is itself
    # nondeterministic (see ISSUES.md 2026-06-23) — re-structure targeted ids, never
    # the whole corpus, and keep the snapshot test green.
    es_block = _section_any(
        full,
        [
            "Summary of Noncompliance Findings",
            "Summary of Findings of Noncompliance",
            "Summary of Compliance Findings",  # FY2014-2018 backfill reports use this wording
            "Summary of Findings",
        ],
        ["Summary of Other Matter", "Recommendations", "II. Background"],
    )
    es_items = _parse_numbered_findings(es_block)
    if es_items:
        specs = [(t, s, False) for _n, t, s in es_items]
        om_block = _section(full, "Summary of Other Matter", ["Recommendations", "II. Background"])
        specs += [(t, s, True) for _n, t, s in _parse_numbered_findings(om_block)]
    else:
        dk = meta["docket_full"]
        specs = [(t, _body_summary(full_raw, t, dk), False) for t in _toc_titles(full_raw, _TOC_FR_RE)]
        specs += [(t, _body_summary(full_raw, t, dk), True) for t in _toc_titles(full_raw, _TOC_OM_RE)]

    # ADDITIVE zero-finding recovery: when the primary path found no noncompliance
    # findings, the report may be a format-gap case (multi-column scramble, a header
    # variant, or a body-only list). Re-parse PyMuPDF-linearized text, gated on the
    # report's own stated count (see recover_zero_finding_specs). Reports that already
    # parsed to >=1 finding never enter this branch, so their output is unchanged.
    if not any(not om for _t, _s, om in specs):
        pm_full = _pymupdf_full(entry)
        if pm_full:
            recovered = recover_zero_finding_specs(pm_full)
            if recovered:
                # Strip the running page header ("<Company> Docket No. <full>") that
                # can bleed into a summary spanning a page break, so quotes stay clean.
                hdr = re.compile(
                    r"\s*" + re.escape(entry.company) + r"\s*Docket No\.\s*[A-Z]{2}\d{2}-\d+-\d+\s*",
                    re.I,
                ) if entry.company else None
                specs = [
                    (t, (hdr.sub(" ", s).strip() if s and hdr else s), om)
                    for t, s, om in recovered
                ]
                full = _clean(pm_full, meta["docket_full"])  # cleaner text for the recs parse too
                logger.info("%s: recovered %d finding(s) (was 0)", entry.id, len(recovered))

    titles = [t for t, _s, _o in specs]
    parsed_recs = _parse_recommendations(_recommendations_section(full), titles)

    findings: list[Finding] = []
    for idx, (title, summary, is_other) in enumerate(specs, 1):
        recs = [
            Recommendation(number=r["number"], text=r["text"])
            for r in parsed_recs
            if r["group"] == title
        ]
        findings.append(
            Finding(index=idx, title=title, summary=summary, is_other_matter=is_other, recommendations=recs)
        )

    return AuditReport(
        source=FERC_AUDIT_SOURCE,
        id=entry.id,
        company=entry.company,
        company_raw=entry.company_raw,
        docket=entry.docket,
        docket_full=meta["docket_full"],
        issued_date=entry.issued_date,
        source_page_url=entry.source_page_url,
        pdf_download_url=entry.pdf_download_url,
        captured_at=entry.captured_at,
        source_note=entry.source_note,
        archived_via=entry.archived_via,
        page_count=text.page_count,
        scanned_pages=text.scanned_pages,
        ocr_used=text.ocr_used,
        audit_period=meta["audit_period"],
        industry=meta["industry"],
        audit_type=forms.audit_type_from_docket(entry.docket),
        functions=forms.detect_functions(full_raw),
        forms=meta["forms"],
        finding_count=sum(1 for f in findings if not f.is_other_matter),
        findings=findings,
    )


def structure_state_rate_case(entry: ListingEntry, text: ReportText, existing_report: Optional[dict] = None) -> AuditReport:
    """State rate-case orders, testimony, and settlements — metadata-only.

    Rate cases are free-form legal/testimony prose with no enumerable findings
    structure (no "Exhibit I-2"-style table, no self-stated count to gate
    against). A prior version here (`_extract_rate_case_findings`, removed) grabbed
    a blind +/-100/150-char window around any "$N ... disallow/approve" or
    "settlement ... agreement" match and called it a "finding" — on real
    documents this produced mid-sentence fragments ~78% of the time (528 of the
    corpus's 1341 findings, 100% of it in the 41 affected reports) with titles
    like "Settlement: Agreement" that carry no audit signal. This is exactly the
    "loose marker-based parser harvests garbage" anti-pattern documented in
    CLAUDE.md/AGENTS.md — anchor on a structural marker or fall back to
    metadata-only; there is no structural marker in rate-case prose, so: always
    metadata-only, matching the prudence_review default.
    """
    if existing_report:
        return AuditReport(
            **{k: v for k, v in existing_report.items() if k not in ("findings", "finding_count")},
            findings=[],
            finding_count=0,
            structured=False,
        )

    # Fallback if no existing report
    return AuditReport(
        source="State Regulatory Commission",
        id=entry.id,
        company=entry.company,
        company_raw=entry.company_raw,
        docket=entry.docket,
        docket_full=None,
        issued_date=entry.issued_date,
        source_page_url=entry.source_page_url,
        pdf_download_url=entry.pdf_download_url,
        captured_at=entry.captured_at,
        source_note=entry.source_note,
        archived_via=entry.archived_via,
        page_count=text.page_count,
        scanned_pages=text.scanned_pages,
        ocr_used=text.ocr_used,
        audit_period=None,
        industry="electric",
        audit_type=None,
        functions=[],
        forms=[],
        collection="state_rate_case",
        finding_count=0,
        findings=[],
        structured=False,
    )


def structure_state_pa_audit(entry: ListingEntry, text: ReportText, existing_report: Optional[dict] = None) -> AuditReport:
    """Parse PA Public Utility Commission management & operations audits.

    PA audits structure findings via Exhibit I-3 (Summary of Recommendations):
      - Format: Chapter heading (functional area)
        followed by numbered recommendations with page/timeframe/benefits
      - Example: "III-1 Complete and retain documentation..."
                 "VI-3 Begin tracking pole attachment..."

    This parser extracts:
    - Functional areas from chapter headings as Finding titles
    - Recommendations with their number and text
    """
    full_raw = "\n".join(p.text for p in text.pages)
    full = _clean(full_raw, None)

    findings: list[Finding] = []

    # Pattern to extract chapter headings: "Chapter VI – Affiliated Interests..."
    chapter_pattern = re.compile(
        r"Chapter\s+[A-Z]{1,3}\s+(?:–|—|-)\s+([^(\n]+)",
        re.IGNORECASE
    )

    # Pattern to extract recommendation entries
    # Format: "III-1 Recommendation text... PageNum TimeFrame BenefitLevel"
    rec_pattern = re.compile(
        r"^([A-Z]{1,3})-(\d+)\s+(.+?)(?=^[A-Z]{1,3}-\d+\s|^Chapter\s|^Exhibit|Exhibit\s|$)",
        re.MULTILINE | re.DOTALL
    )

    # Find all chapters and their recommendations
    current_chapter = None
    chapter_findings = {}

    for m in chapter_pattern.finditer(full):
        current_chapter = m.group(1).strip()
        chapter_findings[current_chapter] = []

    # Extract all recommendation entries
    for m in rec_pattern.finditer(full):
        rec_code = f"{m.group(1)}-{m.group(2)}"  # e.g., "III-1"
        rec_text = m.group(3).strip()

        # Clean up the text: remove page numbers, timeframes, benefits
        # Keep only the recommendation itself
        # Pattern: text until we hit "Page" or digits or timeframe keywords
        rec_text = re.sub(r"\d+\s+(?:Month|Year|Months|Years)", "", rec_text)
        rec_text = re.sub(r"(?:Low|Medium|High)\s+(?:Benefits?|Savings?)?.*", "", rec_text)
        rec_text = re.sub(r"\$[\d,]+.*", "", rec_text)
        rec_text = re.sub(r"\s+", " ", rec_text).strip()

        # Filter out entries that are just page numbers or metadata
        if len(rec_text) > 10 and not rec_text[0].isdigit():
            # Try to assign to the correct chapter
            chapter_letter = m.group(1)  # e.g., "VI"

            # Find matching chapter
            matched_chapter = None
            for ch in chapter_findings.keys():
                if chapter_letter in ch or chapter_letter in str(full[max(0, m.start() - 500):m.start()]):
                    matched_chapter = ch
                    break

            if matched_chapter:
                chapter_findings[matched_chapter].append({
                    "number": int(m.group(2)),
                    "text": rec_text,
                    "code": rec_code
                })

    # Create Finding objects from chapters
    idx = 1
    for chapter_title, recs in chapter_findings.items():
        if recs:
            recommendations = [
                Recommendation(number=r["number"], text=r["text"])
                for r in sorted(recs, key=lambda x: x["number"])
            ]
            findings.append(
                Finding(
                    index=idx,
                    title=chapter_title,
                    summary=None,
                    is_other_matter=False,
                    recommendations=recommendations
                )
            )
            idx += 1

    if not findings:
        logger.warning("no PA audit findings extracted for %s; falling back to minimal report", entry.id)

    # Preserve metadata from existing report if available
    if existing_report:
        return AuditReport(
            **{k: v for k, v in existing_report.items() if k not in ("findings", "finding_count")},
            findings=findings,
            finding_count=len(findings),
        )

    # Fallback if no existing report
    return AuditReport(
        source="PA PUC Bureau of Audits",
        id=entry.id,
        company=entry.company,
        company_raw=entry.company_raw,
        docket=entry.docket,
        docket_full=None,
        issued_date=entry.issued_date,
        source_page_url=entry.source_page_url,
        pdf_download_url=entry.pdf_download_url,
        captured_at=entry.captured_at,
        source_note=entry.source_note,
        archived_via=entry.archived_via,
        page_count=text.page_count,
        scanned_pages=text.scanned_pages,
        ocr_used=text.ocr_used,
        audit_period=None,
        industry="electric",
        audit_type=None,
        functions=[],
        forms=[],
        collection="state_audit",
        finding_count=len(findings),
        findings=findings,
    )


def load_listing(path: Path) -> dict[str, ListingEntry]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {d["id"]: ListingEntry.model_validate(d) for d in data}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Structure extracted report text into findings")
    ap.add_argument("--listing", type=Path, default=config.LISTING_PATH)
    ap.add_argument("--limit", type=int, default=None, help="only the N most-recent reports")
    ap.add_argument(
        "--electric-only",
        action="store_true",
        help="restrict to Form 1 / electric reports (uses classification.json)",
    )
    args = ap.parse_args()

    listing = load_listing(args.listing)
    listing_ids = set(listing.keys())

    # Also include seed documents from processed directory (state audits, rate cases, etc.)
    # These have text.json but aren't in listing.json
    all_ids = set(listing_ids)
    for text_path in config.PROCESSED_DIR.glob("*/text.json"):
        rid = text_path.parent.name
        if rid not in listing_ids:
            all_ids.add(rid)

    ids = sorted(all_ids, reverse=True)  # Sort for consistent processing

    if args.electric_only:
        classification_path = config.PROCESSED_DIR / "classification.json"
        if not classification_path.exists():
            logger.error("classification.json missing — run `python -m pipeline.classify` first")
            return
        classification = json.loads(classification_path.read_text(encoding="utf-8"))
        electric = {rid for rid, c in classification.items() if c.get("industry") == "electric"}
        ids = [rid for rid in ids if rid in electric]

    if args.limit is not None:
        ids = ids[: args.limit]

    ok = 0
    for rid in ids:
        text_path = config.PROCESSED_DIR / rid / "text.json"
        if not text_path.exists():
            logger.warning("no extracted text for %s (run extract first)", rid)
            continue
        try:
            text = ReportText.model_validate_json(text_path.read_text(encoding="utf-8"))
            # For seed documents not in listing, load from their report.json
            entry = listing.get(rid)
            if not entry:
                report_path = config.PROCESSED_DIR / rid / "report.json"
                if report_path.exists():
                    report_json = json.loads(report_path.read_text(encoding="utf-8"))
                    # Create entry from report fields
                    entry = ListingEntry(
                        id=rid,
                        company=report_json.get("company", ""),
                        company_raw=report_json.get("company_raw", ""),
                        accession_number=rid,
                        docket=report_json.get("docket"),
                        source_page_url=report_json.get("source_page_url", ""),
                        pdf_download_url=report_json.get("pdf_download_url", ""),
                        captured_at=report_json.get("captured_at", "2026-06-07"),
                        source_note=report_json.get("source_note", ""),
                    )
                else:
                    continue
            report = structure_report(entry, text)
            (config.PROCESSED_DIR / rid / "report.json").write_text(
                report.model_dump_json(indent=2), encoding="utf-8"
            )
            logger.info(
                "structured %s: %d findings, %d recs",
                rid,
                report.finding_count,
                sum(len(f.recommendations) for f in report.findings),
            )
            ok += 1
        except Exception as exc:  # noqa: BLE001 — one report never aborts the batch
            logger.error("structure failed for %s: %s", rid, exc)
    logger.info("structured %d report(s)", ok)


if __name__ == "__main__":
    main()
