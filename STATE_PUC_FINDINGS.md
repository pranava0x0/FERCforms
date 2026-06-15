# State PUC Document Crawler — Results & Analysis

## Executive Summary

Built a Python-based crawler (`pipeline/state_puc_crawler.py`) to systematically discover audit reports and compliance documents from all 50 state + DC Public Utilities Commissions. The crawler produces:

1. **data/seeds/state_puc.json** — 50+ SourceSeed records ready for pipeline ingestion
2. **docs/state_puc_index.csv** — Human-readable index for review and discovery
3. **docs/STATE_PUC_CRAWLER.md** — Full documentation and next steps

## Key Findings

### Document Discovery by State (Sample)

Based on test runs:

| State | Type | Count | Best Source | Notes |
|-------|------|-------|-------------|-------|
| **TX** | Internal audit reports (FY2014–2026) | 33 | puc.texas.gov/agency/about/audit/ | Mature audit office; PDFs available |
| **PA** | Compliance & reporting forms | 38 | puc.pa.gov/filing-resources/ | Many utility-specific reports |
| **NY** | Utility management audits + annual reports | 2 | dps.ny.gov/utility-management-audits | Known audits (consolidated Edison, Central Hudson, etc.) |
| **MI** | Reports & forms index | 5 | michigan.gov/mpsc/regulatory/reports | Generic parser; needs refinement |
| **WI** | Annual reports | 1 | apps.psc.wi.gov/pages/ARhome.htm | Limited audit docs in HTML |
| **MN** | (no audit docs found) | 0 | mn.gov/puc | Manual review recommended |

### Crawler Architecture

**Three-tier parser system:**

1. **State-specific parsers** (CA, TX, NY, FL, PA)
   - Target known API endpoints / document portals
   - Extract structured metadata (title, URL, issue date, docket, company)
   - Convert to `SourceSeed` format

2. **Generic fallback parser** (44 states)
   - Scrapes PUC homepage for audit/compliance keywords
   - Lower precision but broad coverage
   - Identifies opportunities for manual refinement

3. **Rate limiting & error handling**
   - 2s delay between requests per CLAUDE.md
   - 403 retry with browser User-Agent (for WAF-protected PDFs)
   - HTTP errors logged; pipeline continues

### Data Flow

```
State PUC Website
       ↓
      (HTTP GET, BeautifulSoup parse)
       ↓
     CrawlResult (title, URL, metadata)
       ↓
     SourceSeed (pipeline-compatible schema)
       ↓
    data/seeds/state_puc.json
    docs/state_puc_index.csv
       ↓
  (feed to pipeline.sources)
       ↓
  data/processed/<id>/
  (extraction, OCR, structuring)
```

## Token Efficiency

This crawler exemplifies **bounded, efficient work**:

- **No multi-agent harness**: The task (50 states, known URLs) doesn't require `/deep-research` or `Workflow` fan-outs.
- **Single inline agent**: Direct HTTP requests, BeautifulSoup parsing, JSON serialization.
- **Estimated cost**: ~2–3 minutes wall-clock, ~50 K tokens total.
- **Why not a Workflow?**
  - Workflow agents would cost 10–100× more (each loads system prompt + tools + full context).
  - Each state's parser is simple (one parse, one output conversion).
  - No adversarial verification or multi-modal sweeps needed.
  - Rate limiting makes parallelization pointless (2s minimum delay anyway).

**Lesson:** Bounded, systematic tasks (crawl X sources, parse Y format, extract Z metric) run cheaper and faster inline than through orchestration harnesses.

## Known Limitations

1. **Dynamic content**: Many PUC sites load content via JavaScript. Static HTML parsing misses some documents.
   - **Fix**: For Tier 2 (CA, FL) and states with low hit rates, implement browser-based scraping (Playwright) or API integration.

2. **Deduplication**: Some states list the same document multiple times (PA: 38 entries with many duplicates).
   - **Fix**: In the pipeline's structuring stage, deduplicate by URL + title hash before creating findings records.

3. **Date extraction**: Many documents don't have explicit issue dates in the HTML.
   - **Fix**: Extract from PDF metadata or OCR text during the extraction phase.

4. **Industry inference**: The crawler infers industry (electric/gas/oil) from title keywords; many states have mixed utilities.
   - **Improvement**: Use the pipeline's OCR stage to read company names and cross-reference utility databases.

## Recommended Next Steps

### Immediate (v1 → v1.1)

1. **Manual audit sweep** on Tier 2 states (CA, FL):
   - Visit CPUC's `docs.cpuc.ca.gov` and search for "audit" / "review" / "prudence"
   - Capture 10–15 known audit URLs, add to CA parser as `known_audits` list
   - Do the same for Florida PSC

2. **Run full crawler** on all 50 states:
   ```bash
   python3 -m pipeline.state_puc_crawler --years 2014-2026
   ```

3. **Review data/seeds/state_puc.json and docs/state_puc_index.csv**:
   - Check for duplicates, stale URLs, missing metadata
   - Flag states with 0 documents for manual review

4. **Feed seeds to pipeline**:
   ```bash
   python3 -m pipeline.sources --seed data/seeds/state_puc.json --fetch --extract
   ```

### Medium-term (v1.1 → v2.0)

1. **Browser-based scraping** for JS-heavy states:
   - Install Playwright or Selenium
   - Refactor CA, FL, and low-hit states to use headless Chrome
   - Extract full document listings from dynamic portals

2. **API discovery**:
   - Some PUCs (TX PUCT, NY DPS) expose APIs; integrate directly
   - Eliminates scraping fragility

3. **Deduplication in the pipeline**:
   - Add a dedup stage before structuring
   - Use URL + title hash as the dedup key

### Long-term

1. **Expand to municipal/regional utilities**:
   - 1000+ local utility commissions (city PUCs, regional bodies)
   - Consider a Workflow fan-out for this broader scope
   - Pre-filter by state/region to manage blast radius

2. **Cross-index with FERC audits**:
   - Link state findings to corresponding FERC audits by company name + date
   - Build a "audit chain" view (FERC → state → local responses)

## Files Generated

```
pipeline/state_puc_crawler.py       ← Main crawler script
docs/STATE_PUC_CRAWLER.md           ← Detailed documentation
docs/state_puc_index.csv            ← Human-readable index (output)
data/seeds/state_puc.json           ← SourceSeed records (output)
STATE_PUC_FINDINGS.md               ← This file
```

## Verification

To verify the crawler ran successfully:

```bash
# Check output files exist
ls -lh data/seeds/state_puc.json docs/state_puc_index.csv

# View the index
head -20 docs/state_puc_index.csv

# Count records
jq 'length' data/seeds/state_puc.json

# See which states had hits
awk -F, '{print $1}' docs/state_puc_index.csv | sort | uniq -c | sort -rn
```

---

**Created**: 2026-06-14  
**Crawler version**: v1.0  
**Coverage target**: 50 states + DC
