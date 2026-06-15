"""Crawl state Public Utilities Commission websites for audit/prudence documents.

This script fetches audit reports from all 50 state PUCs and produces:
1. data/seeds/state_puc.json — SourceSeed records ready to ingest
2. docs/state_puc_index.csv — human-readable index for review

State PUCs are organized differently; major states have dedicated parsers, others
fall back to generic web search. Each parser yields SourceSeed records.

Usage:
    python -m pipeline.state_puc_crawler [--dry-run] [--state CA,TX,NY] [--years 2014-2026]
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from pipeline.config import USER_AGENT, BROWSER_USER_AGENT, REQUEST_DELAY_SECONDS, ROOT, SEEDS_DIR
from pipeline.models import SourceSeed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# --- State PUC directory (from PA PUC) ----------------------------------------
STATE_PUCS = {
    "AL": {"name": "Public Service Commission", "url": "https://www.psc.state.al.us"},
    "AK": {"name": "Regulatory Commission", "url": "https://www.state.ak.us/rca"},
    "AZ": {"name": "Corporation Commission", "url": "https://www.azcc.gov"},
    "AR": {"name": "Public Service Commission", "url": "https://www.apsc.arkansas.gov"},
    "CA": {"name": "Public Utilities Commission", "url": "https://www.cpuc.ca.gov"},
    "CO": {"name": "Public Utilities Commission", "url": "https://puc.colorado.gov"},
    "CT": {"name": "Department of Public Utility Control", "url": "https://ct.gov/PURA"},
    "DE": {"name": "Public Service Commission", "url": "https://www.state.de.us/delpsc"},
    "FL": {"name": "Public Service Commission", "url": "https://www.floridapsc.com"},
    "GA": {"name": "Public Service Commission", "url": "https://www.psc.state.ga.us"},
    "HI": {"name": "Public Utilities Commission", "url": "https://puc.hawaii.gov"},
    "ID": {"name": "Public Utilities Commission", "url": "https://puc.idaho.gov"},
    "IL": {"name": "Commerce Commission", "url": "https://www.icc.illinois.gov"},
    "IN": {"name": "Utility Regulatory Commission", "url": "https://www.in.gov/iurc"},
    "IA": {"name": "State Utilities Board", "url": "https://iub.iowa.gov"},
    "KS": {"name": "Corporation Commission", "url": "https://kcc.state.ks.us"},
    "KY": {"name": "Public Service Commission", "url": "https://psc.ky.gov"},
    "LA": {"name": "Public Service Commission", "url": "https://www.lpsc.louisiana.gov"},
    "ME": {"name": "Public Utilities Commission", "url": "https://www.maine.gov/mpuc"},
    "MD": {"name": "Public Service Commission", "url": "https://www.psc.state.md.us"},
    "MA": {"name": "Department of Public Utilities", "url": "https://www.mass.gov/orgs/department-of-public-utilities"},
    "MI": {"name": "Public Service Commission", "url": "https://www.michigan.gov/mpsc"},
    "MN": {"name": "Public Utilities Commission", "url": "https://www.mn.gov/puc"},
    "MS": {"name": "Public Service Commission", "url": "https://www.psc.state.ms.us"},
    "MO": {"name": "Public Service Commission", "url": "https://www.psc.mo.gov"},
    "MT": {"name": "Public Service Commission", "url": "https://www.psc.mt.gov"},
    "NE": {"name": "Public Service Commission", "url": "https://www.psc.nebraska.gov"},
    "NV": {"name": "Public Utilities Commission", "url": "https://puc.nv.gov"},
    "NH": {"name": "Public Utilities Commission", "url": "https://www.puc.nh.gov"},
    "NJ": {"name": "Board of Public Utilities", "url": "https://www.nj.gov/bpu"},
    "NM": {"name": "Public Regulation Commission", "url": "https://www.nm-prc.org"},
    "NY": {"name": "Department of Public Service", "url": "https://dps.ny.gov"},
    "NC": {"name": "Utilities Commission", "url": "https://ncuc.net"},
    "ND": {"name": "Public Service Commission", "url": "https://www.psc.nd.gov"},
    "OH": {"name": "Public Utilities Commission", "url": "https://puc.state.oh.us"},
    "OK": {"name": "Corporation Commission", "url": "https://oklahoma.gov/occ.html"},
    "OR": {"name": "Public Utility Commission", "url": "https://www.oregon.gov/puc"},
    "PA": {"name": "Public Utility Commission", "url": "https://www.puc.pa.gov"},
    "RI": {"name": "Public Utilities Commission", "url": "https://www.ripuc.org"},
    "SC": {"name": "Public Service Commission", "url": "https://www.psc.sc.gov"},
    "SD": {"name": "Public Utilities Commission", "url": "https://www.puc.sd.gov"},
    "TN": {"name": "Regulatory Authority", "url": "https://tn.gov/tpuc.html"},
    "TX": {"name": "Public Utility Commission", "url": "https://www.puc.texas.gov"},
    "UT": {"name": "Public Utilities Division", "url": "https://dpu.utah.gov"},
    "VT": {"name": "Public Service Board", "url": "https://www.psb.vermont.gov"},
    "VA": {"name": "State Corporation Commission", "url": "https://www.scc.virginia.gov"},
    "WA": {"name": "Utilities and Transportation Commission", "url": "https://www.utc.wa.gov"},
    "WV": {"name": "Public Service Commission", "url": "https://www.psc.state.wv.us"},
    "WI": {"name": "Public Service Commission", "url": "https://www.psc.wi.gov"},
    "WY": {"name": "Public Service Commission", "url": "https://www.psc.wyo.gov"},
    "DC": {"name": "Public Service Commission", "url": "https://www.dcpsc.org"},
}


@dataclass
class CrawlResult:
    """Collected metadata from a single document."""
    state: str
    title: str
    url: str
    issued_date: Optional[date] = None
    docket: Optional[str] = None
    company: Optional[str] = None
    doc_type: Optional[str] = None
    source_page: Optional[str] = None


class StatePUCParser(ABC):
    """Base class for state-specific PUC parsers."""

    def __init__(self, state: str):
        self.state = state
        self.puc_info = STATE_PUCS[state]
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce minimum delay between requests to the same host."""
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_DELAY_SECONDS:
            time.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self.last_request_time = time.time()

    def _get(self, url: str, timeout: int = 30) -> Optional[str]:
        """Fetch a URL with rate limiting and error handling."""
        self._rate_limit()
        try:
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code == 403:
                # Retry with browser UA if first attempt was blocked
                logger.warning(f"{self.state}: 403 on {url}, retrying with browser UA")
                self.session.headers["User-Agent"] = BROWSER_USER_AGENT
                resp = self.session.get(url, timeout=timeout)
                self.session.headers["User-Agent"] = USER_AGENT
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.warning(f"{self.state}: Failed to fetch {url}: {e}")
            return None

    @abstractmethod
    def crawl(self, min_year: int, max_year: int) -> list[CrawlResult]:
        """Crawl this state's PUC for audit documents. Return list of CrawlResult."""
        pass

    def to_source_seeds(self, results: list[CrawlResult]) -> list[SourceSeed]:
        """Convert CrawlResult records to SourceSeed format."""
        seeds = []
        for i, result in enumerate(results):
            # Build stable ID: state_YYYY_shortname
            slug = result.title.lower()
            slug = re.sub(r"[^a-z0-9]+", "-", slug)[:40].strip("-")
            doc_id = f"{self.state.lower()}_{result.issued_date.year if result.issued_date else '0000'}_{i:03d}_{slug}"

            # Enable findings extraction for certain state/doc_type combinations
            should_parse = (
                (self.state == "TX" and result.doc_type and "audit" in result.doc_type.lower())
                or (self.state == "PA" and result.doc_type and "management" in result.doc_type.lower())
            )

            seed = SourceSeed(
                id=doc_id,
                company=result.company or result.title,
                collection="state_audit",
                jurisdiction=self.state,
                source=self.puc_info["name"],
                doc_type=result.doc_type,
                industry=self._infer_industry(result.title),
                pdf_url=result.url,
                source_page_url=result.source_page or self.puc_info["url"],
                issued_date=result.issued_date,
                docket=result.docket,
                captured_at=date.today(),
                source_note=f"{self.puc_info['name']} ({self.state})",
                parse=should_parse,
                fetch=True,
            )
            seeds.append(seed)
        return seeds

    @staticmethod
    def _infer_industry(text: str) -> Optional[str]:
        """Infer industry from document title."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["electric", "electricity", "generation", "transmission"]):
            return "electric"
        if any(w in text_lower for w in ["gas", "natural gas"]):
            return "gas"
        if any(w in text_lower for w in ["oil", "petroleum"]):
            return "oil"
        if any(w in text_lower for w in ["water", "wastewater"]):
            return "water"
        return None


class CaliforniaPUCParser(StatePUCParser):
    """CPUC document portal (docs.cpuc.ca.gov)."""

    def crawl(self, min_year: int, max_year: int) -> list[CrawlResult]:
        """Fetch CPUC audit reports from their document database."""
        logger.info(f"CA: Crawling CPUC document portal")
        results = []

        # CPUC publishes audit reports in their proceeding archive.
        # Note: Their document search doesn't expose a direct API; these are
        # known audit proceedings/reports. For a complete crawl, manual review
        # of https://docs.cpuc.ca.gov/ is recommended; we capture known entries here.

        # Example: CPUC published utility audit reports (manually identified from web searches)
        # These would be populated after manual review of the CPUC document portal.
        known_audits = [
            {
                "title": "CPUC: See docs.cpuc.ca.gov for audit reports",
                "url": "https://docs.cpuc.ca.gov/",
                "note": "CPUC document search requires manual navigation"
            }
        ]

        for audit in known_audits:
            results.append(CrawlResult(
                state="CA",
                title=audit["title"],
                url=audit["url"],
                source_page="https://www.cpuc.ca.gov/documents",
                doc_type="audit report",
            ))
            logger.info(f"CA: Documented source — {audit['note']}")

        return results


class NewYorkPUCParser(StatePUCParser):
    """NY DPS Utility Management Audits (dps.ny.gov)."""

    def crawl(self, min_year: int, max_year: int) -> list[CrawlResult]:
        """Fetch NY DPS utility management audits and investigation reports."""
        logger.info(f"NY: Crawling DPS Utility Management Audits")
        results = []

        # NY DPS publishes utility management audits at this page
        url = "https://dps.ny.gov/utility-management-audits"
        html = self._get(url)
        if not html:
            return results

        soup = BeautifulSoup(html, "html.parser")

        # Look for all document links (PDFs and pages)
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # Filter for audit-related content
            if not text:
                continue

            is_audit = any(w in text.lower() for w in [
                "audit", "review", "investigation", "consolidated edison",
                "central hudson", "new york state electric", "rochester gas",
                "national fuel", "orange and rockland"
            ])

            if is_audit and href:
                # Convert relative URLs to absolute
                full_url = urljoin(url, href) if not href.startswith("http") else href

                results.append(CrawlResult(
                    state="NY",
                    title=text,
                    url=full_url,
                    source_page=url,
                    doc_type="management audit",
                ))
                logger.info(f"NY: Found — {text[:60]}")

        # Also check for annual reports page
        reports_url = "https://dps.ny.gov/completed-annual-reports-regulated-utilities"
        html = self._get(reports_url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)

                if "annual report" in text.lower() and href:
                    full_url = urljoin(reports_url, href) if not href.startswith("http") else href
                    results.append(CrawlResult(
                        state="NY",
                        title=text,
                        url=full_url,
                        source_page=reports_url,
                        doc_type="annual report",
                    ))
                    logger.info(f"NY: Found annual report — {text[:60]}")

        return results


class TexasPUCParser(StatePUCParser):
    """Texas PUCT industry filings and compliance reports (puc.texas.gov)."""

    def crawl(self, min_year: int, max_year: int) -> list[CrawlResult]:
        """Search Texas PUCT for audit/compliance filings and reports."""
        logger.info(f"TX: Crawling PUCT filings and audit portal")
        results = []

        # Texas PUCT publishes audit reports and compliance documents
        # Check the industry filings section
        url = "https://www.puc.texas.gov/industry/filings/"
        html = self._get(url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)

                if any(w in text.lower() for w in ["audit", "compliance", "report", "filing"]):
                    full_url = urljoin(url, href) if not href.startswith("http") else href
                    results.append(CrawlResult(
                        state="TX",
                        title=text,
                        url=full_url,
                        source_page=url,
                        doc_type="filing/report",
                    ))
                    logger.info(f"TX: Found — {text[:60]}")

        # Also check the internal audit office page
        audit_url = "https://www.puc.texas.gov/agency/about/audit/"
        html = self._get(audit_url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)

                if any(w in text.lower() for w in ["audit", "report", "annual"]):
                    full_url = urljoin(audit_url, href) if not href.startswith("http") else href
                    if full_url.endswith(".pdf") or "audit" in full_url.lower():
                        results.append(CrawlResult(
                            state="TX",
                            title=text,
                            url=full_url,
                            source_page=audit_url,
                            doc_type="internal audit",
                        ))
                        logger.info(f"TX: Found audit — {text[:60]}")

        return results


class FloridaPSCParser(StatePUCParser):
    """Florida PSC docket and filing library (floridapsc.com)."""

    def crawl(self, min_year: int, max_year: int) -> list[CrawlResult]:
        """Search Florida PSC docket library and filings for audit documents."""
        logger.info(f"FL: Crawling PSC docket and filing library")
        results = []

        # Florida PSC publishes documents through their filing library
        urls = [
            ("https://www.floridapsc.com/library/filings/", "filing library"),
            ("https://www.floridapsc.com/clerks-office-dockets/", "dockets"),
        ]

        for url, source_type in urls:
            html = self._get(url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")

            # Look for audit and compliance-related documents
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)

                if not text or len(text) < 3:
                    continue

                is_audit = any(w in text.lower() for w in [
                    "audit", "review", "compliance", "management", "investigation",
                    "examination", "prudence"
                ])

                if is_audit:
                    full_url = urljoin(url, href) if not href.startswith("http") else href
                    results.append(CrawlResult(
                        state="FL",
                        title=text,
                        url=full_url,
                        source_page=url,
                        doc_type="audit/filing",
                    ))
                    logger.info(f"FL: Found ({source_type}) — {text[:60]}")

        return results


class PennsylvaniaPUCParser(StatePUCParser):
    """PA PUC filing resources and Bureau of Audits (puc.pa.gov)."""

    def crawl(self, min_year: int, max_year: int) -> list[CrawlResult]:
        """Search PA PUC for audit reports and filing documents."""
        logger.info(f"PA: Crawling PUC filing resources and audits")
        results = []

        urls = [
            ("https://www.puc.pa.gov/filing-resources/reports/", "reports"),
            ("https://www.puc.pa.gov/filing-resources/bureau-of-audits/", "bureau of audits"),
            ("https://www.puc.pa.gov/search/document-search/", "document search"),
        ]

        for url, section in urls:
            html = self._get(url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")

            # PA PUC publishes audit reports and investigation documents
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)

                if not text or len(text) < 3:
                    continue

                is_audit = any(w in text.lower() for w in [
                    "audit", "report", "investigation", "bureau", "prudence",
                    "examination", "compliance"
                ])

                if is_audit:
                    full_url = urljoin(url, href) if not href.startswith("http") else href

                    # Only capture PDFs and document pages
                    if full_url.endswith(".pdf") or "puc.pa.gov" in full_url:
                        results.append(CrawlResult(
                            state="PA",
                            title=text,
                            url=full_url,
                            source_page=url,
                            doc_type="audit/report",
                        ))
                        logger.info(f"PA: Found ({section}) — {text[:60]}")

        return results


class GenericStatePUCParser(StatePUCParser):
    """Fallback parser for states without custom logic."""

    def crawl(self, min_year: int, max_year: int) -> list[CrawlResult]:
        """Attempt to find audit documents on the state's PUC homepage."""
        logger.info(f"{self.state}: Using generic parser on {self.puc_info['url']}")
        results = []

        html = self._get(self.puc_info["url"])
        if not html:
            return results

        soup = BeautifulSoup(html, "html.parser")

        # Look for any links with audit-related keywords
        for link in soup.find_all("a"):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            if any(w in text.lower() for w in ["audit", "report", "investigation", "compliance"]):
                full_url = urljoin(self.puc_info["url"], href) if not href.startswith("http") else href
                if full_url:
                    results.append(CrawlResult(
                        state=self.state,
                        title=text,
                        url=full_url,
                        source_page=self.puc_info["url"],
                    ))

        if results:
            logger.info(f"{self.state}: Found {len(results)} audit-related documents")
        else:
            logger.info(f"{self.state}: No audit documents found (manual review recommended)")

        return results


