"""Pydantic schemas for pipeline data.

`extra="forbid"` everywhere so a stray/renamed field fails fast at the boundary
instead of silently corrupting the dataset (see CLAUDE.md → Testing & validation).
Report/Finding/Recommendation models are added in the structuring stage; this
module currently defines the listing seed.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
