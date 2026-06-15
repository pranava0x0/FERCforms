# State PUC Document Ingestion — Work in Progress

## Timeline & Current Status

**Created: 2026-06-14 21:00 UTC**  
**Last updated: 2026-06-14 22:00 UTC**  
**Status: ACTIVELY INGESTING DOCUMENTS**

---

## Phase 1: Crawl State PUC Websites ✅ COMPLETE

### Results
- **Tool**: `pipeline/state_puc_crawler.py`
- **Coverage**: All 50 states + DC (51 total)
- **Documents discovered**: 245 from 48 states (94% coverage)
- **Top sources**: WA (68), PA (38), TX (33), WV (10)

### Output
- `data/seeds/state_puc.json` — All 245 SourceSeed records
- `docs/state_puc_index.csv` — Human-readable index
- `docs/STATE_PUC_CRAWLER.md` — Full documentation

### Quality Breakdown
```
Direct PDF URLs (.pdf extension):     30 documents
Landing pages / portals:             215 documents
  ├─ Indexable (archive links):      ~50
  ├─ Navigation only (no PDFs):      ~165
```

**Key finding**: Most state PUCs don't expose PDF URLs directly in their HTML.
They use:
- Dynamic JavaScript-based docket searches
- Document portal databases
- eSignature/filing systems

---

## Phase 2: Identify High-Value PDFs ✅ COMPLETE

### Results
Created focused seed file: `data/seeds/state_puc_pdfs_only.json`

**Direct PDF sources (30 documents):**
- **Texas (20 PDFs)**: Internal audit office reports (FY2019–2026)
  - Efficiency audits, compliance audits, management reviews
  - URLs: `ftp.puc.texas.gov/public/puct-info/agency/about/audit/reports/*.pdf`
  
- **West Virginia (5 PDFs)**: Annual reports & compliance forms
  - Annual Report ILEC Line Count
  - Management Summary Report (2025)
  
- **Idaho (3 PDFs)**: Final Orders
  - `puc.idaho.gov/Fileroom/PublicFiles/LawAndOrder/*.pdf`
  
- **Montana (2 PDFs)**: Annual performance reports
  - PSC Annual Reports (FY2024, FY2025)

**Quality**: These are direct, downloadable PDFs with known URLs. Ready for extraction.

---

## Phase 3: Run Pipeline on Direct PDFs 🔄 IN PROGRESS

### Current Operation
```
Command: python3 -m pipeline.sources --seed data/seeds/state_puc_pdfs_only.json
Status: RUNNING (started ~22:00 UTC)
Expected time: 10–15 minutes
```

### What the pipeline does
1. **Fetch**: Download each PDF using cached requests
2. **Extract**: Parse pages with pdfplumber/PyMuPDF
3. **Structure**: Create `AuditReport` metadata record
4. **Output**: Write `data/processed/<id>/report.json` + cached PDF text

### Expected Outputs
```
data/processed/
├── tx_audit_001_fy2026_audit_plan/
│   ├── report.json          (metadata + extracted pages)
│   ├── pages.txt            (full text, gitignored)
│   └── pages/
│       ├── 1.txt
│       ├── 2.txt
│       └── ...
├── tx_audit_002_efficiency_audit/
├── wv_audit_001_annual_report/
└── ... (30 total)
```

**Note**: We set `parse=False` for most seeds (metadata-only). Texas audit reports are set to `parse=True` for findings extraction later.

---

## Phase 4: Enhanced Crawler for Deep Document Discovery 🚀 READY

### Tool
`pipeline/state_puc_crawler_v2.py` — Dig into state portals

**Target states** (initial focus):
- **Texas (TX)**: Extracts 20 audit PDFs from PUCT audit office portal
- **Washington (WA)**: Extracts report PDFs from UTC documents page
- **Pennsylvania (PA)**: Extracts audit/investigation PDFs from filing resources

**Why v2?**
- v1 found landing pages; v2 extracts actual PDFs from those pages
- v1 reached 245 "documents" (mostly navigation); v2 targets direct PDFs
- Reduces false positives and increases pipeline-ready seeds

**Status**: Ready to run once Phase 3 completes
```bash
python3 pipeline/state_puc_crawler_v2.py
# Outputs: data/seeds/state_puc_v2_enhanced.json
```

**Expected yield**: 50–100+ additional direct PDFs

---

## Phase 5: Findings Extraction (PLANNED)

### For Texas audit reports (high-value):
- Override `structure.py` to parse PUCT audit format
- Extract: Findings, Recommendations, Company, Date, Docket
- Mirror the FERC parser shape but adapted to state audit structure

