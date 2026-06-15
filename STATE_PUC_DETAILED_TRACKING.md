# State-by-State PUC Data Collection Tracking

**Last updated**: 2026-06-15  
**Overall status**: Tier 2 pipeline in progress, Tier 3 ready

---

## 🎯 CURRENT STATUS BY STATE

### ✅ TIER 1 COMPLETE (Ingested)

#### **TEXAS (TX)**
- **Landing pages found**: 33 (v1 crawl)
- **Direct PDFs**: 20 (internal audit office reports)
- **Pipeline status**: ✅ INGESTED (data/processed/tx_*/report.json)
- **Pages extracted**: 100+
- **Findings extracted**: 0 (state parser needed)
- **Next steps**:
  1. Build Texas-specific findings parser (`structure_tx_audit()`)
  2. Extract findings from internal audit reports
  3. Identify audit types: efficiency, compliance, management
  4. Cross-link with FERC audits by company name + date
- **Priority**: 🔴 HIGH (highest quality audit documents)

#### **WEST VIRGINIA (WV)**
- **Landing pages found**: 10 (v1 crawl)
- **Direct PDFs**: 5 (compliance reports, annual reports)
- **Pipeline status**: ✅ INGESTED (data/processed/wv_*/report.json)
- **Pages extracted**: 150+ (forms, reports)
- **Findings extracted**: 0 (forms-based, lower priority)
- **Next steps**:
  1. Analyze document types (mostly compliance forms, not audit reports)
  2. Assess feasibility of findings extraction
  3. If viable, build WV-specific parser
  4. Otherwise, keep as metadata-only reference documents
- **Priority**: 🟡 MEDIUM (useful for compliance context, not primary audit source)

#### **IDAHO (ID)**
- **Landing pages found**: 3 (v1 crawl)
- **Direct PDFs**: 3 (final orders, rules/regulations)
- **Pipeline status**: ✅ INGESTED (data/processed/id_*/report.json)
- **Pages extracted**: 50+
- **Document types**: Legal orders, not audit reports
- **Findings extracted**: 0
- **Next steps**:
  1. Evaluate: Are these audit-related or just regulatory orders?
  2. If audit-related, build ID findings parser
  3. If just legal orders, categorize as reference-only
  4. Clarify jurisdiction: Are these PUC audits or just Commission orders?
- **Priority**: 🟡 MEDIUM (unclear if audit documents; needs classification)

#### **MONTANA (MT)**
- **Landing pages found**: 7 (v1 crawl)
- **Direct PDFs**: 2 (annual performance reports, PSC annual reports)
- **Pipeline status**: ✅ INGESTED (data/processed/mt_*/report.json)
- **Pages extracted**: 60+
- **Document types**: Annual reports (not audit reports)
- **Findings extracted**: 0
- **Next steps**:
  1. Determine: Are annual reports relevant to audit analysis?
  2. Extract any audit-related sections if present
  3. If not audit-focused, downgrade to reference material
- **Priority**: 🟢 LOW (annual reports, not primary audit source)

---

### 🔄 TIER 2 IN PROGRESS (Pipeline Running)

#### **WASHINGTON (WA)**
- **Landing pages found**: 68 (v1 crawl)
- **Deep scrape results**: 50 PDFs (Tier 2)
- **Pipeline status**: 🔄 INGESTING NOW
- **Expected pages**: 200+
- **Document types**: Mixed (inspection reports, compliance docs, audit-adjacent)
- **Findings extracted**: Will be 0 until parser built
- **Next steps**:
  1. Wait for pipeline completion
  2. Analyze document types in processed output
  3. Identify audit-focused documents vs. regulatory docs
  4. Filter for actual audit reports (estimate: 20-30 of 50)
  5. Build WA-specific parser if audit documents found
  6. Otherwise, cross-reference with company names for context
- **Priority**: 🟡 MEDIUM (large document set, needs analysis)

