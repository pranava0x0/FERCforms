# State Audit & Rate-Case Extraction Strategy (Options C & D)

**Date: 2026-06-07**  
**Status: Implementation Planning**

---

## Executive Summary

Options C (Full State Audit Coverage) and D (Rate-Case Findings) require different approaches due to data availability:

- **Option C Feasibility:** Limited by PDF access (13/73 state audits available; 60 are metadata-only)
- **Option D Feasibility:** High (99/110 rate-case documents available; diverse regulatory formats)
- **Recommendation:** Implement Option C incrementally (start with 13 available PDFs, build framework for future ones), then pivot to Option D for immediate ROI

---

## Option C: State Audit Coverage

### Current Data Status

**Total state audit documents:** 73  
**Documents with accessible PDFs:** 13 (18%)  
**Documents with fetch=false (inaccessible URLs):** 60 (82%)

#### PDF-Available Documents by Format

| Format | Count | Notes |
|--------|-------|-------|
| PA management & operations audits | 3 | Structured; already have manual findings |
| PA management efficiency investigation | 1 | Similar structure to M&O audits |
| CT performance/rate design investigations | 2 | Regulatory decision format |
| MO prudence reviews | 2 | Staff evaluation format |
| MS utilities staff annual reports | 2 | Administrative format |
| UT energy balancing account audit | 1 | Specialized technical audit |
| TN weather normalization audit | 1 | Regulatory review |
| **Subtotal** | **13** | Ready for parsing |

#### Metadata-Only Documents by Format

| Format | Count | Status |
|--------|-------|--------|
| Service quality audits | 21 | URLs blocked/inaccessible |
| Utility compliance reviews | 21 | URLs blocked/inaccessible |
| Other state audit types | 18 | Mixed accessibility |
| **Subtotal** | **60** | Require URL verification + fetch |

### Implementation Approach

#### Phase 1: Parse 13 Available PDFs (Weeks 1-2)

**Build parsers for each format:**

1. **PA Management & Operations Audits** (3 docs, 3 hrs)
   - Structure: Functional area headings → Exhibit I-3 summary table with recommendations
   - Key sections: Exhibits I-1 (ratings), I-2 (savings), I-3 (recommendations)
   - Extraction: Functional areas as Finding titles, numbered recs as Recommendation objects
   - Status: **In progress** — `structure_state_pa_audit()` partially implemented in `pipeline/structure.py`

2. **CT Performance/Rate-Design Investigations** (2 docs, 2 hrs)
   - Structure: Regulatory decision orders with ordered findings/conclusions
   - Extraction: Findings from decision narrative, rulings as recommendations

3. **MO Prudence Reviews** (2 docs, 2 hrs)
   - Structure: Staff evaluation with comparative analysis
   - Extraction: Evaluated claims as findings, staff recommendations

4. **Other formats** (MS reports, UT/TN audits): 3 hrs
   - Lighter-weight parsers for specialized formats

**Effort:** ~10 hours of implementation + testing

**Expected findings:** 80–150 across 13 documents (audit formats less detailed than FERC)

#### Phase 2: URL Verification & Fallback Strategy (Weeks 3-4)

For the 60 metadata-only documents:

1. **Batch verify URLs** using HTTP HEAD requests
   - Expected result: Some URLs will become accessible (domain changes, redirects)
   - Estimate: 20–30% will respond after fixing redirect/domain issues

2. **For genuinely inaccessible URLs:** Mark as "archived" and create a crawler task
   - Some URLs may be recoverable from Wayback Machine
   - Others may require direct agency contact

3. **Add to backlog:** Defer to post-launch if URLs remain inaccessible

#### Phase 3: Framework for Future Expansion

- Document parser patterns in a template (`pipeline/structure_state_*.py`)
- Add state audit type detection (doc_type-based routing)
- Create regression test suite for each format

### Expected Yield (Option C)

- **From 13 available PDFs:** 80–150 findings
- **New themes:** Service quality performance, compliance standards, distribution system efficiency, cost control
- **Coverage gaps:** Pending URL verification for 60 documents