### For other states (metadata-only first):
- Ingest as reference documents
- Cross-link with FERC audits by company + date
- Add findings extraction in a later iteration (lower priority)

---

## Key Metrics

| Metric | Value |
|--------|-------|
| States crawled | 51 (50 + DC) |
| Landing pages found | 245 |
| Direct PDFs identified | 30 |
| Documents in pipeline NOW | 30 |
| Documents queued (v2) | ~50–100 (estimated) |
| Total pipeline target | 100–150 documents |

---

## Token Cost Breakdown

| Phase | Cost | Notes |
|-------|------|-------|
| v1 Crawler (50 states) | ~60K | Inline; no harness |
| Pipeline on 30 PDFs | ~50K (in progress) | Text extraction + structuring |
| v2 Crawler | ~30K (ready) | Enhanced portal scraping |
| **Total so far** | **~140K** | Still under 200K; efficient |

**Key insight**: By right-sizing the task (direct PDFs first, landing pages later), we stay efficient. No multi-agent harness needed yet.

---

## Next Immediate Steps

1. **Wait for Phase 3 to complete** (pipeline.sources on 30 PDFs)
   - Monitor: `ps aux | grep pipeline.sources`
   - Check outputs: `ls -lh data/processed/*/report.json | wc -l`

2. **Run v2 enhanced crawler** once Phase 3 is done
   ```bash
   python3 pipeline/state_puc_crawler_v2.py
   ```

3. **Feed v2 output to pipeline** (another 50–100 PDFs)
   ```bash
   python3 -m pipeline.sources --seed data/seeds/state_puc_v2_enhanced.json
   ```

4. **Build findings extraction** for Texas audits
   - Analyze `data/processed/tx_audit_*/report.json` structure
   - Adapt FERC parser to state audit format

---

## Known Issues & Workarounds

### Issue 1: Most state PUCs use JavaScript-rendered content
**Status**: Identified but deferred  
**Workaround**: Focus on states with direct PDF URLs first (TX, WV, ID, MT)  
**Future fix**: Implement Playwright/Selenium for dynamic sites (CA, FL, etc.)

### Issue 2: Landing pages with no direct PDF links
**Status**: Identified (PA, many others)  
**Workaround**: v2 crawler extracts from portal pages; some still manual  
**Future fix**: Build state-specific database crawlers (docket APIs, eSignature systems)

### Issue 3: Document dates/metadata often in PDF, not HTML
**Status**: Expected  
**Workaround**: Extract during OCR phase  
**Action**: Set `issued_date=None` in seeds; populate during structuring

---

## Files Created This Session

```
NEW:
├── pipeline/state_puc_crawler.py          (v1 — web crawler)
├── pipeline/state_puc_crawler_v2.py       (v2 — enhanced portal scraper)
├── data/seeds/state_puc.json              (all 245 landing pages)
├── data/seeds/state_puc_pdfs_only.json    (30 direct PDFs — ready for pipeline)
├── docs/STATE_PUC_CRAWLER.md              (full documentation)
├── STATE_PUC_FINDINGS.md                  (analysis & next steps)
├── STATE_PUC_SUMMARY.txt                  (executive results)
└── STATE_PUC_INGESTION_PROGRESS.md        (this file)

GENERATED BY PIPELINE (in progress):
├── data/processed/tx_audit_001/report.json
├── data/processed/tx_audit_002/report.json
├── ... (30 total, one per direct PDF)
└── docs/data/llms.txt                     (will update with state docs)
```

---

## Estimated Timeline

```
22:00 — Phase 1 (crawl) ✅ DONE
22:30 — Phase 2 (identify PDFs) ✅ DONE
22:45 — Phase 3 (pipeline run) 🔄 IN PROGRESS (should finish ~23:15)
23:15 — Phase 4 (v2 crawler) ⏳ READY
23:45 — Phase 4 output to pipeline ⏳ QUEUED
00:30 — Phase 5 preparation ⏳ PLANNED
```

**Total effort**: ~2 hours end-to-end (from crawler to findings-ready documents)

---

## Success Criteria (Next Session)

- [ ] Phase 3 completes: 30 PDFs processed, `report.json` created for each
- [ ] Phase 4 runs: v2 crawler yields 50+ additional PDFs
- [ ] Phase 5 starts: Texas audit reports parsed into findings structure
- [ ] Findings extracted: 10+ findings from at least 2 audit reports
- [ ] Cross-index: Link state findings to corresponding FERC audits by company

---

**Checkpoint**: @22:00 UTC — System operational, ingesting documents in real-time.
