"""Pydantic schemas for pipeline data.

`extra="forbid"` everywhere so a stray/renamed field fails fast at the boundary
instead of silently corrupting the dataset (see CLAUDE.md → Testing & validation).
Report/Finding/Recommendation models are added in the structuring stage; this
module currently defines the listing seed.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ListingEntry(BaseModel):
    """One audit report as listed on ferc.gov/audits — the pipeline's seed.

    Each report links to eLibrary by `accession_number`; the report's issue
    date is embedded in that accession (YYYYMMDD-####).
    """

    model_config = ConfigDict(extra="forbid")

    id: str                       # readable stable slug (date_company_docket)
    company: str                  # display name (anchor text, sans docket)
    company_raw: str              # verbatim anchor text (provenance)
    docket: Optional[str] = None  # e.g. "PA21-2"
    accession_number: str         # unique eLibrary key, e.g. "20250410-3014"
    issued_date: Optional[date] = None  # derived from the accession number
    source_page_url: str          # eLibrary filelist URL (human-facing)
    pdf_download_url: str          # eLibraryWebAPI DownloadPDF URL (machine)
    captured_at: date             # when the listing snapshot was captured
    # Provenance note (see CLAUDE.md → Data handling). Every record states the
    # ferc.gov source it was found on; only ferc.gov-origin documents are ingested.
    source_note: str = ""         # human-readable, e.g. "Listed on ferc.gov/audits (captured 2026-02-03)"
    archived_via: Optional[str] = None  # Internet Archive Wayback snapshot URL when not sourced live


class PageText(BaseModel):
    """Extracted text for a single PDF page."""

    model_config = ConfigDict(extra="forbid")

    page: int            # 1-based page number
    char_count: int
    is_image_only: bool  # True when no extractor cleared the text threshold
    extractor: str       # "pdfplumber" | "pymupdf" | "none"
    text: str


class ReportText(BaseModel):
    """Per-page extraction output for one report (data/processed/<id>/text.json)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    accession_number: str
    page_count: int
    scanned_pages: list[int]   # 1-based pages flagged image-only
    ocr_used: bool             # whether OCR filled any page (v1: always False)
    pages: list[PageText]


class Recommendation(BaseModel):
    """A staff recommendation for corrective action (verbatim)."""

    model_config = ConfigDict(extra="forbid")

    number: int
    text: str


class Finding(BaseModel):
    """One area of noncompliance from the Executive Summary (verbatim)."""

    model_config = ConfigDict(extra="forbid")

    index: int                 # order within the report (1-based)
    title: str                 # e.g. "Tariff Administration and Oversight"
    summary: Optional[str] = None  # verbatim noncompliance description
    is_other_matter: bool = False  # True for "Other Matter" items vs noncompliance
    recommendations: list[Recommendation] = Field(default_factory=list)


class AuditReport(BaseModel):
    """A structured FERC audit report (data/processed/<id>/report.json)."""

    model_config = ConfigDict(extra="forbid")

    # Which collection / tab this record belongs to. Defaults keep the original
    # FERC audit corpus valid without rewriting 120 committed report.json files.
    #   "ferc_audit"      — FERC Office of Enforcement audit reports (Form 1/2/6)
    #   "prudence_review" — FERC rate-case prudence determinations (metadata-only)
    #   "state_audit"     — state PUC/PSC/SCC audits & prudence reviews
    collection: str = "ferc_audit"
    jurisdiction: str = "FERC"          # "FERC" | "PA" | "MI" | "VA" | "IL" | ...
    source: str = ""                    # human label, e.g. "PA PUC Bureau of Audits"
    doc_type: Optional[str] = None      # e.g. "management audit", "Commission order", "fuel reconciliation"

    # Provenance / identity (from the listing seed)
    id: str
    company: str
    company_raw: str
    docket: Optional[str] = None        # short form from the listing, e.g. "FA23-10"
    docket_full: Optional[str] = None   # full form from the PDF, e.g. "FA23-10-000"
    issued_date: Optional[date] = None
    source_page_url: str
    pdf_download_url: str
    captured_at: date
    # Provenance note carried from the listing seed (ferc.gov-origin only).
    source_note: str = ""
    archived_via: Optional[str] = None  # Wayback snapshot URL when backfilled via Internet Archive

    # Extraction stats
    page_count: int
    scanned_pages: list[int] = Field(default_factory=list)
    ocr_used: bool = False

    # Structured content
    audit_period: Optional[str] = None  # e.g. "January 1, 2020 to December 31, 2023"
    industry: Optional[str] = None      # "electric" | "gas" | "oil" | None
    audit_type: Optional[str] = None    # "financial" (FA) | "non-financial" (PA), from docket
    functions: list[str] = Field(default_factory=list)  # generation/transmission/distribution
    forms: list[str] = Field(default_factory=list)  # e.g. ["1"] for FERC Form No. 1
    finding_count: int = 0
    findings: list[Finding] = Field(default_factory=list)
    # False for metadata-only records (legal orders / testimony we deliberately do
    # NOT parse into findings — see multi-source policy). Lets the UI distinguish
    # "not machine-structured, read the source" from a genuinely finding-free audit.
    structured: bool = True


class ThemeStat(BaseModel):
    """How often a cross-report theme appears (transparent keyword tagging)."""

    model_config = ConfigDict(extra="forbid")

    theme: str
    description: str = ""          # plain-English explanation (THEME_DESCRIPTIONS)
    keywords: list[str]            # the rule's keywords (shown for transparency)
    finding_count: int            # findings matching this theme
    report_count: int             # distinct reports with >=1 matching finding
    example_titles: list[str]     # up to a few real finding titles that matched


class PatternsSummary(BaseModel):
    """Cross-report aggregates (data/processed/patterns.json)."""

    model_config = ConfigDict(extra="forbid")

    report_count: int
    finding_count: int
    other_matter_count: int
    recommendation_count: int
    by_industry: dict[str, int]
    by_year: dict[str, int]
    by_function: dict[str, int]   # reports touching each function (gen/trans/distribution)
    themes: list[ThemeStat]       # sorted by report_count desc
    top_titles: list[dict]        # [{"title": str, "count": int}], most common first
    generated_at: date
