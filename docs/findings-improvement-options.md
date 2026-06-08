# Findings depth — options to improve explorer weight

**Current state** (as of 2026-06-07):
- **250 total reports** (120 FERC + 14 prudence + 116 state)
- **632 findings** (602 FERC + 0 prudence + 30 state)
- **1,582 recommendations** (1,505 FERC + 0 + 77 state)
- **State audit tab is light:** 116 docs but only 3 parsed (PA M&O audits), 113 metadata-only

**Why state audits are metadata-only:**
- Legal orders, testimony, settlement agreements are unstructured prose
- Parsing them into clean findings risks garbled/inaccurate extractions
- The editorial rule: quote verbatim or not at all (see [CLAUDE.md](../CLAUDE.md) § "Data is the product")
- Exception: PA M&O audits have a **clean, enumerable Exhibit I-2** ("Summary of Recommendations")

---

## Options, ranked by effort → value

### Option A: Broaden PA M&O parser (low effort, medium value)
**Current:** 3 PA reports parsed (Duquesne, PPL, FirstEnergy PA)  
**Opportunity:** PA has ~20+ M&O audits across multiple utilities + years

**Steps:**
1. Check `data/seeds/pa_puc.json` for all M&O audit records
2. Flip `parse=true` on the remaining M&O audits (keep `parse=false` for focused audits / MEI)
3. Run `pipeline.structure --limit 50` to parse them
4. Review the no-regression snapshot test — ensure Duquesne/PPL/FirstEnergy counts don't change
5. Commit

**Estimated findings gain:** ~30–50 additional PA findings across 10–15 more audits  
**Risk:** Snapshot test may fail on parsing edge cases; low-risk, easy to debug

---

### Option B: Create MI Liberty parser (medium effort, medium value)
**Current:** 0 MI audits parsed (4 seeded, all metadata-only)  
**Opportunity:** MI Liberty Consulting reports are consultant-authored, cleaner structure than legal orders

**Structure:**  Liberty reports typically have:
- Executive summary
- Findings table (utility, issue, recommendation)
- Detailed sections per finding

**Steps:**
1. Read a few MI Liberty PDFs locally to understand their structure
2. Write `pipeline/state_structure.parse_mi_liberty()` (similar to PA's Exhibit I-2 handler)
3. Add a snapshot test (current: 0 findings, no regression expected)
4. Flip `parse=true` in `mi_mpsc.json` for the Liberty audits
5. Run `pipeline.structure --limit 10` and review output
6. Commit

**Estimated findings gain:** ~20–40 MI findings across 4 audits  
**Risk:** Requires PDF structure analysis; moderate complexity; but structured consultant reports are more predictable than legal orders

---

### Option C: Focus on FERC audit recovery (high effort, high value)
**Current:** 120 FERC reports, 94 parsed, 26 with 0 findings (22%)  
**Opportunity:** The 26 zero-finding reports likely contain findings but use different TOC/section layouts

**Detail:** [BACKLOG.md § "Recover findings from 26 zero-finding reports"](../BACKLOG.md) — split into two tracks:
- **~15 FY2014–2018 (backfill)** — older format (combined "Summary of Compliance Findings" + tab-leader TOCs)
- **~11 live 2019+** — newer format, same parser, but new header/TOC variants not yet captured

**Steps:**
1. Create `structure_report_legacy()` function for FY2014–2018 format (separate path, can't alter 2019+ output)
2. Extend header/TOC variant regex for 2019+ (additively, re-validate snapshot)
3. Re-run `pipeline.structure --limit 50` on the 26 reports
4. Commit

**Estimated findings gain:** ~50–150 FERC findings from currently zero-finding reports  
**Risk:** High — touching the core parser can break the 594 already-working findings; strict snapshot test required

---

### Option D: Accept metadata-only for state legal docs (low effort, clarifies intent)
**Rationale:** Legal orders, testimony, and settlement agreements are intentionally NOT parsed because:
- No clean enumerable structure (prose, cross-references, complex conditions)
- Paraphrasing risks loss of nuance
- Verbatim extraction from legal text is fragile (footnotes, "whereas" clauses, severability)

**Action:** 
1. Update the explorer's state-audit tab to **lean into** metadata-only model — add a section like:
   ```
   "About this collection: State PUC audits are documented with full provenance 
    (source links, filing dates, doc types) but not parsed into findings. 
    This preserves the legal text's integrity — findings live in the PDFs, 
    not in abstracted quotes. Open any doc to read its findings directly."
   ```
2. Optionally, add a **"Document type" facet** to the state-audit tab so users can filter by (rate-case order, testimony, settlement, audit report)
3. Commit a clarifying note to the site

**Estimated findings gain:** 0 (intentional; improves UX clarity instead)  
**Risk:** None; reframes existing design as intentional

---

## Recommendation

**Sequence:**
1. **Start with Option A (PA broadening)** — straightforward, likely quick wins, lowest risk
2. **Then Option C (FERC zero-finding recovery)** — high value but requires strict testing; do once PA is solid
3. **Then Option B (MI parser)** if time permits — medium complexity, good learning for other state formats
4. **Codify Option D (metadata-only framing)** as documentation, not code

This sequence maximizes findings improvement while managing risk — PA is proven, FERC recovery is the biggest value pool, MI is nice-to-have.

**Current blockers:** None identified; all paths are open.
