# MI Liberty Findings Parser Refinement — Phased Plan

**Effort:** 3–4 hours (one session)  
**Expected outcome:** Extract true audit findings (not chapter headers), +10–20 high-quality findings  
**Priority:** MEDIUM-LOW (quality improvement; low volume impact, high correctness impact)

---

## Current State

**Seeded audits:** 4 MI distribution audits (Consumers Energy part 1 & 2, DTE part 1 & 2)  
**Current extraction:** 22 findings total (mostly chapter/section headers as findings)
**Parser:** `parse_mi_findings()` in `state_structure.py` uses regex to extract chapter lines + numbered items  
**Assessment:** Extraction works mechanically but captures structural markers instead of audit content

---

## Root Cause Analysis

### What's Being Extracted Now
```
Finding 1: "Introduction & Executive Summary" 
  → 6 numbered items (these are TOC entries, not recommendations)

Finding 2: "Distribution System Organization, Management and..."
  → 59 numbered items (chapter content)
```

### Why This Happens
- Regex patterns match:
  - `_MI_CHAPTER_RE = r"^Chapter\s+([IVXLCM]+)\s*(?:–|—|-)\s*(.+?)$"`
  - `_MI_FINDING_RE = r"^(\d+)\.\s+(.+?)$"`
- The parser correctly identifies chapters but treats all numbered items as "findings"
- The audit structure (chapters with sub-numbered sections) is being flattened incorrectly

### What Should Be Extracted
True audit findings should be:
- Statements like: "We found that..." or "The auditor noted..." or "Management should..."
- Typically appear in a dedicated "Findings" or "Audit Results" section
- Have clear audit/recommendations/actions structure
- Are NOT part of narrative chapters

---

## Phase 1: Document Analysis (45 min)

### Task
Understand the actual structure of MI Liberty audits to identify where true findings live.

### Steps
1. **Extract sample text** from one MI audit:
   ```bash
   python3 << 'EOF'
   import json
   from pathlib import Path
   
   text_file = Path("data/processed/2024-09-23_consumers-energy_mi-distribution-audit-part1/text.json")
   text_data = json.loads(text_file.read_text())
   
   # Print first 30 pages
   for page in text_data['pages'][:30]:
       print(f"--- Page {page['page']} ---")
       print(page['text'][:500])
       print()
   EOF
   ```

2. **Look for:**
   - Where does "Findings" or equivalent section start?
   - What markers precede true findings (e.g., "Finding 1:", "Issue:", "Observation:")?
   - How are findings structured (single statement vs. multi-part)?
   - Is there a recommendations section?

3. **Document the structure** in `docs/MI_AUDIT_STRUCTURE.txt`:
   ```
   Page 1-5: Cover, TOC
   Page 6-X: Introduction (narrative, not findings)
   Page Y-Z: Findings Section
     - Marker: "Finding 1:" or similar
     - Each finding: statement + recommended action
   Page Z+: Appendices (data tables, etc.)
   ```

### Success Criteria
- ✓ Identified actual "Findings" section in audit
- ✓ Found true marker pattern (e.g., "Finding 1:", "Issue:")
- ✓ Understand finding structure (single vs. multi-part)

---

## Phase 2: Regex Refinement (1.5 hours)

### Task
Update `parse_mi_findings()` regex patterns to extract true findings instead of chapter headers.

### Steps

1. **Create new regex patterns:**
   ```python
   # Current (broken):
   _MI_CHAPTER_RE = r"^Chapter\s+([IVXLCM]+)\s*(?:–|—|-)\s*(.+?)$"
   _MI_FINDING_RE = r"^(\d+)\.\s+(.+?)$"
   
   # New patterns (from Phase 1 analysis):
   _MI_TRUE_FINDING_RE = r"^Finding\s+(\d+):?\s+(.+?)$"  # or "Observation 1:", etc.
   _MI_RECOMMENDATION_RE = r"^(?:Recommendation|Action|Management should):\s*(.+?)$"
   ```

2. **Refactor `parse_mi_findings()`:**
   - Skip chapter-level aggregation
   - Iterate through lines looking for `Finding N:` pattern
   - For each finding, capture the statement
   - Look ahead for associated recommendations
   - Group finding + recommendations into Finding object

3. **Add unit test** in `tests/test_mi_parser.py`:
   ```python
   def test_mi_parser_extracts_true_findings():
       """Parser extracts audit findings (not chapter headers)."""
       text = """
       Chapter I – Distribution System Organization
       
       Finding 1: The utility did not adequately document asset lifecycle.
       Recommendation: Implement documentation procedures per FERC guidance.
       
       Finding 2: Cost allocation methodology lacks transparency.
       Recommendation: Publish allocation basis in annual report.
       """
       findings = parse_mi_findings(text)
       assert len(findings) == 2
       assert "did not adequately document" in findings[0][1][0]
   ```

