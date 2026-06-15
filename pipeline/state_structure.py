"""Structure PA PUC Management & Operations (M&O) audits into findings.

FERC audits are parsed by `pipeline/structure.py`; state PUC documents are
ingested metadata-only by `pipeline/sources.py`. This module is the first
exception: PA Bureau of Audits **M&O audits** carry an **Exhibit I-2 "Summary
of Recommendations"** — a clean, enumerated table that linearizes (via the PDF
text extractor) as:

    Chapter III – Executive Management and Organizational Structure   <- functional area
    III-1                                                             <- rec label
    <verbatim recommendation text, 1-4 wrapped lines>
    16            <- page no.  (a standalone integer ends the rec text)
    0-6 Months    <- initiation time frame  )  trailing columns,
    Medium        <- benefits               )  discarded
    ...
    Chapter IV – Corporate Governance
    None                                                             <- area with no recs

So we map, **verbatim, no LLM**:
  - one `Finding` per chapter that has >=1 recommendation (title = functional area),
  - one `Recommendation` per `{ROMAN}-{N}` row (text verbatim, page/timeframe/benefit
    columns stripped), numbered sequentially across the report.

Chapters whose entry is "None" are genuinely clean areas -> no finding. Only the
M&O format (Exhibit I-2) is handled here; PA focused audits / MEI and MI consultant
reports stay metadata-only until their formats are added (see BACKLOG.md). The
caller falls back to metadata-only when this yields zero findings, so a parser miss
never emits a broken structured record.
"""
from __future__ import annotations

import logging
import re

from pipeline.models import AuditReport, Finding, PageText, Recommendation, SourceSeed

logger = logging.getLogger(__name__)

# Table column header (standalone lines) that opens the Exhibit I-2 data; the
# prose "E. Recommendation Summary" mentions "INITIATION TIME FRAME"/"BENEFITS"
# inline, so anchoring on the two as *consecutive* lines hits the real table.
_TABLE_HEADER_RE = re.compile(r"Time\s*Frame\s*\n\s*Benefits\s*\n")
# Functional-area / chapter heading. Two real PA M&O layouts:
#   "Chapter III – Executive Management…"  (PPL/PGW/FirstEnergy/PECO), and
#   "III Executive Management…"            (National Fuel Gas — no "Chapter", no dash).
# The second form requires a capital-letter title start so it can't match a rec
# label ("IV – 1" → after the Roman comes "– 1", not a letter) or stray numerics.
_CHAPTER_RE = re.compile(r"^Chapter\s+[IVXLCM]+\s*[–—-]\s*(.+)$")
_CHAPTER_NODASH_RE = re.compile(r"^[IVXLCM]+\s+([A-Z][A-Za-z].+)$")
# Recommendation label: "IV-1" (PECO etc.) or "IV – 1" (NFG — spaces + en/em dash).
_REC_LABEL_RE = re.compile(r"^[IVXLCM]+\s*[–—-]\s*\d+[A-Za-z]?$|^[IVXLCM]+-\d+[A-Za-z]?$")
_PAGE_NO_RE = re.compile(r"^\d{1,4}$")
_PAGE_MARK_RE = re.compile(r"^-?\s*\d{1,4}\s*-?$")           # "- 8 -" footer marker
# Page-break header to skip mid-table. The exhibit number varies by report (I-2 for
# PECO, I-3 for NFG whose I-2 is the Quantifiable Savings Summary), so match any I-N.
_HDR_START_RE = re.compile(r"^(Exhibit\s+I-\d+|Page\s+\d+\s+of\s+\d+)$", re.I)


def parse_exhibit_i2(full_text: str) -> list[tuple[str, list[str]]]:
    """Parse the Exhibit I-2 'Summary of Recommendations' table.

    Returns chapters in document order as
    (functional_area_title, [(verbatim_rec, source_page | None), ...]); source_page is
    the printed body page from the table's "Page No." column. Empty list if the exhibit
    isn't present (not an M&O-format report).
    """
    m = _TABLE_HEADER_RE.search(full_text)
    if not m:
        return []
    rest = full_text[m.end():]
    end = rest.find("BACKGROUND")              # next major section after the exec-summary exhibits
    block = rest[: end if end != -1 else 8000]
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]

    chapters: list[tuple[str, list[tuple[str, "int | None"]]]] = []
    rec_parts: list[str] = []
    collecting = False  # True while accumulating a rec's wrapped text (before the page-no column)

    def flush_rec(page: "int | None" = None) -> None:
        nonlocal rec_parts, collecting
        if rec_parts and chapters:
            text = re.sub(r"\s+", " ", " ".join(rec_parts)).strip()
            if text:
                chapters[-1][1].append((text, page))
        rec_parts = []
        collecting = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip a repeated page-break header run (Exhibit I-2 / Page N of N ... Benefits)
        # WITHOUT flushing: a recommendation's wrapped text can split across the
        # page break, so preserve the in-progress rec and keep collecting after it.
        if _HDR_START_RE.match(line):
            while i < len(lines) and lines[i] != "Benefits":
                i += 1
            i += 1  # step past "Benefits"
            continue

        ch = _CHAPTER_RE.match(line) or _CHAPTER_NODASH_RE.match(line)
        if ch:
            flush_rec()
            chapters.append((re.sub(r"\s+", " ", ch.group(1)).strip(), []))
            i += 1
            continue

        if line == "None":
            flush_rec()
            i += 1
            continue

        if _REC_LABEL_RE.match(line):
            flush_rec()
            collecting = True
            i += 1
            continue

        if collecting:
            if _PAGE_NO_RE.match(line):   # the "Page No." column ends the rec text — capture it
                flush_rec(int(line))      # (timeframe/benefit columns that follow are discarded)
            else:
                rec_parts.append(line)
            i += 1
            continue

        i += 1  # trailing timeframe/benefit columns, footers, stray lines between recs

    flush_rec()
    return chapters


