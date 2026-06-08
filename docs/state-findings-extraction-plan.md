# State Audit Findings Extraction Options

## The Gap

- **FERC audits (120 docs):** Full parser → 602 findings → 13 themes
- **State audits (53 docs):** 53 born-digital, extractable, but **NO parser** → 0 findings → 0 themes  
- **State rate cases (108 docs):** Born-digital cost recovery/fuel orders, but no findings extraction

**Root cause:** The extraction pipeline (`pipeline/structure.py`) only handles FERC audit format. State audits come from different regulatory bodies with different formats.

---

## State Audit Document Types (by what we have)

```
18 × service quality and reliability audit       (VA, CA, NY, TX, OH, WA, OR, etc)
12 × utility audit and compliance review          (VA, CO, NJ, MD, IN, KS, KY, etc)
 6 × utility compliance and performance audit     (IL, GA, NC, SC, AR, AZ)
 4 × distribution reliability audit               (MI Liberty Consulting, 2-part)
 2 × utility efficiency and compliance audit      (CO, MD)
 2 × affiliate transaction audit investigation    (NY)
 1 × energy balancing account audit               (UT — Daymark)
 1 × service quality and compliance investigation (NY)
 1 × management efficiency investigation          (PA — exists but unparsed)
 1 × utilities staff annual report               (MS)
```

---

## Extraction Options (Ranked by Effort & Impact)

### Option A: FERC-Only Focus (Lowest Effort)
**Decision:** Accept that state audits are reference material; don't extract from them.

- ✓ No new code needed
- ✓ Clear scope boundary
- ✗ State audits remain at 0 findings (wasted 169 docs)

**Recommendation:** NOT recommended — we collected 61 audit docs for a reason.

---

### Option B: Pick ONE State Format + Grow (Medium Effort, High ROI)

Extract from the largest/cleanest single format, prove the pattern, then expand.

**Best candidate: MI Liberty Consulting distribution audits (4 docs, 2-part structure)**
- 2-part format (Infrastructure Part 1 + Programs Part 2)
- Consultant format = consistent structure
- Topic: distribution reliability/operations/cost-recovery
- Challenge: Consultant reports have exec summary + detailed sections

**Extraction approach:**
1. Read the 4 MI Liberty reports manually
2. Document their consistent structure (exec summary, recommendations, detailed findings)
3. Write a `structure_state_liberty_consulting()` parser in `pipeline/structure.py`
4. Regression test on the 4 known docs
5. Extract findings → themes → verify sample manually

**Expected findings:** ~80-150 findings across 4 reports (consultant audits are typically detailed)

**Cost:** ~4-6 hours engineering + testing

---

### Option C: Full State PUC Coverage (High Effort, Full Impact)

Build a family of parsers for all state audit formats.

**Formats identified:**
1. **MI Liberty Consulting** (2 multi-part docs) → structured consultant audit
2. **PA Bureau of Audits** (2 mgmt&ops + 1 focused audit) → tabular "Summary of Recommendations"
3. **TX PUCT Fuel-Cost Proceedings** (4 docs: testimony + settlement + proposed order) → testimony + order format
4. **CA CPUC ERRA decisions** (3 HTML docs) → regulatory decision format
5. **Service Quality Audits** (18 docs: VA, NY, TX, OH, WA, OR, etc.) → regulatory order format
6. **Compliance Reviews** (12 docs) → varies by state; some tabular, some prose

**Per-format parser work:**
- Liberty (4 docs): `structure_state_liberty_consulting()` — 3 hrs
- PA Management (2 docs): `structure_state_pa_management()` — 2 hrs
- TX Fuel Case (4 docs): `structure_state_tx_fuel_proceedings()` — 2 hrs
- CA ERRA (3 docs): `structure_state_ca_erra()` — 2 hrs
- Service Quality (18 docs): `structure_state_service_quality_audit()` — 4 hrs
- Compliance Reviews (12 docs): `structure_state_compliance_review()` — 4 hrs

**Total effort:** ~17 hours engineering + testing

**Expected findings:** ~300-500 findings across 53 state audits → new themes like:
- "Service quality performance"
- "Compliance with reliability standards"
- "Distribution system efficiency"
- "Cost control recommendations"

**Regression risk:** High if parsers aren't validated carefully — wrong captures regress findings like FERC did (Cleco 12→1).

---

### Option D: Rate-Case & Fuel-Cost Findings (Exploratory)

The 108 rate-case documents include settlement agreements, cost-recovery orders, fuel-cost decisions with actual **disallowances** and **recovery amounts**. These are findings of a different type.

**Examples:**
- **Florida fuel-cost orders:** "Final Order on fuel cost recovery" — utilities request recovery; PSC grants/denies by amount
- **TX fuel-cost proceedings:** settlements + staff recommendations + final order
- **Fuel adjustment clauses:** orders approving/denying cost pass-through

**What could be extracted:**
- Disallowances: "$X found imprudent, denied recovery"
- Cost allocations: "Agreed allocation: $A to fuel, $B to O&M"
- Settlement terms: "Parties agree to $X refund over Y years"

**Challenge:** These are regulatory *decisions* about cost recovery, not audit *findings* about noncompliance. Different structure, different extraction rules.

**Recommendation:** Defer for now — focus on actual audits first.

---

## Recommended Path Forward

**Tier 1 (Do This Week):** Extract MI Liberty Consulting audits
1. Create `structure_state_liberty_consulting()` in `pipeline/structure.py`
2. Manually read 4 docs to understand structure
3. Extract recommendations/findings
4. Add regression test
5. Ingest & rebuild → ~80-150 findings

**Tier 2 (Next Month):** Add PA Management audits (already have some manual extraction)
1. Reuse existing PA parser logic
2. Verify it works on the PA focused audits
3. Extract → rebuild

**Tier 3 (Backlog):** Full state coverage IF we decide state audits are core
- Prioritize by: (a) doc count, (b) format uniqueness, (c) extraction clarity
- Service quality audits (18 docs) are the biggest bucket but may have variable structure — sample 3 first

---

## Why State Audits Matter (Justification for Investment)

1. **Geographic diversity:** Captures utilities across 26 states vs. FERC's federal scope
2. **Compliance focus:** State audits are mandated compliance reviews; rate cases are cost-recovery (different angle)
3. **Emerging patterns:** State oversight of service quality, data-center load, distributed generation — FERC audits don't touch these
4. **Regulatory trend mining:** Can we show "service quality audits are trending toward stricter compliance"?

---

## Current Findings by Collection (For Reference)

```
ferc_audit:           602 findings across 120 docs (13 themes, avg 5/doc)
state_audit:            3 findings across  61 docs (1 theme, from PA only)
state_rate_case:        0 findings across 108 docs (0 themes)
prudence_review:       30 findings across  14 docs (reference)
———————————————————————————————————————————————————
Total:                635 findings

Target if state extraction enabled:
state_audit:          300-500 findings across  61 docs (8-12 themes, avg 5-8/doc)
———————————————————————————————————————————————————
Total target:        932-1132 findings
```

---

## Implementation Checklist

- [ ] **Option A decision:** Confirm scope with user
- [ ] **Pick a starter format:** Liberty (MI) or PA? Or hybrid?
- [ ] **Manually parse 3-5 sample docs** to understand structure
- [ ] **Write the parser** in `pipeline/structure.py`
- [ ] **Add regression test** with known examples
- [ ] **Re-run pipeline:** `python -m pipeline.build`
- [ ] **Spot-check findings** on the original PDFs (10% sample)
- [ ] **Commit & document** which formats are now supported
