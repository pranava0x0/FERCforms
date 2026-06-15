"""Enhanced state PUC crawler — dig into portals to extract actual PDF URLs.

This is a follow-up to state_puc_crawler.py that targets specific states'
document portals and extracts direct PDF links rather than landing pages.

Focus: Texas (PUCT internal audits), Washington (UTC reports), Pennsylvania,
and other high-hit states.

Usage:
    python3 -m pipeline.state_puc_crawler_v2 --state TX,WA,PA --output-pdfs
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

from pipeline.config import USER_AGENT, REQUEST_DELAY_SECONDS
from pipeline.models import SourceSeed
from pipeline.state_puc_crawler import STATE_PUCS, CrawlResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class EnhancedStatePUCParser:
    """Base parser that digs deeper into PUC portals to find actual PDFs."""

    def __init__(self, state: str):
        self.state = state
        self.puc = STATE_PUCS[state]
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _get(self, url: str, timeout: int = 30) -> Optional[str]:
        """Fetch URL with error handling."""
        try:
            resp = self.session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.warning(f"{self.state}: Failed to fetch {url}: {e}")
            return None

    def extract_pdfs_from_html(self, html: str, base_url: str) -> list[str]:
        """Extract all PDF URLs from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        pdfs = set()

        # Find all links ending in .pdf
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if ".pdf" in href.lower():
                full_url = urljoin(base_url, href)
                if full_url.endswith(".pdf") or ".pdf" in full_url.split("?")[0]:
                    pdfs.add(full_url)

        return sorted(pdfs)

    def crawl(self) -> list[SourceSeed]:
        """Override in subclass."""
        raise NotImplementedError


class TexasEnhancedParser(EnhancedStatePUCParser):
    """Deep dive into Texas PUCT audit reports."""

    def crawl(self) -> list[SourceSeed]:
        """Fetch all PUCT internal audit reports."""
        logger.info(f"TX: Extracting internal audit PDFs")
        seeds = []

        # Texas PUCT internal audit office publishes reports at this portal
        audit_base = "https://www.puc.texas.gov/agency/about/audit/"
        html = self._get(audit_base)
        if not html:
            return seeds

        # Find all PDF links on the audit page
        pdfs = self.extract_pdfs_from_html(html, audit_base)

        for i, pdf_url in enumerate(pdfs):
            # Extract title from URL
            filename = urlparse(pdf_url).path.split("/")[-1]
            title = filename.replace(".pdf", "").replace("_", " ").replace("-", " ")

            seed = SourceSeed(
                id=f"tx_audit_{i:03d}_{filename.replace('.pdf', '').lower()[:30]}",
                company="Texas PUCT Internal Audit Office",
                collection="state_audit",
                jurisdiction="TX",
                source="Texas Public Utility Commission — Internal Audit Office",
                doc_type="internal audit report",
                industry="electric",  # PUCT covers electric, gas, water, comms
                pdf_url=pdf_url,
                source_page_url=audit_base,
                issued_date=None,  # Extract from filename or PDF metadata
                docket=None,
                captured_at=date.today(),
                source_note="Texas PUCT Internal Audit Office",
                parse=True,  # These are high-value audit reports
                fetch=True,
            )
            seeds.append(seed)
            logger.info(f"TX: Found audit PDF — {title[:60]}")

        logger.info(f"TX: Extracted {len(seeds)} audit PDFs")
        return seeds


