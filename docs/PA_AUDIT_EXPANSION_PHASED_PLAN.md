# PA Audit Expansion — Phased Delivery Plan

**Effort:** 2–3 hours (one session)  
**Expected yield:** 3–5 new M&O audits, ~30–100 new findings  
**Priority:** HIGH (cheap, high-confidence findings extraction)

---

## Current State

**Seeded audits:** 9 M&O + 1 MEI (all parse=True)  
**Coverage:** Major electric (PPL, PECO, FirstEnergy ×4, Duquesne) + major gas (NF Gas, Peoples, UGI, Columbia, Philadelphia GW)  
**Parser:** PA Exhibit-I-2 handler in `state_structure.py` — both known layouts (PPL/PECO and NFG variant) working, no regressions in test suite

---

## Phase 1: Audit Discovery (30 min)

### Task
Scrape PA PUC press-release archive for "management and operations audit" or "management efficiency investigation" records not yet seeded.

### Steps
1. Navigate to https://www.puc.pa.gov/press-release/ (if blocked, use Wayback Machine snapshot)
2. Filter/search for "management and operations audit" or "audit report"
3. Extract candidates (company, date, press-release URL, PDF link)
4. Cross-check against `data/seeds/pa_puc.json` (deduplicate by URL)
5. Identify 3–5 new utilities with recent audits

### Success Criteria
- ✓ Found 3+ audits not yet seeded
- ✓ All URLs are .puc.pa.gov domain (official provenance)
- ✓ Page-1 caption readable (confirm doc type)

### Deliverable
Candidate list: `[(company, audit_date, pdf_url, source_page_url), ...]`

---

## Phase 2: Verification (30 min)

### Task
Verify each candidate audit is real and extract properly.

### Steps
1. For each candidate PDF:
   - Fetch page 1 via browser or `fetch_doc()` with informative User-Agent
   - Read the page caption: should mention "Management & Operations Audit" or "Management Efficiency Investigation"
   - Verify company name + audit year match the metadata
   - Check for Exhibit I-2 or equivalent recommendation summary (success marker for parsing)

2. Reject if:
   - Page count = 0 (fetch failed)
   - Title is placeholder/error page
   - No recommendation summary found (metadata-only)

3. Accept and add to seed list

### Success Criteria
- ✓ All candidates verified against page-1 caption
- ✓ At least 3 confirmed with Exhibit I-2 equivalent
- ✓ No false positives

### Deliverable
Verified seed list (ready for seeding)

---

## Phase 3: Seed & Parse (1 hour)

### Task
Add verified audits to `data/seeds/pa_puc.json` and validate parsing.

### Steps
1. **Add to seed file:**
   ```json
   {
     "id": "YYYY-MM-DD_company-name_pa-mo-audit",
     "company": "Full Legal Name",
     "company_raw": "Raw name from document",
     "collection": "state_audit",
     "jurisdiction": "PA",
     "source": "PA PUC Bureau of Audits",
     "doc_type": "management & operations audit",
     "industry": "electric" | "gas" | "mixed",
     "pdf_url": "https://www.puc.pa.gov/pcdocs/{id}.pdf",
     "source_page_url": "https://www.puc.pa.gov/press-release/YYYY/...",
     "parse": true,
     "fetch": true,
     "captured_at": "2026-06-15"
   }
   ```

2. **Run pipeline:**
   ```bash
   python3 -m pipeline.sources --seed data/seeds/pa_puc.json
   python3 -m pipeline.structure
   ```

3. **Validate extraction:**
   - Check `data/processed/{id}/report.json` for findings count > 0
   - Spot-check 2–3 findings to ensure Exhibit-I-2 parsing worked (titles should be functional areas, not headers)
   - Verify no regressions: existing PA audits still parse correctly

4. **Run test suite:**
   ```bash
   python3 -m pytest tests/ -k "test_" --tb=short
   ```

### Success Criteria
- ✓ All new audits extract findings (finding_count > 0)
- ✓ No test regressions
- ✓ New findings added to `docs/data/findings.csv` via next `pipeline.build`

### Deliverable
3–5 new report.json files in data/processed/ with parsed findings

---

## Phase 4: Commit & Document (15 min)

### Steps
1. Create commit with the new seeds + findings:
   ```bash
   git add data/seeds/pa_puc.json data/processed/*/report.json
   git commit -m "feat(pa-expansion): add 3–5 new PA M&O audits with findings
   
   - Added {count} audits from PA PUC Bureau (dates/companies)
   - All parse=true, verified via page-1 captions
   - Total {N} new findings extracted across audits
   
   Parsers: PA Exhibit-I-2 (no regressions, existing audits still extract correctly)
   Tests: {count} passed, 2 skipped
   "
   ```

2. Update docs/PA_EXPANSION_PLAN.md with completed audits

### Deliverable
Single commit; updated docs

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Press-release archive incomplete/blocked | Low | Use Wayback Machine snapshot or PUC news email archive |
| PDF fetch fails for new audits | Very low | Fallback: `fetch=false`, tag as metadata-only, re-verify later |
| Parser fails on variant layout | Low | Investigate format, update `_PA_EXHIBIT_I2_*` regex if needed (add variant test) |
| Test regression | Very low | Full suite passes before commit |

---

## Success Definition

✅ **3–5 new PA M&O audits seeded, verified, and parsing successfully**  
✅ **30–100 new findings extracted**  
✅ **Zero test regressions**  
✅ **Single clean commit to main**

---

## Timeline
- Phase 1 (Discovery): 30 min
- Phase 2 (Verification): 30 min
- Phase 3 (Seed & Parse): 1 hour
- Phase 4 (Commit & Docs): 15 min
- **Total: 2 hours 15 minutes**

---

## Resource Links

- PA PUC press releases: https://www.puc.pa.gov/press-release/
- PA M&O audit checklist: docs/PA_EXPANSION_PLAN.md
- Parser source: pipeline/state_structure.py:parse_pa_exhibit_i2_findings
- Seed format: pipeline/models.py:SourceSeed