def get_parser(state: str) -> StatePUCParser:
    """Factory: return state-specific parser or fallback to generic."""
    parsers = {
        "CA": CaliforniaPUCParser,
        "NY": NewYorkPUCParser,
        "TX": TexasPUCParser,
        "FL": FloridaPSCParser,
        "PA": PennsylvaniaPUCParser,
    }
    parser_class = parsers.get(state, GenericStatePUCParser)
    return parser_class(state)


def crawl_all_states(
    states: Optional[list[str]] = None,
    min_year: int = 2014,
    max_year: int = 2026,
    dry_run: bool = False,
) -> dict[str, list[SourceSeed]]:
    """Crawl all specified states' PUCs. Return dict of state → SourceSeed list."""
    if states is None:
        states = list(STATE_PUCS.keys())

    all_seeds: dict[str, list[SourceSeed]] = {}

    for state in states:
        if state not in STATE_PUCS:
            logger.warning(f"Unknown state: {state}")
            continue

        logger.info(f"=== Crawling {state} ({STATE_PUCS[state]['name']}) ===")
        parser = get_parser(state)
        results = parser.crawl(min_year, max_year)

        if results:
            seeds = parser.to_source_seeds(results)
            all_seeds[state] = seeds
            logger.info(f"{state}: {len(results)} document(s) → {len(seeds)} seed(s)")
        else:
            logger.info(f"{state}: No documents found")

        if dry_run:
            for seed in all_seeds.get(state, []):
                logger.info(f"  {seed.id}: {seed.company}")

    return all_seeds


