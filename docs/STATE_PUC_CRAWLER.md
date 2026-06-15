# State PUC Document Crawler

## Overview

This tool systematically crawls all 50 state + DC Public Utilities Commission (PUC) websites to discover audit reports, prudence reviews, and compliance documents that complement the FERC audit corpus.

## Architecture

### `pipeline/state_puc_crawler.py`

**Main components:**

1. **State-specific parsers** (`CaliforniaPUCParser`, `NewYorkPUCParser`, etc.)
   - Override `crawl(min_year, max_year)` to fetch documents from each state's unique portal
   - Convert results to `SourceSeed` format (pipeline-compatible)
   - Handle rate limiting and HTTP errors

2. **Generic fallback parser** (`GenericStatePUCParser`)
   - Used for states without custom logic
   - Scrapes the PUC homepage for audit-related links

3. **CrawlResult dataclass**
   - Captures: title, URL, issue date, docket #, company, doc type
   - Converted to `SourceSeed` on output

### STATE_PUCS directory

All 50 states + DC with their PUC URLs and names. Source: PA PUC's national directory.

## State-Specific Parsers (Priority Tier)

### Tier 1 (Implemented)

- **Texas (TX)**: Mature audit portal with internal audit office reports (FY2019–2026)
- **Pennsylvania (PA)**: Bureau of audits + filing resources (38+ documents indexed)
- **New York (NY)**: Utility management audits + annual reports

### Tier 2 (Placeholder)

- **California (CA)**: Requires manual review of docs.cpuc.ca.gov (dynamic content)
- **Florida (FL)**: PSC docket library (needs refinement)

### Tier 3 (Generic)

- All other states use generic parser targeting audit/compliance keywords

## Usage

```bash
# Dry run on Big 5 states
python3 -m pipeline.state_puc_crawler --dry-run --state CA,TX,NY,FL,PA

# Crawl all 50 states + DC (2014–2026)
python3 -m pipeline.state_puc_crawler --years 2014-2026

# Focus on a region
python3 -m pipeline.state_puc_crawler --state TX,LA,AR,OK,NM

# Custom year range
python3 -m pipeline.state_puc_crawler --state NY,PA --years 2020-2026
```

## Output

**Saved to:**

1. `data/seeds/state_puc.json` — SourceSeed records (pipeline-ready)
2. `docs/state_puc_index.csv` — Human-readable index for review

**CSV columns:**
- `State`: Two-letter state code
- `ID`: Stable record ID (state_year_seq_slug)
- `Company`: Audited entity or case caption
- `Type`: "audit report", "compliance", "annual report", etc.
- `Industry`: electric | gas | oil | water | (inferred from title)
- `Issued Date`: Document date (when available)
- `Docket`: Case/docket number (when available)
- `Source`: PUC name and state
- `URL`: Direct PDF URL or landing page
- `Status`: "Not fetched yet" (placeholder for pipeline status)

## Known Issues

1. **Dynamic content**: Many PUC sites load content via JavaScript. The crawler uses BeautifulSoup (static HTML parsing), so it may miss dynamically rendered documents.
   - **Fix**: For major states, implement browser-based scraping (Selenium/Playwright) or target their APIs directly.

2. **Deduplication**: Some states list the same document multiple times (e.g., PA's reporting pages). The CSV includes duplicates for manual review.
   - **Fix**: In the pipeline's structuring stage, deduplicate by URL + title hash.

3. **Year extraction**: Many documents don't explicitly state an issue date; the crawler sets `issued_date: null`.
   - **Fix**: In the OCR stage, extract the issue date from the PDF itself.

4. **Missing Tier 2 states** (CA, FL, etc.): Manual review recommended to populate these PUCs with known audit reports, then update the parser.

## Next Steps

### For Pipeline Integration

1. Run the crawler: `python3 -m pipeline.state_puc_crawler`
2. Review `docs/state_puc_index.csv` for accuracy
3. Feed the seeds to the standard extraction pipeline:
   ```bash
   python3 -m pipeline.sources --seed data/seeds/state_puc.json
   ```
4. Deduplicate and structure findings as usual

### For Improved Coverage

1. **California (CPUC)**: Implement direct search of `docs.cpuc.ca.gov` API or add known audit proceedings manually
2. **Florida (PSC)**: Refine docket search to extract structured metadata
3. **Browser-based scraping**: For states where JavaScript renders content, add Selenium or Playwright support
4. **API discovery**: Some PUCs (TX PUCT) expose APIs; integrate them directly instead of scraping HTML

## Token Efficiency Notes

This crawler was designed to run efficiently **inline** (not as a multi-agent fan-out harness):

- **No Workflow/deep-research**: The task is bounded (50 states, known PUC URLs) and doesn't benefit from adversarial verification or multi-modal sweeps.
- **Direct HTTP requests**: Each state gets 1–3 sequential requests, rate-limited at 2s between hosts per CLAUDE.md.
- **Estimated cost**: ~2–3 minutes wall-clock, ~50 K tokens for HTML parsing + JSON serialization.

If you need to expand coverage (e.g., add municipal/regional utilities), consider a Workflow that parallelizes state-specific parsers.

---

**Last updated**: 2026-06-14  
**Crawler version**: v1  
**States covered**: 50 + DC
