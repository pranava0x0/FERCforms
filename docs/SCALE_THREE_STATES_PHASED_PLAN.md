# Scale to 3 New States — Phased Delivery Plan

**Effort:** 4–5 hours (one full session)  
**Expected yield:** 9–15 new documents, 50–150 new findings  
**Priority:** MEDIUM (breadth matters for pattern confidence and "audit-my-doc" coverage)

---

## Target States Selection

Recommend Deep South cluster (high regulatory activity, lower coverage):
1. **Louisiana (LA)** — LPSC (Louisiana Public Service Commission)
2. **Mississippi (MS)** — MPSC (Mississippi Public Service Commission)
3. **Arkansas (AR)** — APSC (Arkansas Public Service Commission)

**Rationale:** 
- Adjacent utilities (Entergy, utilities with multi-state footprints)
- Audit and rate-case records publicly available
- Currently minimal or zero seeded docs (high value)
- Similar to existing corpus (state commissions, rate cases, fuel-cost reviews)

---

## General Workflow (Repeat 3× per state)

```
FOR each state:
  1. IDENTIFY: Find 3–5 high-value documents (audits + contested rate cases)
  2. VERIFY: Page-1 caption + source confirmation
  3. SEED: Add to appropriate seed file with metadata
  4. INGEST: Run pipeline.sources on new seeds
  5. TEST: Check extraction quality
  6. COMMIT: Group commits per state
```

---

## Phase 1: Louisiana (LPSC) — 1.5 hours

### Task
Add 3–5 Louisiana documents focused on fuel-cost reviews and management audits.

### Discovery (30 min)
1. **Access:** Visit https://www.lpsc.louisiana.gov/
   - Find "Orders" or "Dockets" section (may be named "Official Proceedings")
   - Search for: "fuel cost recovery", "audits", "prudence review", or target utility (Entergy, SWEPCO)

2. **Candidates to seek:**
   - Recent utility management/operations audit (any major utility serving LA)
   - Entergy Louisiana fuel-cost prudence order (annual)
   - SWEPCO fuel-cost compliance order
   - Any contested rate case with staff testimony

3. **Capture metadata:**
   - Company name (exact legal name from document)
   - Docket number
   - Decision/Order date
   - PDF URL (capture from LPSC site, must be .lpsc.louisiana.gov domain)

### Verification (30 min)
1. For each candidate: fetch page 1
2. Confirm document type matches metadata
3. Check: does it have substantive content (not just cover letter)?
4. Verify company name + docket number match

### Seeding & Testing (30 min)
1. Create `data/seeds/la_lpsc.json` with 3–5 verified documents
2. Run: `python3 -m pipeline.sources --seed data/seeds/la_lpsc.json`
3. Check extraction: each doc should have page_count > 0 and be marked structured=true
4. Spot-check 1–2 documents in `docs/data/` to verify no parse errors

### Success Criteria
- ✓ 3–5 LA documents seeded
- ✓ All page_count > 0 (fetch successful)
- ✓ All extract without errors (check `data/processed/*/report.json` exists)

---

## Phase 2: Mississippi (MPSC) — 1.5 hours

### Task
Add 3–5 Mississippi documents focused on utility audits and rate cases.

### Discovery (30 min)
1. **Access:** Visit https://www.psc.ms.gov/
   - Find "Orders" or "Filings" section
   - Search for: "audit", "management", target utilities (Dominion, MPLS, regulated electric co-ops)

2. **Candidates:**
   - MPLS (Mississippi Power) or Dominion Energy Mississippi recent audits
   - Annual cost-of-service or rate case from past 2 years
   - Any fuel-cost prudence decision

3. **Capture metadata** (same as LA)

### Verification (30 min)
1. Same as LA (page-1 verification, substantive content check)

### Seeding & Testing (30 min)
1. Create `data/seeds/ms_psc.json`
2. Run: `python3 -m pipeline.sources --seed data/seeds/ms_psc.json`
3. Spot-check extraction quality