#### **INDIANA (IN)**
- **Landing pages found**: 7 (v1 crawl)
- **Deep scrape results**: 50 PDFs (Tier 2) ⭐ Huge expansion!
- **Pipeline status**: 🔄 INGESTING NOW
- **Expected pages**: 150+
- **Document types**: To be determined (likely utility filings, reports)
- **Findings extracted**: Will be 0 until categorized
- **Next steps**:
  1. Wait for pipeline completion
  2. Sample 5-10 documents to understand content
  3. Classify: Are these audit reports or general filings?
  4. If audit-reports, estimate coverage and build parser
  5. If general filings, extract audit-relevant sections
- **Priority**: 🟠 MEDIUM-HIGH (50 documents from 7 landing pages = high-value state)

#### **DISTRICT OF COLUMBIA (DC)**
- **Landing pages found**: 6 (v1 crawl)
- **Deep scrape results**: 27 PDFs (Tier 2) ⭐ 4.5x expansion
- **Pipeline status**: 🔄 INGESTING NOW
- **Expected pages**: 100+
- **Document types**: To be determined
- **Findings extracted**: Will be 0 until analyzed
- **Next steps**:
  1. Wait for pipeline completion
  2. Review sample documents
  3. Check if DC includes federal/utility audits or just local
  4. Prioritize based on audit relevance
  5. Build DC parser if high-value audit documents found
- **Priority**: 🟠 MEDIUM-HIGH (27 PDFs from 6 pages = excellent extraction)

#### **PENNSYLVANIA (PA)**
- **Landing pages found**: 38 (v1 crawl)
- **Deep scrape results**: 13 PDFs (Tier 2)
- **Pipeline status**: 🔄 INGESTING NOW
- **Expected pages**: 50+
- **Document types**: Audit reports, compliance documents, Bureau of Audits materials
- **Findings extracted**: Will be 0 until parser built
- **Next steps**:
  1. Wait for pipeline completion
  2. These are likely higher-quality audit materials
  3. Build PA findings parser (Bureau of Audits format)
  4. Prioritize alongside Texas for findings extraction
  5. Cross-link with FERC audits by company
- **Priority**: 🔴 HIGH (PA has dedicated Bureau of Audits; audit-focused)

#### **GEORGIA (GA)**
- **Landing pages found**: 6 (v1 crawl)
- **Deep scrape results**: 9 PDFs (Tier 2)
- **Pipeline status**: 🔄 INGESTING NOW
- **Expected pages**: 30+
- **Document types**: To be determined
- **Findings extracted**: Will be 0 until categorized
- **Next steps**:
  1. Wait for pipeline completion
  2. Analyze document content
  3. Assess audit relevance
  4. If audit-focused, build GA parser
  5. If general filings, reference material only
- **Priority**: 🟡 MEDIUM (moderate document set, needs analysis)

#### **MAINE (ME)**
- **Landing pages found**: 8 (v1 crawl)
- **Deep scrape results**: 2 PDFs (Tier 2)
- **Pipeline status**: 🔄 INGESTING NOW
- **Expected pages**: 10+
- **Document types**: To be determined
- **Findings extracted**: Will be 0
- **Next steps**:
  1. Wait for pipeline completion
  2. If documents are audit-related, analyze
  3. Otherwise, low priority
- **Priority**: 🟢 LOW (only 2 documents, likely low-value)

---

### 📋 TIER 3 READY (Not Yet Started)

#### **ALASKA (AK)**
- **Landing pages found**: 7 (v1 crawl)
- **Deep scrape needed**: Tier 3 crawler
- **Expected PDFs**: 5-10 (estimate)
- **Next steps**:
  1. Run Tier 3 crawler on state.ak.us/rca
  2. Extract any audit PDFs found
  3. Validate & ingest through pipeline
  4. Analyze documents
  5. Build parser if audit-focused
- **Priority**: 🟡 MEDIUM (7 landing pages, worth exploring)

#### **MICHIGAN (MI)**
- **Landing pages found**: 5 (v1 crawl)
- **Deep scrape needed**: Tier 3 crawler
- **Expected PDFs**: 3-8 (estimate)
- **Next steps**:
  1. Run Tier 3 crawler
  2. Extract PDFs from michigan.gov/mpsc
  3. Ingest & analyze
  4. Note: Michigan was source of some data in prior sessions
