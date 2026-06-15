# Next Ideas & Roadmap

**Current state**: 153 documents ingested, 1263 findings extracted, 25 themes identified, TX parser complete.

---

## 🎯 High-Impact Ideas (Prioritized)

### 1. **PA Findings Parser** (2–3 hours)
**Why**: PA Bureau of Audits has 13 validated government-source PDFs. Infrastructure for parsing (Exhibit I-2 table) already exists in `state_structure.py`.

**What to do**:
- Enable `parse=True` for PA M&O audit documents
- Run `pipeline.sources` on PA seeds
- Expected: 30–50 findings from 13 documents
- Output: `data/processed/pa_*/report.json` with structured findings

**Impact**: Double the state findings (TX + PA = ~60 findings), test multi-state theme clustering.

---

### 2. **State Findings Cross-Link to FERC** (1–2 hours)
**Why**: The north-star feature asks "audit-my-document" — given a filing, flag issues FERC auditors would raise. State patterns provide independent validation.

**What to do**:
- Build `cross_reference.py` to match state findings to FERC themes
- Key signals: utility company name, audit year, finding type (accounting, cost-of-service, etc.)
- Create `docs/cross_links.json`: {state_finding_id → [ferc_theme, ferc_examples]}

**Impact**: Bridges state + federal audit knowledge; enables "audit-my-document" MVP.

**Example**: If state finds "Depreciation mismatch" in Company X (2024), flag similar FERC theme + top examples.

---

### 3. **Expand State Coverage: High-Value States** (1–2 hours)
**Why**: Focus on states with existing audit infrastructure (MI, NJ, CA, OR, WA). These are top-20 utilities by regulated assets.

**Which states**:
- **MI**: Consumers Energy, DTE (major electric utilities)
- **NJ**: PSE&G, Jersey Central Power & Light (high audit activity)
- **CA**: PG&E, SCE (largest regulated utilities; active CPUC audits)
- **OR**: Portland General, PacifiCorp (smaller scale, but well-documented)
- **WA**: Puget Sound Energy, Avista (regional majors)

**What to do**:
- Use existing Tier 2/3 crawlers on these states' PUC portals
- Target: 50–100 PDFs total across 5 states
- Build state-specific parsers if document format differs from PA/TX

**Impact**: 60–100 new findings, validate theme patterns across geographies.

---

### 4. **Dollar-Impact Quantification** (Medium effort, high value)
**Why**: Findings are currently verbatim quotes. Adding dollar amounts makes them actionable.

**What to do**:
- For FERC audits: Extract "Questioned Costs" / "Unfavorable Findings" dollar amounts from executive summaries
- For state audits: Pull "Estimated Annual Impact" or "Potential Savings" from management response sections
- Build `findings_with_impact.json`: {finding_id → (amount, is_questioned_cost, year)}

**Data sources**:
- FERC reports often include settlement/audit outcome pages with dollar impact
- State management letters include estimated financial impact

**Impact**: Enable cost-of-noncompliance analysis; justify audit priorities.

---

### 5. **Interactive Web Dashboard** (3–4 hours, or defer)
**Why**: Current deliverable is JSON files. Dashboard makes themes discoverable and shareable.

**MVP**:
- Static HTML/JS page (no backend needed)
- Filter themes by: industry, audit type, year, state, company
- Show top findings per theme with verbatim quotes + source links
- Export findings as CSV/JSON

**Data flow**: `data/processed/patterns.json` → `docs/audit-explorer.html`

**Impact**: Showcases dataset to regulators, utilities, researchers.

---

### 6. **Multi-State Theme Clustering** (1–2 hours)
**Why**: Validate that themes are consistent across states/federal.

**What to do**:
- Cross-tabulate: theme × jurisdiction (FERC vs. TX vs. PA vs. others)
- Build heatmap: which themes appear in which states?
- Output: `docs/theme_by_jurisdiction.json` and visualization