4. **Run regression test:**
   ```bash
   python3 -m pytest tests/test_state_structure.py -v
   # Ensure existing PA/CA/NJ parsers still pass
   ```

### Success Criteria
- ✓ New regex patterns identify true findings (not headers)
- ✓ Unit test passes
- ✓ No regression in other state parsers
- ✓ Sample MI audit parse shows meaningful findings (not "Introduction & Executive Summary")

---

## Phase 3: Re-extraction & Validation (1 hour)

### Task
Re-run MI audits through the updated parser and validate quality.

### Steps
1. **Re-extract one MI audit:**
   ```bash
   rm -r data/processed/2024-09-23_consumers-energy_mi-distribution-audit-part1/report.json
   python3 -m pipeline.structure --id 2024-09-23_consumers-energy_mi-distribution-audit-part1
   ```

2. **Inspect results:**
   ```bash
   python3 << 'EOF'
   import json
   report = json.loads(Path("data/processed/2024-09-23_consumers-energy_mi-distribution-audit-part1/report.json").read_text())
   print(f"Findings: {len(report['findings'])}")
   for finding in report['findings'][:3]:
       print(f"  - {finding['title'][:70]}")
   EOF
   ```

3. **Validate:**
   - Do findings now say things like "The utility did not..." or "We found that..."?
   - Do they include recommendations?
   - Is the finding_count reasonable (5–10 per audit, not 4–7)?

4. **If quality acceptable:**
   - Re-run all 4 MI audits:
     ```bash
     python3 -m pipeline.structure --id "*_mi-distribution-audit-*"
     ```
   - Check full extraction produces coherent findings

### Success Criteria
- ✓ Re-extracted MI audits show meaningful findings (not headers)
- ✓ finding_count reasonable (5–10 per audit)
- ✓ Spot-checked 3–5 findings read like real audit findings
- ✓ No errors in extraction

---

## Phase 4: Full Pipeline & Testing (30 min)

### Steps
1. **Run full structure pass:**
   ```bash
   python3 -m pipeline.structure  # all documents
   python3 -m pipeline.patterns   # re-mine themes
   python3 -m pytest --tb=short   # full test suite
   ```

2. **Update CSV export:**
   ```bash
   python3 -m pipeline.csv_export
   ```

3. **Spot-check CSV:**
   ```bash
   grep "michigan" docs/data/findings.csv | head -3
   ```
   - Do MI findings now include substantive audit findings?

### Success Criteria
- ✓ Full pipeline runs without error
- ✓ Test suite passes (no regressions)
- ✓ CSV export includes improved MI findings

---

## Phase 5: Commit & Document (15 min)

### Steps
```bash
git add pipeline/state_structure.py tests/test_state_structure.py \
        data/processed/*/report.json docs/data/ \
        docs/MI_AUDIT_STRUCTURE.txt

git commit -m "refactor(mi-parser): extract true audit findings instead of chapter headers

Previously:
- Parser extracted chapter headers as 'findings' (22 total, low quality)
- Example: 'Finding 1: Introduction & Executive Summary'

Now:
- Parser identifies true 'Finding N:' markers in text
- Extracts audit findings like 'The utility did not...'
- Captures associated recommendations

Result:
- MI audits now show {X} high-quality findings (improved from {Y})
- Improved data quality for pattern mining
- No regressions: PA/CA/NJ parsers still extract correctly

Technical: Updated regex patterns + refactored parse_mi_findings()
Tests: {count} passed, 2 skipped (new unit test for MI parser added)
"
```

2. **Update docs/MI_AUDIT_STRUCTURE.txt** (for future reference)

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| New regex misses some findings | Medium | Add fallback to existing parser; test thoroughly before committing |
| Breaks other parsers | Low | Full test suite validates; revert if needed |
| Finding structure is doc-specific | Medium | Use existing 4 audits to validate pattern; flag if variant found |

---

## Success Definition

✅ **MI audits now extract true audit findings (not chapter headers)**  
✅ **finding_count reasonable per audit (5–10 instead of 4–7)**  
✅ **Sample findings read like audit findings, not structural markers**  
✅ **No test regressions; full pipeline passes**  
✅ **Single clean commit with improved MI data quality**

---

## Timeline

- Phase 1 (Analysis): 45 min
- Phase 2 (Refinement): 1.5 hours
- Phase 3 (Re-extraction): 1 hour
- Phase 4 (Testing): 30 min
- Phase 5 (Commit): 15 min
- **Total: 3 hours 40 minutes**

---

## Optional Expansion

If refinement succeeds + shows high value:
- Apply same analysis to **NJ Liberty Consulting audits** (4 audits, currently metadata-only)
- Extract recommendations + findings from prose-embedded audit text
- Would add 50–100+ findings across NJ corpus

---

## Resource Links

- MI parser: pipeline/state_structure.py:parse_mi_findings
- Test file: tests/test_state_structure.py
- MI audit samples: data/processed/*_mi-distribution-audit-*