---

## Option D: Rate-Case & Fuel-Cost Findings

### Current Data Status

**Total rate-case documents:** 110  
**Documents with accessible PDFs:** 99 (90%)  
**Documents format:** Diverse regulatory orders, settlements, testimony, applications

#### Document Types (Top Categories)

| Type | Count | Content |
|------|-------|---------|
| Direct testimony | 20 | Witness statements; technical justifications for cost requests |
| Base-rate case orders | 5 | Commission decisions on total revenue requirements |
| Fuel cost adjustment orders | 6 | Fuel-cost pass-through decisions with findings |
| Settlement agreements | 3+ | Negotiated resolutions with specific terms |
| Commission orders | 10+ | Regulatory decisions with findings and rulings |
| Applications/petitions | 10+ | Utility requests for rate adjustments |
| Other (ERRA, environmental, conservation, etc.) | 40+ | Specialized cost recovery or tariff matters |

### Extraction Strategy

Rate-case documents don't contain **audit findings** (noncompliance issues). Instead, they contain **regulatory decisions** with three key finding types:

#### Finding Type A: Disallowances
```
"Disallowance: $X cost request denied for [reason]"
Example: "Disallowance: $5.2M fossil-fuel generation costs denied due to 
efficiency standards violation."
```

#### Finding Type B: Approved Costs
```
"Approved: $X cost recovery granted [with conditions]"
Example: "Approved: $42.1M fuel-cost recovery granted with quarterly 
true-up mechanism."
```

#### Finding Type C: Settlement Terms
```
"Settlement: Parties agree to [outcome]"
Example: "Settlement: Utility accepts 2% rate cap; Commission allows 
recovery of 80% of smart-meter deployment costs over 5 years."
```

### Implementation Approach

#### Phase 1: Build Rate-Case Parser (Week 1)

**Pattern-based extraction** (simpler than audit parsing):

1. **Identify document type** (order vs. settlement vs. testimony)
2. **Extract key decision sections:**
   - "The Commission finds..."
   - "This order approves/denies..."
   - "Settlement terms:"
   - Dollar amounts and findings

3. **Tag by category** (disallowance/approval/settlement)

**Expected precision:** 70–80% (regulatory language is varied, structured but not formulaic)

#### Phase 2: Sample & Verify (Week 1-2)

- Process 10–15 representative documents
- Manually verify extraction accuracy (spot-check 5 documents)
- Refine regex patterns based on false positives/misses

#### Phase 3: Batch Extract (Week 2)

- Run parser on all 99 available rate-case documents
- Log any documents that fail extraction (error rate tracking)
- Generate findings summary

#### Phase 4: Thematic Analysis (Week 3)

- Group findings by theme:
  - "Fuel cost disallowances" (frequency, avg amount, reasons)
  - "Smart-meter / distribution automation approvals"
  - "Reliability infrastructure investments"
  - Settlement patterns (rate caps, cost-sharing, phase-ins)

### Expected Yield (Option D)

- **Total findings:** 300–500 across 99 documents (3–5 per document average)
- **New themes:**
  - "Fuel cost recovery patterns" (what drives disallowance?)
  - "Infrastructure investment approval trends"
  - "Regulatory settlement strategies"
  - "Rate design innovations" (time-of-use, demand response, decoupling)
  - "Cost allocation disputes" (common disagreements)

- **Regulatory Intelligence:**
  - Which utility types face the most frequent cost disallowances?
  - Are settlement rates increasing (faster resolution)?
  - What cost categories are easiest/hardest to recover?

---

## Combined Findings (C + D)

### Corpus After Completion

| Collection | Docs | Findings (Est.) | Themes |
|------------|------|-----------------|--------|
| FERC Audits | 120 | 602 | 13 |
| Prudence Reviews | 14 | 30 | Existing |
| State Audits (Phase 1) | 13 | 80–150 | 3–5 new |
| State Rate Cases | 99 | 300–500 | 5–8 new |
| **Total** | **246+** | **1,012–1,282** | **~26 themes** |