**Example finding**: "Depreciation" appears in 80% of FERC electric audits, but only 20% of state audits → suggests FERC has stricter depreciation scrutiny.

**Impact**: Identify jurisdiction-specific risk areas; guide state regulators to federal best practices.

---

### 7. **Audit Recommendation Extraction** (2–3 hours)
**Why**: Currently, we extract findings (noncompliance) but not recommendations (corrective actions).

**What to do**:
- Update TX/PA parsers to extract `Recommendation` objects alongside findings
- For PA: already built (Exhibit I-2 has "Summary of Recommendations")
- For TX: extend parser to capture action items from detailed results
- For FERC: extract from executive summary "recommended" sections

**Output**: `report.findings[i].recommendations[]` populated in all parsed documents.

**Impact**: Enables utilities to understand what corrective action FERC/states expect.

---

### 8. **Trend Analysis: Recurrent Offenders** (1–2 hours)
**Why**: Some utilities appear in multiple audit reports. Do they have recurrent findings?

**What to do**:
- Build `utility_audit_history.py`: group reports by company name
- Cross-reference findings across years
- Flag utilities with 3+ findings in same theme across multiple audit years
- Output: `docs/recurrent_issues.json`: {utility_name → [(theme, year, finding), ...]}

**Example**: "Company X had Depreciation issues in 2020, 2021, 2022 → systemic weakness."

**Impact**: Identify chronic underperformers; highlight utilities needing priority audit attention.

---

## 📋 Implementation Order (Effort vs. Impact)

| Rank | Idea | Effort | Impact | Priority |
|------|------|--------|--------|----------|
| 1 | PA parser | 2h | HIGH | 🔴 Do next |
| 2 | State cross-link | 1h | HIGH | 🔴 Do next |
| 3 | High-value states | 2h | HIGH | 🟠 Do soon |
| 4 | Dollar-impact | 3h | HIGH | 🟡 Medium |
| 5 | Multi-state clustering | 2h | MEDIUM | 🟡 Medium |
| 6 | Recommendation extraction | 3h | MEDIUM | 🟡 Medium |
| 7 | Web dashboard | 4h | MEDIUM | 🟢 Polish |
| 8 | Trend analysis | 2h | MEDIUM | 🟢 Polish |

---

## 🎯 Session Goals (Next 2–3 hours)

**Realistic scope**: PA parser + state cross-link + start high-value states

**Stretch goal**: All 3 + multi-state clustering

**Deliverables**:
- ✓ `structure_pa_audit()` parser with tests
- ✓ PA findings extracted (30–50 new findings)
- ✓ Cross-reference logic (state → FERC theme mapping)
- ✓ Initial high-value state crawl (MI + NJ)

**Success metric**: 100+ total findings across 2+ states, cross-linked to themes.

---

## 🚀 Beyond This Session

**Month 1 goals**:
- 200+ documents from 10+ states
- 50+ findings/audits with dollar impact
- Web dashboard MVP
- Utility trend analysis

**Month 2 goals**:
- "Audit-my-document" prototype (given a filing, flag likely findings)
- 500+ findings across 20+ states
- Published research: "Common FERC/State Audit Findings Patterns"

**Month 3 goals**:
- Full production system with CI/CD
- Interactive public dashboard
- API for utility/regulator access

---

## 💡 Stretch Ideas (If time permits)

- **NLP-based finding similarity**: Cluster semantically similar findings across reports (vs. keyword-based themes)
- **Recommendation outcome tracking**: Did utilities follow auditor recommendations? (requires follow-up data)
- **Bayesian utility risk model**: Predict audit-failure probability given historical patterns
- **Comparative benchmarking**: "How does this utility's audit findings compare to peers?"
- **Machine-readable findings**: Convert all findings to structured schema (company, account, amount, fiscal year, etc.)

---

**Last updated**: 2026-06-15  
**Status**: Ready for next session — PA parser recommended as immediate next step.
