"""Central configuration for the FERC audit-analysis pipeline.

Single source of truth for paths, source URLs, and tunable constants.
Keep this module dependency-free (no project imports) so every stage can
import it without cycles.
"""
from __future__ import annotations

from pathlib import Path

# --- Filesystem layout -------------------------------------------------------
ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"                 # downloaded PDFs (gitignored)
PROCESSED_DIR: Path = DATA_DIR / "processed"     # per-report extracted+structured
LISTING_PATH: Path = DATA_DIR / "listing.json"   # scraped audit index (seed)
DOCS_DIR: Path = ROOT / "docs"                   # GitHub Pages site root
SITE_DATA_DIR: Path = DOCS_DIR / "data"          # baked JSON the site reads

# --- FERC sources ------------------------------------------------------------
FERC_BASE: str = "https://www.ferc.gov"
AUDITS_LISTING_URL: str = f"{FERC_BASE}/audits"
# NOTE (verified 2026-05-22): HTML pages on www.ferc.gov sit behind a Cloudflare
# JS challenge and return 403 to scripts. Born-digital PDFs under
# /sites/default/files/ are NOT challenged and download with any User-Agent.
# Therefore: capture the audit *listing* via a real browser; download the PDFs
# themselves over plain HTTP.
FILES_PREFIX: str = f"{FERC_BASE}/sites/default/files/"

# Audit-report PDFs live in eLibrary, behind an F5 WAF (see DATA_STRUCTURE §5.1):
# GET a filelist page to seed the session cookie, then POST DownloadPDF. The
# honest bot User-Agent above works — the WAF only requires the cookie + app
# headers, not a browser UA (verified 2026-05-22).
ELIBRARY_ORIGIN: str = "https://elibrary.ferc.gov"

# --- HTTP politeness (see CLAUDE.md "Network ethics & rate limiting") ---------
USER_AGENT: str = (
    "FERC-Audit-Tool/0.1 (public-interest research; see project README) "
    "python-requests/2.32"
)
REQUEST_DELAY_SECONDS: float = 2.0     # min gap between requests to one host
REQUEST_TIMEOUT_SECONDS: int = 60
MAX_RETRIES: int = 4
BACKOFF_BASE_SECONDS: int = 10         # exponential backoff start on 429/5xx

# --- Extraction --------------------------------------------------------------
# Below this many extractable characters per page, treat the page as image-only
# (scanned) and flag the report for OCR rather than emitting blank text.
MIN_TEXT_CHARS_PER_PAGE: int = 50
