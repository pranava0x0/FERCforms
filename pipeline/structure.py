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
_TOC_ITEM_RE = re.compile(r"(\d+)\.\s+(.+?)\s*\.{3,}\s*\d+")


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


def structure_report(entry: ListingEntry, text: ReportText) -> AuditReport:
    page1 = text.pages[0].text if text.pages else ""
    full_raw = "\n".join(p.text for p in text.pages)
    meta = _metadata(page1, full_raw)
    full = _clean(full_raw, meta["docket_full"])

    # Findings: prefer the exec-summary "Summary of [Noncompliance] Findings" list
    # (title + inline verbatim summary). Most reports lack it, so fall back to the
    # TOC "Findings and Recommendations" subsection + body-paragraph summaries.
    # Reports whose section is just "A. Conclusion" legitimately have 0 findings.
    #
    # KNOWN COVERAGE GAP (audited 2026-05-31): 26/120 reports (22%) yield 0
    # findings. ~half are genuinely clean small-entity letters; the rest are a
    # parser miss spanning BOTH eras — the FY2014-2018 combined "Compliance
    # Findings and Other Matter" header + `(cid:9)` tab leaders, AND ~11 live
    # 2019+ reports (e.g. SDG&E FA19-3 85pp, WEC FA21-2 65pp) whose section
    # wording this path doesn't catch. A naive header/leader extension regressed
    # the validated path (Cleco 12->1, MISO 3->7). Recovery is gated on a
    # no-regression snapshot of current finding counts — see ISSUES.md and the
    # top BACKLOG.md item before touching the dispatch below.
    es_block = _section_any(
        full,
        [
            "Summary of Noncompliance Findings",
            "Summary of Findings of Noncompliance",
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
    ids = list(listing.keys())  # listing.json is newest-first

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
            report = structure_report(listing[rid], text)
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