### Success Criteria
- ✓ 3–5 MS documents seeded
- ✓ All fetch and extract successfully
- ✓ No errors in pipeline

---

## Phase 3: Arkansas (APSC) — 1.5 hours

### Task
Add 3–5 Arkansas documents.

### Discovery (30 min)
1. **Access:** Visit https://www.apsc.arkansas.gov/
   - Find "Dockets" or "Orders" section
   - Search for: "audit", "order", target utilities (Entergy Arkansas, Empire District)

2. **Candidates:**
   - Entergy Arkansas or Empire District recent audit
   - Rate case with Commission order
   - Any rider adjustment (fuel-cost, renewable energy)

3. **Capture metadata**

### Verification (30 min)
1. Same as LA/MS

### Seeding & Testing (30 min)
1. Create `data/seeds/ar_apsc.json`
2. Run pipeline
3. Verify extraction

### Success Criteria
- ✓ 3–5 AR documents seeded
- ✓ All fetch and extract successfully

---

## Phase 4: Consolidation & Testing (30 min)

### Steps
1. **Run full pipeline:**
   ```bash
   python3 -m pipeline.sources  # reprocess all including new LA/MS/AR
   python3 -m pipeline.structure
   python3 -m pipeline.patterns  # generate new themes across expanded corpus
   python3 -m pytest --tb=short  # verify no regressions
   ```

2. **Validate coverage:**
   - Check `docs/data/meta.json` for updated jurisdiction counts
   - Spot-check 1–2 new findings in CSV export
   - Verify patterns detected across new docs (should mine 1–2 new themes if data-rich)

3. **Document findings:**
   - Count new documents + findings per state
   - Record in session notes

### Success Criteria
- ✓ Full pipeline runs without error
- ✓ Test suite passes
- ✓ New corpus metadata updated

---

## Phase 5: Commit (15 min)

### Steps
```bash
git add data/seeds/la_lpsc.json data/seeds/ms_psc.json data/seeds/ar_apsc.json \
        data/processed/*/report.json docs/data/
git commit -m "feat(scale-three-states): expand Deep South coverage — LA, MS, AR

Added:
- LA: 3–5 LPSC documents (fuel-cost reviews + audits)
- MS: 3–5 MPSC documents
- AR: 3–5 APSC documents

Total: {N} new documents, {M} new findings across 3 states
Jurisdictions now covered: {updated list}

All documents verified via page-1 captions, official .gov sources only.
Tests: {count} passed, 2 skipped (no regressions)
"
```

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Commission website structure unclear | Low | Use Wayback Machine or ask commission directly |
| PDF fetch fails | Very low | Re-verify URL; if persistent, tag as fetch=false |
| Document is metadata-only (0 pages) | Low | Keep anyway; mark structured=false; note for follow-up |
| Parser fails on new format | Low | Investigate in isolation; metadata-only fallback; plan variant parser if pattern repeats |

---

## Success Definition

✅ **9–15 new Deep South documents seeded and extracted**  
✅ **50–150 new findings across 3 states**  
✅ **Full pipeline runs without error**  
✅ **3 state-specific commits, properly documented**  
✅ **Corpus now includes LA, MS, AR regulatory decisions**

---

## Timeline

- Phase 1 (LA): 1.5 hours
- Phase 2 (MS): 1.5 hours
- Phase 3 (AR): 1.5 hours
- Phase 4 (Consolidation): 30 min
- Phase 5 (Commit): 15 min
- **Total: 5 hours**

---

## Resource Links

- LA LPSC: https://www.lpsc.louisiana.gov/
- MS MPSC: https://www.psc.ms.gov/
- AR APSC: https://www.apsc.arkansas.gov/
- Seed format: pipeline/models.py:SourceSeed
- Access notes: docs/data-sources.md
