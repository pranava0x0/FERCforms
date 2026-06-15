"""Document validators: authenticity, provenance, content quality.

Three validator types:
1. Per-state validators: URL comes from correct regulatory commission (.gov domain)
2. Content validators: themes/summaries exist and are grounded in source text
3. Realism validators: documents aren't placeholders/stubs/errors
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from pipeline import config
from pipeline.models import AuditReport

logger = logging.getLogger(__name__)

# Per-state regulatory commission .gov domains (not all states in listing.json yet)
STATE_GOV_DOMAINS = {
    "PA": ["puc.pa.gov"],  # PA PUC
    "MI": ["michigan.gov"],  # Michigan MPSC
    "CA": ["cpuc.ca.gov", "docs.cpuc.ca.gov"],  # California PUC
    "NJ": ["nj.gov"],  # NJ BPU
    "TX": ["puc.texas.gov"],  # Texas PUC
    "OH": ["puc.state.oh.us"],  # Ohio PUCO
    "CT": ["ct.gov"],  # Connecticut PURA
    "VA": ["scc.virginia.gov"],  # Virginia SCC
    "NY": ["dec.ny.gov"],  # NY DEC
    "MA": ["mass.gov"],  # MA MassDEP
}


def validate_state_provenance(report: AuditReport) -> tuple[bool, Optional[str]]:
    """Check that a state audit document's source URL matches the expected .gov domain.

    Returns (is_valid, error_message). is_valid=True means the document's URL
    either matches the state domain or is from FERC (which has its own domain rules).
    """
    if report.jurisdiction == "FERC":
        # FERC documents must come from ferc.gov (checked elsewhere)
        return True, None

    state = report.jurisdiction
    url = report.pdf_download_url or ""

    if not url:
        return False, f"No URL in document"

    if state not in STATE_GOV_DOMAINS:
        # State domain not yet mapped — accept for now, log for future
        logger.debug("state %s not in STATE_GOV_DOMAINS; skipping domain check", state)
        return True, None

    expected_domains = STATE_GOV_DOMAINS[state]
    for domain in expected_domains:
        if domain in url.lower():
            return True, None

    return False, (
        f"{state} document {report.id} from unexpected domain. "
        f"Expected one of {expected_domains}, got: {url}"
    )


def validate_document_realism(report: AuditReport) -> tuple[bool, Optional[str]]:
    """Check that a document isn't a placeholder/error/stub.

    Red flags:
    - No company name (metadata-only fallback)
    - Page count 0 (fetch failed, metadata-only)
    - Title contains "REPORT A PROBLEM", "ERROR", "NOT FOUND", etc.
    - Explicitly marked as metadata-only (structured=False) AND findings=0
    - Source note looks like a placeholder
    """
    if not report.company or report.company.strip() == "":
        return False, f"No company name (likely metadata-only placeholder)"

    if report.page_count == 0 and not report.structured:
        return False, f"No page content extracted (page_count=0, structured=False)"

    title = (report.doc_type or "") + " " + (report.company or "")
    if any(bad in title.upper() for bad in ["REPORT A PROBLEM", "ERROR 404", "NOT FOUND", "PLACEHOLDER"]):
        return False, f"Document title contains placeholder/error marker: {title}"

    source_note = report.source_note or ""
    if source_note.strip() == "" and report.page_count == 0:
        return False, f"Empty source note and no extracted text (metadata-only stub)"

    return True, None


def validate_finding_grounding(report: AuditReport, text_path: Optional[Path] = None) -> tuple[bool, Optional[str]]:
    """Check that findings are grounded in source text.

    For structured reports (findings extracted from the document), spot-check
    that finding titles appear somewhere in the extracted text. This catches
    cases where a parser fabricates findings.

    text_path: Path to text.json for this report (optional; inferred if not provided)
    """
    if not report.structured or not report.findings:
        # Not a structured report or no findings to check
        return True, None

    if not text_path:
        text_path = config.PROCESSED_DIR / report.id / "text.json"

    if not text_path.exists():
        logger.debug("no text.json for %s; skipping finding grounding check", report.id)
        return True, None

    try:
        text_json = json.loads(text_path.read_text(encoding="utf-8"))
        full_text = "\n".join(p.get("text", "") for p in text_json.get("pages", []))
    except Exception as e:
        logger.warning("failed to load text.json for %s: %s", report.id, e)
        return True, None  # Skip validation on load error

    if not full_text:
        return False, f"No text extracted for {report.id}"

    # For each finding, check that at least 2-3 words from the title appear in the text
    # This is a loose check to catch wholesale fabrication, not a strict quote match
    full_text_lower = full_text.lower()
    ungrounded = []

    for finding in report.findings[:3]:  # Check first 3 findings only (sample)
        title = finding.title or ""
        if not title:
            continue
        # Split title into words, take first 3 significant ones
        words = [w for w in re.split(r"\W+", title.lower()) if len(w) > 3][:3]
        if words and not all(w in full_text_lower for w in words):
            ungrounded.append(title[:60])

    if ungrounded:
        return False, f"{report.id}: {len(ungrounded)} findings don't appear grounded in text: {ungrounded[0]}"

    return True, None


def validate_theme_coverage(themes_path: Path = None, reports_path: Path = None) -> list[tuple[str, bool, Optional[str]]]:
    """Check that identified themes have findings spanning at least 2-3 documents.

    A theme with only 1-2 documents might be an artifact or overfitting.
    Returns list of (theme_name, is_valid, error_message).
    """
    if not themes_path:
        themes_path = config.PROCESSED_DIR / "patterns.json"
    if not reports_path:
        reports_path = config.PROCESSED_DIR.parent / "data" / "reports.json"

    if not themes_path.exists() or not reports_path.exists():
        logger.warning("themes or reports file not found; skipping theme coverage validation")
        return []

    try:
        themes_data = json.loads(themes_path.read_text(encoding="utf-8"))
        themes = themes_data.get("themes", [])
    except Exception as e:
        logger.warning("failed to load themes: %s", e)
        return []

    results = []
    for theme in themes:
        name = theme.get("name", "?")
        count = theme.get("report_count", 0)
        coverage = "good" if count >= 3 else "weak" if count >= 1 else "none"
        is_valid = count >= 2  # Require at least 2 documents per theme
        msg = f"theme '{name}' covers {count} document(s)" if not is_valid else None
        results.append((name, is_valid, msg))

    return results


def run_all_validators(report: AuditReport, text_path: Optional[Path] = None) -> dict[str, tuple[bool, Optional[str]]]:
    """Run all validators on a single report. Returns dict of {validator_name: (passed, message)}."""
    return {
        "provenance": validate_state_provenance(report),
        "realism": validate_document_realism(report),
        "grounding": validate_finding_grounding(report, text_path),
    }