class WashingtonEnhancedParser(EnhancedStatePUCParser):
    """Deep dive into Washington UTC (Utilities and Transportation Commission)."""

    def crawl(self) -> list[SourceSeed]:
        """Fetch Washington UTC audit and report PDFs."""
        logger.info(f"WA: Extracting UTC report PDFs")
        seeds = []

        # Washington UTC publishes reports and documents
        base_urls = [
            "https://www.utc.wa.gov/",
            "https://www.utc.wa.gov/about-us/",
            "https://www.utc.wa.gov/documents-reports/",
        ]

        all_pdfs = set()
        for base_url in base_urls:
            html = self._get(base_url)
            if html:
                pdfs = self.extract_pdfs_from_html(html, base_url)
                all_pdfs.update(pdfs)
                logger.info(f"WA: Found {len(pdfs)} PDFs on {base_url.split('/')[-2]}")

        # Filter for audit/report/investigation documents
        audit_keywords = ["audit", "report", "investigation", "review", "compliance"]
        filtered_pdfs = [
            pdf for pdf in all_pdfs
            if any(kw in pdf.lower() for kw in audit_keywords)
        ]

        for i, pdf_url in enumerate(filtered_pdfs):
            filename = urlparse(pdf_url).path.split("/")[-1]
            title = filename.replace(".pdf", "").replace("_", " ")[:70]

            seed = SourceSeed(
                id=f"wa_report_{i:03d}_{filename.replace('.pdf', '').lower()[:30]}",
                company="Washington UTC",
                collection="state_audit",
                jurisdiction="WA",
                source="Washington Utilities and Transportation Commission",
                doc_type="report",
                industry=None,  # Infer from PDF
                pdf_url=pdf_url,
                source_page_url="https://www.utc.wa.gov/documents-reports/",
                issued_date=None,
                docket=None,
                captured_at=date.today(),
                source_note="Washington UTC",
                parse=False,  # Metadata-only initially
                fetch=True,
            )
            seeds.append(seed)

        logger.info(f"WA: Extracted {len(filtered_pdfs)} audit/report PDFs from {len(all_pdfs)} total")
        return seeds


class PennsylvaniaEnhancedParser(EnhancedStatePUCParser):
    """Deep dive into Pennsylvania PUC audit and investigation documents."""

    def crawl(self) -> list[SourceSeed]:
        """Fetch PA PUC Bureau of Audits and investigation reports."""
        logger.info(f"PA: Extracting audit and investigation PDFs")
        seeds = []

        # PA PUC publishes audit documents
        base_urls = [
            "https://www.puc.pa.gov/filing-resources/reports/",
            "https://www.puc.pa.gov/search/document-search/",
        ]

        all_pdfs = set()
        for base_url in base_urls:
            html = self._get(base_url)
            if html:
                pdfs = self.extract_pdfs_from_html(html, base_url)
                all_pdfs.update(pdfs)

        # Filter for audit-related documents
        audit_keywords = [
            "audit", "investigation", "bureau", "prudence", "compliance", "examination"
        ]
        filtered_pdfs = [
            pdf for pdf in all_pdfs
            if any(kw in pdf.lower() for kw in audit_keywords)
        ]

        for i, pdf_url in enumerate(filtered_pdfs[:50]):  # Limit to first 50
            filename = urlparse(pdf_url).path.split("/")[-1]
            title = filename.replace(".pdf", "").replace("_", " ")[:70]

            seed = SourceSeed(
                id=f"pa_audit_{i:03d}_{filename.replace('.pdf', '').lower()[:30]}",
                company="Pennsylvania PUC",
                collection="state_audit",
                jurisdiction="PA",
                source="Pennsylvania Public Utility Commission",
                doc_type="audit/investigation",
                industry=None,
                pdf_url=pdf_url,
                source_page_url="https://www.puc.pa.gov/filing-resources/reports/",
                issued_date=None,
                docket=None,
                captured_at=date.today(),
                source_note="Pennsylvania PUC",
                parse=False,
                fetch=True,
            )
            seeds.append(seed)

        logger.info(f"PA: Extracted {len(filtered_pdfs)} audit/investigation PDFs")
        return seeds


def main():
    parsers = {
        "TX": TexasEnhancedParser,
        "WA": WashingtonEnhancedParser,
        "PA": PennsylvaniaEnhancedParser,
    }

    all_seeds = []
    for state, parser_class in parsers.items():
        logger.info(f"\n=== {state} ===")
        parser = parser_class(state)
        seeds = parser.crawl()
        all_seeds.extend(seeds)

    # Save to file
    output_path = Path("data/seeds/state_puc_v2_enhanced.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to JSON-serializable format
    records = []
    from datetime import date
    for seed in all_seeds:
        record = seed.model_dump()
        if record["captured_at"] is None:
            record["captured_at"] = str(date.today())
        records.append(record)

    output_path.write_text(json.dumps(records, indent=2, default=str))
    logger.info(f"\nSaved {len(records)} enhanced seeds to {output_path}")


if __name__ == "__main__":
    main()