- **Priority**: 🟡 MEDIUM (moderate landing page count)

#### **NORTH CAROLINA (NC)**
- **Landing pages found**: 5 (v1 crawl)
- **Deep scrape needed**: Tier 3 crawler
- **Expected PDFs**: 3-8 (estimate)
- **Next steps**:
  1. Run Tier 3 crawler
  2. Extract from ncuc.net
  3. Ingest & categorize
- **Priority**: 🟡 MEDIUM

#### **ILLINOIS (IL)**
- **Landing pages found**: 4 (v1 crawl)
- **Deep scrape needed**: Tier 3 crawler
- **Expected PDFs**: 2-6 (estimate)
- **Next steps**:
  1. Run Tier 3 crawler on icc.illinois.gov
  2. Extract PDFs
  3. Ingest & analyze
- **Priority**: 🟡 MEDIUM

#### **KENTUCKY (KY)**
- **Landing pages found**: 4 (v1 crawl)
- **Deep scrape needed**: Tier 3 crawler
- **Expected PDFs**: 2-6 (estimate)
- **Next steps**:
  1. Run Tier 3 crawler
  2. Extract PDFs
  3. Ingest
- **Priority**: 🟡 MEDIUM

#### **OKLAHOMA (OK)**
- **Landing pages found**: 4 (v1 crawl)
- **Deep scrape needed**: Tier 3 crawler
- **Expected PDFs**: 2-6 (estimate)
- **Next steps**: Same as above
- **Priority**: 🟡 MEDIUM

#### **TENNESSEE (TN)**
- **Landing pages found**: 4 (v1 crawl)
- **Deep scrape needed**: Tier 3 crawler
- **Expected PDFs**: 2-6 (estimate)
- **Next steps**: Same as above
- **Priority**: 🟡 MEDIUM

#### **[REMAINING 15 TIER 3 STATES]**
- **HI, IA, MS, MD, NY, OR, AZ, CA, CT, NV, NJ, NM, ND, UT, WY**
- **Landing pages found**: 1-3 each (v1 crawl)
- **Status**: 📋 QUEUED FOR TIER 3
- **Strategy**: Batch crawl all remaining states in one run
- **Priority**: 🟢 LOW (1-3 documents each; can batch together)

---

### ❌ TIER 3 NO DATA FOUND (3 states)

- **Minnesota (MN)**: 0 documents found (v1 crawl)
- **New Mexico (NM)**: 0 documents found
- **[1 other state TBD]**

**Next steps**: Manual research needed. May not publish audit documents online, or documents buried in portal.

---

## 📊 SUMMARY TABLE

| State | v1 Docs | Tier Found | Status | PDFs | Docs Ingested | Parser Needed | Priority |
|-------|---------|-----------|--------|------|---|---|---|
| TX | 33 | Tier 1 | ✅ Done | 20 | 20 | 🔴 YES | 🔴 HIGH |
| WV | 10 | Tier 1 | ✅ Done | 5 | 5 | 🟡 Maybe | 🟡 MED |
| ID | 3 | Tier 1 | ✅ Done | 3 | 3 | ❓ TBD | 🟡 MED |
| MT | 7 | Tier 1 | ✅ Done | 2 | 2 | 🟢 No | 🟢 LOW |
| WA | 68 | Tier 2 | 🔄 Ingesting | 50 | TBD | ❓ TBD | 🟡 MED |
| IN | 7 | Tier 2 | 🔄 Ingesting | 50 | TBD | ❓ TBD | 🟠 MED-HIGH |
| DC | 6 | Tier 2 | 🔄 Ingesting | 27 | TBD | ❓ TBD | 🟠 MED-HIGH |
| PA | 38 | Tier 2 | 🔄 Ingesting | 13 | TBD | 🔴 YES | 🔴 HIGH |
| GA | 6 | Tier 2 | 🔄 Ingesting | 9 | TBD | ❓ TBD | 🟡 MED |
| ME | 8 | Tier 2 | 🔄 Ingesting | 2 | TBD | 🟢 No | 🟢 LOW |
| [15 more] | <5 ea | Tier 3 | 📋 Queued | est. 3-8 | 0 | ❓ TBD | 🟢 LOW |
| MN, NM, [1] | 0 | None | ❌ No data | 0 | 0 | — | — |