# --- Overland Consulting affiliate/management audits (e.g. NJ BPU PSE&G) -----------
# These carry a consolidated "Overland Consulting - Comprehensive Listing of All
# Recommendations" (Attachment 1-1). The text extractor linearizes each row as:
#     Recommendation 15.3            <- {chapter}.{item} label
#     <verbatim recommendation text, 1-N wrapped lines, ends with a period>
#     Accounting and Property Records  <- the row's "Chapter" column value (title-case,
#                                          no terminal punctuation), then the next label.
# So per row the chapter title trails the text. We map, verbatim and no-LLM, one
# Finding per consecutive run of the same chapter title. (Liberty Consulting audits —
# JCP&L/ACE/NJNG/MI — have NO such consolidated list, only prose "We recommend …"
# embedded in chapters, so they stay metadata-only — forcing a parse would garble.)
_OVERLAND_ANCHOR = "Comprehensive Listing of All Recommendations"
_OVERLAND_LABEL_RE = re.compile(r"^Recommendation\s+\d+\.\d+$")
_OVERLAND_SKIP_RE = re.compile(r"^(Public Version|Public Service|Overland Consulting|Attachment\b|©|\d+$)")


def _looks_like_chapter(line: str) -> bool:
    """A trailing 'Chapter' column value: short, title-case, no terminal sentence punctuation."""
    return bool(line) and len(line) < 60 and line[:1].isupper() and not line.rstrip().endswith((".", ":", ";", ")"))


def parse_overland_recommendations(full_text: str) -> list[tuple[str, list[tuple[str, "int | None"]]]]:
    """Parse the Overland 'Comprehensive Listing of All Recommendations'. Returns
    chapters in document order as (chapter_title, [(verbatim_rec, None), ...]); empty
    if the listing isn't present (not an Overland-format report). source_page is None —
    the listing's N.M numbers are chapter.item, not body page numbers."""
    idx = full_text.find(_OVERLAND_ANCHOR)
    if idx == -1:
        return []
    lines = [ln.strip() for ln in full_text[idx:].splitlines() if ln.strip()]
    lines = [ln for ln in lines if ln not in ("Recommendation", "Chapter") and not _OVERLAND_SKIP_RE.match(ln)]

    # 1) Split into (text-lines) buffers per Recommendation N.M label.
    raw: list[list[str]] = []
    cur: list[str] | None = None
    for ln in lines:
        if _OVERLAND_LABEL_RE.match(ln):
            if cur is not None:
                raw.append(cur)
            cur = []
        elif cur is not None:
            cur.append(ln)
    if cur is not None:
        raw.append(cur)

    # 2) Per row, peel the trailing chapter-title line(s) off the verbatim text.
    rows: list[tuple[str, str]] = []  # (chapter_title, rec_text)
    for buf in raw:
        chap: list[str] = []
        while buf and _looks_like_chapter(buf[-1]):
            chap.insert(0, buf.pop())
        text = re.sub(r"\s+", " ", " ".join(buf)).strip()
        if text:
            rows.append((re.sub(r"\s+", " ", " ".join(chap)).strip() or "Recommendations", text))

    # 3) Group consecutive rows sharing a chapter title into one Finding.
    chapters: list[tuple[str, list[tuple[str, "int | None"]]]] = []
    for title, text in rows:
        if not chapters or chapters[-1][0] != title:
            chapters.append((title, []))
        chapters[-1][1].append((text, None))
    return chapters