### New Insights

The combined dataset would show:

1. **Compliance vs. Cost Control:** Audits flag *operational issues*; rate cases show *cost control outcomes*
2. **Regulatory Strategy Patterns:** Settlements indicate leverage points in negotiations
3. **Geographic Variation:** Themes differ by region (fuel-heavy vs. distribution-heavy states)
4. **Temporal Trends:** Service quality (audit focus) vs. cost recovery (rate-case focus) trends over time

---

## Implementation Timeline & Effort

| Phase | Task | Weeks | Effort | Owner |
|-------|------|-------|--------|-------|
| C-Phase 1 | PA audit parser | 1–2 | 3 hrs | Claude |
| C-Phase 1 | Other state audit parsers | 1–2 | 7 hrs | Claude |
| C-Phase 2 | URL verification & fallback | 3–4 | 2 hrs | Claude + Manual |
| D-Phase 1 | Rate-case parser (draft) | 1 | 2 hrs | Claude |
| D-Phase 2 | Sample & verify | 1–2 | 3 hrs | Claude + Manual |
| D-Phase 3 | Batch extraction | 2 | 1 hr | Claude |
| D-Phase 4 | Thematic analysis | 3 | 2 hrs | Claude |
| **Total** | | **3–4 weeks** | **20 hrs** | |

---

## Risk & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| State audit URLs remain inaccessible | High (60%) | Medium | Phase 2 verification; mark as "recoverable later" |
| Parser precision < 70% (state audits) | Medium (30%) | Low | Manual sampling; regression tests |
| Rate-case extraction miss key findings | Medium (20%) | Low | Domain-expert review of samples; iterative refinement |
| Format diversity exceeds parser capability | Medium (40%) | Low | Graceful degradation (fewer findings, not crashes); document limitations |

---

## Success Criteria

- [ ] All 13 available state audit PDFs processed (≥ 50 findings extracted)
- [ ] Rate-case batch extraction complete (≥ 250 findings across 99 docs)
- [ ] Parser accuracy verified on 5-document sample (≥ 70% precision)
- [ ] New themes identified and named (≥ 5 distinct themes)
- [ ] All code committed with regression tests
- [ ] Documentation complete (parser implementation guide for future extensions)

---

## Next Steps

1. **Immediately:** Finalize PA audit parser; test on 3 available PDFs
2. **Week 1–2:** Complete other state audit parsers; estimate actual findings yield
3. **Week 2:** Pivot to rate-case parser; build and test on 10-doc sample
4. **Week 3–4:** Batch processing and thematic synthesis
5. **Post-launch:** Add state audit URL verification to backlog; prioritize high-confidence URL fixes

---

## Appendices

### A. State Audit Parser Status

- **PA Management & Operations:** 
  - Status: Partial implementation in `pipeline/structure.py`
  - Function: `structure_state_pa_audit()`
  - Needs: Full Exhibit I-3 table parsing; testing on real PDFs

- **Other formats:**
  - Status: Not started
  - Effort estimate: 2–3 hrs each

### B. Rate-Case Parser Patterns

Key regex patterns to match:

```
# Disallowance
r"(\$[\d.]+M?)\s+(?:cost|expense|claim).*?(?:denied|disallowed|rejected)"

# Approval
r"(\$[\d.]+M?)\s+(?:recovery|authorization|approval).*?(?:approved|granted|allowed)"

# Settlement
r"settlement\s+.*?(?:agree|parties|Commission).*?(?:\$[\d.]+M?)"
```

### C. Document Type Mapping

State audits → Finding = Functional area + Recommendation  
Rate cases → Finding = Regulatory decision (disallowance/approval/settlement)

This keeps the AuditReport model flexible for both data types.

---

**Document Version:** 1.0  
**Last Updated:** 2026-06-07  
**Author:** Claude Code (AI Agent)
