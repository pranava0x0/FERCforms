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
_CHAPTER_RE = re.compile(r"^Chapter\s+[IVXLCM]+\s*[–—-]\s*(.+)$")
_REC_LABEL_RE = re.compile(r"^[IVXLCM]+-\d+[A-Za-z]?$")
_PAGE_NO_RE = re.compile(r"^\d{1,4}$")
_PAGE_MARK_RE = re.compile(r"^-?\s*\d{1,4}\s*-?$")           # "- 8 -" footer marker
_HDR_START_RE = re.compile(r"^(Exhibit\s+I-2|Page\s+\d+\s+of\s+\d+)$", re.I)


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

        ch = _CHAPTER_RE.match(line)
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


def structure_mo_audit(
    seed: SourceSeed, pages: list[PageText], scanned_pages: list[int]
) -> AuditReport | None:
    """Build a structured AuditReport from a PA M&O audit's Exhibit I-2.

    Returns None when the report isn't M&O format (no Exhibit I-2) or yields no
    findings — the caller then falls back to metadata-only.
    """
    full_text = "\n".join(p.text for p in pages)
    chapters = parse_exhibit_i2(full_text)
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