def structure_mo_audit(
    seed: SourceSeed, pages: list[PageText], scanned_pages: list[int]
) -> AuditReport | None:
    """Build a structured AuditReport from a state management/operations audit.

    Tries the PA Bureau of Audits Exhibit I-2 table first, then the Overland
    Consulting "Comprehensive Listing of All Recommendations". Returns None when
    neither format is present or neither yields findings — the caller then falls
    back to metadata-only (so a non-matching report never emits a broken record).
    """
    full_text = "\n".join(p.text for p in pages)
    chapters = parse_exhibit_i2(full_text)
    with_recs = [(title, recs) for title, recs in chapters if recs]
    if not with_recs:
        chapters = parse_overland_recommendations(full_text)
        with_recs = [(title, recs) for title, recs in chapters if recs]
    if not with_recs:
        return None

    findings: list[Finding] = []
    rec_no = 0
    for idx, (title, recs) in enumerate(with_recs, 1):
        rec_models = []
        for text, page in recs:
            rec_no += 1
            rec_models.append(Recommendation(number=rec_no, text=text, source_page=page))
        findings.append(Finding(index=idx, title=title, summary=None, recommendations=rec_models))

    return AuditReport(
        collection=seed.collection,
        jurisdiction=seed.jurisdiction,
        source=seed.source,
        doc_type=seed.doc_type,
        id=seed.id,
        company=seed.company,
        company_raw=seed.company,
        docket=seed.docket,
        docket_full=None,
        issued_date=seed.issued_date,
        source_page_url=seed.source_page_url,
        pdf_download_url=seed.pdf_url,
        captured_at=seed.captured_at,
        source_note=seed.source_note,
        archived_via=seed.archived_via,
        industry=seed.industry,
        page_count=len(pages),
        scanned_pages=scanned_pages,
        ocr_used=False,
        finding_count=len(findings),
        findings=findings,
        structured=True,
    )


# --- Texas PUC Internal Audits ----
# TX internal audits published by the PUC's Internal Audit Division use a consistent
# "Detailed Results" section with numbered findings (either "Chapter N" or "Observation N").
# Each finding has a title (headline) and descriptive paragraphs. We map, verbatim:
#   - one Finding per Chapter/Observation (title = headline, summary = description)
#   - no separate Recommendations (TX format puts action items in the description)
_TX_CHAPTER_RE = re.compile(r"^Chapter\s+(\d+)\s*$")
_TX_OBSERVATION_RE = re.compile(r"^Observation\s+(\d+)\s*$")
_TX_DETAILED_RESULTS_RE = re.compile(r"Detailed Results")


def parse_tx_findings(full_text: str) -> list[tuple[str, str]]:
    """Parse Texas PUC audit findings from Detailed Results section.

    Returns a list of (title, description) tuples. Scans for "Detailed Results"
    anchor, then extracts numbered findings (Chapter N or Observation N format).
    """
    idx = full_text.find("Detailed Results")
    if idx == -1:
        return []

    # Extract from Detailed Results to Appendix/end
    rest = full_text[idx:]
    end = max(
        rest.find("Appendix") if rest.find("Appendix") != -1 else 999999,
        rest.find("Project Information") if rest.find("Project Information") != -1 else 999999,
    )
    block = rest[: min(end, len(rest))]

    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]

    findings: list[tuple[str, str]] = []
    current_title = ""
    current_desc_lines: list[str] = []

    for line in lines:
        # Check for chapter or observation header
        ch = _TX_CHAPTER_RE.match(line)
        obs = _TX_OBSERVATION_RE.match(line)

        if ch or obs:
            # Flush previous finding
            if current_title:
                desc = re.sub(r"\s+", " ", " ".join(current_desc_lines)).strip()
                if desc:
                    findings.append((current_title, desc))
            # Reset for new finding
            current_title = ""
            current_desc_lines = []
        elif current_title == "" and line and not line.startswith("Detailed Results"):
            # This is the title line for the current finding
            current_title = line
        elif current_title:
            # Accumulate description lines
            current_desc_lines.append(line)

    # Flush final finding
    if current_title:
        desc = re.sub(r"\s+", " ", " ".join(current_desc_lines)).strip()
        if desc:
            findings.append((current_title, desc))

    return findings


def structure_tx_audit(
    seed: SourceSeed, pages: list[PageText], scanned_pages: list[int]
) -> AuditReport | None:
    """Build a structured AuditReport from a Texas PUC internal audit.

    Extracts findings from the "Detailed Results" section. Returns None if no
    findings are found (metadata-only fallback).
    """
    full_text = "\n".join(p.text for p in pages)
    findings_data = parse_tx_findings(full_text)

    if not findings_data:
        return None

    findings: list[Finding] = []
    for idx, (title, description) in enumerate(findings_data, 1):
        findings.append(Finding(index=idx, title=title, summary=description, recommendations=[]))

    return AuditReport(
        collection=seed.collection,
        jurisdiction=seed.jurisdiction,
        source=seed.source,
        doc_type=seed.doc_type,
        id=seed.id,
        company=seed.company,
        company_raw=seed.company,
        docket=seed.docket,
        docket_full=None,
        issued_date=seed.issued_date,
        source_page_url=seed.source_page_url,
        pdf_download_url=seed.pdf_url,
        captured_at=seed.captured_at,
        source_note=seed.source_note,
        archived_via=seed.archived_via,
        industry=seed.industry,
        page_count=len(pages),
        scanned_pages=scanned_pages,
        ocr_used=False,
        finding_count=len(findings),
        findings=findings,
        structured=True,
    )
