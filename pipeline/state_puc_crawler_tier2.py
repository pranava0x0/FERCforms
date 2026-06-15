"""Tier 2 State PUC Crawler — Deep extraction for medium-hit states.

Targets: Washington (68), Pennsylvania (38), Maine (8), Indiana (7),
Georgia (6), DC (6) — states with content but mostly landing pages.

Focuses on extracting direct PDF links from archive/report pages rather than
accepting landing pages. Uses refined keyword filtering and recursive link
extraction.

Usage:
    python3 -m pipeline.state_puc_crawler_tier2 --state WA,PA,ME,IN,GA,DC
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from pipeline.config import USER_AGENT
from pipeline.models import SourceSeed

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s]: %(message)s")
logger = logging.getLogger(__name__)


class Tier2Parser:
    """Deep portal scraper for states with 5+ documents but mostly landing pages."""

    def __init__(self, state: str, puc_url: str):
        self.state = state
        self.puc_url = puc_url
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.visited_urls = set()
        self.found_pdfs = set()

    def _get(self, url: str, timeout: int = 30) -> Optional[str]:
        """Fetch URL with caching and error handling."""
        if url in self.visited_urls:
            return None
        self.visited_urls.add(url)

        try:
            resp = self.session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.warning(f"{self.state}: Failed to fetch {url}: {e}")
            return None

    def extract_pdfs_and_links(self, html: str, base_url: str, depth: int = 1) -> list[str]:
        """Extract PDF URLs and recursively follow report/archive links."""
        if depth > 2:  # Limit recursion depth
            return list(self.found_pdfs)

        soup = BeautifulSoup(html, "html.parser")

        # Find all PDFs
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if ".pdf" in href.lower():
                full_url = urljoin(base_url, href)
                if full_url.endswith(".pdf"):
                    self.found_pdfs.add(full_url)

        # Find and follow report/archive/audit links
        if depth < 2:
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True).lower()

                # Follow links that look like report archives
                is_report_link = any(
                    kw in text for kw in [
                        "audit", "report", "archive", "filing", "investigation",
                        "compliance", "annual", "document", "publication"
                    ]
                )

                if is_report_link and href and not href.endswith(".pdf"):
                    full_url = urljoin(base_url, href)
                    # Avoid loops and external links
                    if (self.state.lower() in full_url.lower() and
                        full_url not in self.visited_urls and
                        full_url.startswith("http")):
                        logger.debug(f"{self.state}: Following -> {text}")
                        sub_html = self._get(full_url)
                        if sub_html:
                            self.extract_pdfs_and_links(sub_html, full_url, depth + 1)

        return list(self.found_pdfs)

    def crawl(self) -> list[SourceSeed]:
        """Crawl state PUC portal and extract PDFs."""
        logger.info(f"{self.state}: Starting Tier 2 crawl")
        self.found_pdfs = set()
        self.visited_urls = set()

        html = self._get(self.puc_url)
        if not html:
            return []

        pdfs = self.extract_pdfs_and_links(html, self.puc_url)
        logger.info(f"{self.state}: Found {len(pdfs)} PDFs from {len(self.visited_urls)} pages visited")

        # Filter for audit-related documents
        audit_keywords = ["audit", "report", "investigation", "review", "compliance", "exam"]
        filtered = [
            pdf for pdf in pdfs
            if any(kw in pdf.lower() for kw in audit_keywords) or
            not any(kw in pdf.lower() for kw in ["form", "blank", "template", "guide"])
        ]

        logger.info(f"{self.state}: Filtered to {len(filtered)} audit-related PDFs")

        # Convert to SourceSeed
        seeds = []
        for i, pdf_url in enumerate(filtered[:50]):  # Limit to 50 per state
            filename = urlparse(pdf_url).path.split("/")[-1]
            title = filename.replace(".pdf", "").replace("_", " ")[:70]

            seed = SourceSeed(
                id=f"{self.state.lower()}_tier2_{i:03d}_{filename.replace('.pdf', '').lower()[:30]}",
                company=title,
                collection="state_audit",
                jurisdiction=self.state,
                source=f"State of {self.state} Utility Commission",
                doc_type="report",
                industry=None,
                pdf_url=pdf_url,
                source_page_url=self.puc_url,
                issued_date=None,
                docket=None,
                captured_at=date.today(),
                source_note=f"{self.state} PUC (Tier 2 deep scrape)",
                parse=False,
                fetch=True,
            )
            seeds.append(seed)

        return seeds


# Tier 2 state configurations
TIER2_STATES = {
    "WA": "https://www.utc.wa.gov/",
    "PA": "https://www.puc.pa.gov/",
    "ME": "https://www.maine.gov/mpuc/",
    "IN": "https://www.in.gov/iurc/",
    "GA": "https://www.psc.state.ga.us/",
    "DC": "https://www.dcpsc.org/",
}


def main():
    """Crawl all Tier 2 states."""
    all_seeds = []

    for state, url in TIER2_STATES.items():
        logger.info(f"\n=== {state} ===")
        try:
            parser = Tier2Parser(state, url)
            seeds = parser.crawl()
            all_seeds.extend(seeds)
            logger.info(f"{state}: Extracted {len(seeds)} seeds")
        except Exception as e:
            logger.error(f"{state}: Error — {e}")

    # Save output
    output_path = Path("data/seeds/state_puc_tier2_extended.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    for seed in all_seeds:
        record = seed.model_dump()
        record["captured_at"] = str(record["captured_at"])
        records.append(record)

    output_path.write_text(json.dumps(records, indent=2, default=str))
    logger.info(f"\nSaved {len(records)} Tier 2 seeds to {output_path}")

    return all_seeds


if __name__ == "__main__":
    main()