def save_results(all_seeds: dict[str, list[SourceSeed]], output_dir: Path):
    """Save SourceSeed records to JSON and human-readable CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save as JSON (for pipeline ingestion)
    json_path = output_dir / "state_puc.json"
    all_records = []
    for state_seeds in all_seeds.values():
        all_records.extend([json.loads(s.model_dump_json()) for s in state_seeds])

    json_path.write_text(json.dumps(all_records, indent=2, default=str))
    logger.info(f"Saved {len(all_records)} seeds to {json_path}")

    # Save as CSV (for human review)
    csv_path = ROOT / "docs" / "state_puc_index.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "State", "ID", "Company", "Type", "Industry", "Issued Date", "Docket",
            "Source", "URL", "Status"
        ])
        for state, seeds in sorted(all_seeds.items()):
            for seed in seeds:
                writer.writerow([
                    seed.jurisdiction,
                    seed.id,
                    seed.company,
                    seed.doc_type or "—",
                    seed.industry or "—",
                    seed.issued_date or "—",
                    seed.docket or "—",
                    seed.source,
                    seed.pdf_url,
                    "Not fetched yet",
                ])
    logger.info(f"Saved index to {csv_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Crawl state PUC websites for audit/prudence documents."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not save output; log results only"
    )
    parser.add_argument(
        "--state",
        default=None,
        help="Comma-separated state codes (e.g., CA,TX,NY). Default: all states."
    )
    parser.add_argument(
        "--years",
        default="2014-2026",
        help="Year range (e.g., 2014-2026). Default: 2014-2026"
    )

    args = parser.parse_args()

    # Parse year range
    try:
        year_parts = args.years.split("-")
        min_year = int(year_parts[0])
        max_year = int(year_parts[1]) if len(year_parts) > 1 else min_year
    except (ValueError, IndexError):
        logger.error(f"Invalid year range: {args.years}")
        sys.exit(1)

    # Parse state list
    states = None
    if args.state:
        states = [s.strip().upper() for s in args.state.split(",")]

    logger.info(f"Starting state PUC crawl (years {min_year}–{max_year})")
    if states:
        logger.info(f"States: {', '.join(states)}")
    else:
        logger.info(f"States: all 50 + DC")

    all_seeds = crawl_all_states(states, min_year, max_year, args.dry_run)

    if not args.dry_run:
        save_results(all_seeds, SEEDS_DIR)
        logger.info("✓ Crawl complete. Ready for pipeline ingestion.")
    else:
        logger.info(f"[DRY RUN] Would have saved {sum(len(s) for s in all_seeds.values())} seeds")


if __name__ == "__main__":
    main()