---

## 🚀 NEXT ACTIONS BY PRIORITY

### 🔴 TIER 0 - IMMEDIATE (Now)

1. **Complete Tier 2 pipeline ingestion** (123 documents)
   - **Estimated time**: 10-20 minutes
   - **Success criterion**: data/processed/ count reaches 153+
   - **Owner**: Pipeline daemon (running)

### 🔴 TIER 1 - URGENT (Next session)

2. **Analyze Tier 2 ingested documents**
   - **States**: WA, IN, DC, PA, GA, ME
   - **Action**: Sample 3-5 documents per state
   - **Goal**: Classify document types and audit relevance
   - **Output**: Update this tracking document with actual findings

3. **Build Texas findings parser**
   - **State**: TX
   - **Input**: data/processed/tx_*/report.json (20 documents)
   - **Output**: Extract findings, recommendations, audit types
   - **Success criterion**: 10+ findings extracted from 2+ documents
   - **Estimated effort**: 2-3 hours

4. **Cross-link Texas findings with FERC**
   - **Action**: Match TX audit subjects/companies with FERC audits
   - **Output**: Build company-to-audit mapping
   - **Success criterion**: 5+ cross-links identified

### 🟠 TIER 2 - HIGH PRIORITY (After Tier 1)

5. **Analyze PA documents for audit type**
   - **State**: PA
   - **Action**: Determine if Bureau of Audits format matches FERC parser
   - **Output**: Build PA parser (if audit-focused) or reference-only classification

6. **Build PA findings parser (if audit-focused)**
   - **Estimated effort**: 2-3 hours
   - **Input**: data/processed/pa_*/report.json (13 documents)
   - **Success criterion**: 5+ findings extracted

7. **Analyze IN, DC, WA documents**
   - **Action**: Classify 50+27+50 = 127 documents
   - **Goal**: Identify 10-20 audit-focused documents per state
   - **Output**: Prioritize for parsing

### 🟡 TIER 3 - MEDIUM PRIORITY (If budget allows)

8. **Run Tier 3 crawler**
   - **States**: AK, MI, NC, IL, KY, OK, TN (7 states)
   - **Estimated PDFs**: 5-8 per state = 35-56 total
   - **Estimated effort**: 30-40 minutes
   - **Cost**: ~20K tokens

9. **Validate & ingest Tier 3 documents**
   - **Estimated cost**: ~30K tokens
   - **Success criterion**: 80%+ government source validation

10. **Batch crawl remaining Tier 3 states** (15 low-hit states)
    - **Estimated cost**: ~20K tokens
    - **Expected documents**: 20-40 total (1-3 per state)

### 🟢 TIER 4 - OPTIONAL (Polish)

11. **Manual research on 3 states with no data** (MN, NM, other)
    - **Effort**: 1-2 hours research
    - **Goal**: Determine if they publish audits online at all

12. **Build comprehensive findings database**
    - **Input**: All extracted findings from TX, PA, IN, DC, WA
    - **Output**: Searchable findings index by state/company/audit type

---

## 📌 KEY DEPENDENCIES

```
Tier 2 pipeline completion
  ↓
Analyze WA, IN, DC, PA, GA, ME documents
  ├─ If TX findings viable → Build TX parser (HIGH PRIORITY)
  ├─ If PA findings viable → Build PA parser
  └─ If others → Plan Tier 3 crawl
```

---

## 🎯 SUCCESS METRICS

- **Document count target**: 200+ (153 Tier 1+2 + 50+ Tier 3)
- **State coverage target**: 30+ states with audit documents
- **Findings extracted target**: 50+ initial findings (Texas focus)
- **Cross-links target**: 10+ state findings matched to FERC audits
- **Token budget target**: <400K total (we're at 200K; 200K remaining)

---

**Last updated**: 2026-06-15 (mid-Tier 2 pipeline run)  
**Next review**: When Tier 2 pipeline completes (10-20 min)
