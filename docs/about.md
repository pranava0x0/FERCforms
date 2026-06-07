# About the FERC Audit Explorer

## What is this?

The **FERC Audit Explorer** is a static, public-interest tool that aggregates and analyzes findings from **every published FERC utility audit** — electric (Form 1), gas (Form 2), and oil (Form 6) — issued from 2014 to present. It surfaces **common patterns of noncompliance** and staff recommendations across years, utilities, and sectors, so analysts, journalists, and advocates can spot systemic issues without reading 100+ individual PDFs.

**Key facts:**
- **Source:** Audit reports published at [ferc.gov/audits](https://www.ferc.gov/audits) and the FERC eLibrary
- **Coverage:** ~120 FERC audits + ~80 state PUC audit documents + ~5 FERC formal-challenge/prudence reviews (multi-collection since v1.5)
- **Extraction:** Findings and recommendations quoted **verbatim** from each report's Executive Summary or findings section — no paraphrase, no LLM-judged editorial calls
- **Data is the product:** Every finding carries a source URL and capture date; users can trace any claim back to its original PDF
- **Zero backend:** Static baked JSON + vanilla HTML/CSS/JS, hosted on GitHub Pages. No ads, no cookies, no tracking
- **Open:** Codebase at [github.com/pranava0x0/FERCforms](https://github.com/pranava0x0/FERCforms); data in `docs/data/*.json` and `llms.txt`

---

## Why does this matter?

FERC audits surface the **operational and financial compliance failures** that affect utility ratepayers — improper cost allocations, missing documentation, policy violations. A single audit finding might note "$X million overcharged to customers" or "failure to implement required tariff." But finding those patterns requires reading hundreds of reports individually.

This explorer **structures that corpus** so you can ask:
- *What compliance issues recur across utilities?*
- *Which utilities show the most findings?*
- *What themes carry the largest ratepayer impact?*
- *How has noncompliance changed over time?*

The north-star feature (in development): **"audit my filing"** — given a company's Form 1 or other regulatory submission, flag the issues a FERC auditor would likely raise, using the pattern library mined here.

---

## How to use this explorer

**Read a report:** Click any card to expand its thread — each finding of noncompliance, with the staff recommendations nested beneath, quoted verbatim from the original PDF.

**Spot the trends:** The "Top patterns of noncompliance" strip ranks the issues FERC raises most. Tap one to narrow the stream to reports with that issue.

**Filter & search:** Narrow by industry, FERC form, audit type, function, or year — or type a company or keyword in the Search box. Picks within one filter widen the results; picks across different filters narrow them.

**Trace the source:** Every card links to FERC's original PDF via *View on eLibrary*. All findings are quoted verbatim with a capture date so you can verify the source.

---

## Collections & scope

The explorer now spans **three collections**:

1. **FERC Audits** (~120 reports) — FERC's direct audits of electric, gas, and oil utilities; financial (FA) and non-financial/compliance (PA) types; issued 2014–present.
2. **FERC Prudence Reviews** (~5 reports) — Formal-challenge orders and ALJ decisions on fuel-cost and investment prudence, sourced from the FERC eLibrary.
3. **State PUC Audits** (~80 reports) — Management audits, rate-case testimony, and fuel-cost reviews from state Public Utility Commissions (electric & gas) across 20+ jurisdictions (PA, MI, VA, TX, IL, SC, OH, NJ, MD, DE, KY, IN, WV, DC, GA, LA, MS, AR, MO, MN, WI, CO, CA, NY, KS, UT, CT, RI, NE, TN, ND, SD, WA, OR, ID, AZ).

Each collection has its own browsable tab and baked statistics; all are metadata-only (findings fully quoted with source links) except FERC audits, which have structured findings extraction.

---

## Technical approach

**Data pipeline:**
1. **Source discovery:** FERC eLibrary AdvancedSearch API + browser-captured docket listings for state PUCs (Cloudflare/WAF-blocked sites use Chrome MCP capture).
2. **PDF extraction:** pdfplumber + PyMuPDF for text, OCR fallback (tesseract) for scanned reports.
3. **Structure extraction:** Pattern-matched TOC parsing → findings → recommendations; Pydantic validation with no-regression snapshot tests.
4. **Pattern mining:** Keyword rules + theme tagging for common noncompliance patterns (below-the-line, affiliate, depreciation, AFUDC, cost-of-service, etc.).
5. **Baking:** Static JSON (`docs/data/*.json`) → vanilla JS renderer. No database, no backend.

**Code:** All CLI-driven, agent-verifiable. Re-runs are idempotent and cacheable.

---

## Limitations & scope

- **FERC audits only** — we cover FERC's Form 1/2/6 audits. FERC Enforcement actions (civil penalties, market-manipulation cases) are out of scope (but a planned future module).
- **Historical, not prospective** — we surface *past* compliance failures, not *future* regulatory proposals. For pending rules, see LegiScan or the FERC Notice of Proposed Rulemaking.
- **Extracted findings are a subset** — we parse the Executive Summary and findings sections. Detailed Section IV (dollar impacts, regulatory citations, remediation) is part of each PDF but not yet extracted.
- **State coverage is partial** — we've seeded high-value docs from 30+ states but have not exhaustively harvested all state PUC audit libraries. See [State coverage breakdown](state-coverage.md) for what's here and what's planned.
- **No LLM judgment** — every statement is quoted verbatim. We don't rephrase, score, or invent severity ratings. This trades breadth for trustworthiness.

---

## Related Projects

The FERC Audit Explorer draws inspiration and lessons from these related tools and initiatives in the public-interest data & regulatory transparency space:

### Data Integration & Infrastructure
- **[PUDL (Public Utility Data Liberation Project)](https://pudl.readthedocs.io/)** — Open-source pipeline that aggregates energy data from FERC, EIA, EPA, PHMSA into analysis-ready databases. Covers operational/financial data (capacity, costs, generation). If you want to cross-reference our audit findings against the Form 1 numbers being audited, PUDL is the foundational infrastructure.

### Official Archives & Raw Data
- **[FERC eLibrary](https://elibrary.ferc.gov/)** — Official FERC searchable docket repository. The source for all our FERC audit PDFs and prudence reviews. Upstream of this explorer.
- **[data.ferc.gov](https://data.ferc.gov/)** — FERC's open data catalog. Structured datasets (EQRs, annual reports). Complementary to our findings library.

### Curated Public Datasets & Investigations
- **[ProPublica Data Store](https://www.propublica.org/datastore/)** — Curated, fact-checked datasets from ProPublica's investigative journalism (e.g., IRS audit rates by county, hospital pricing). Demonstrates how to combine journalism + data to surface patterns.
- **[InvestigateWest](https://www.investigatewest.org/)** — Pacific Northwest nonprofit newsroom doing accountability investigations on energy, environment, and public health. Shows how pattern-mining feeds investigative narrative.

### Legislative & Regulatory Tracking
- **[LegiScan](https://legiscan.com/)** — Tracks bills and legislation across all 50 states + Congress. Complementary for prospective (future) regulation vs. our retrospective audit findings.
- **[Ballotpedia Administrative State Index](https://ballotpedia.org/Administrative_State_Index)** — Reference for state and federal agencies and their audit authorities. Good for understanding *which agencies audit*; this explorer shows *what they found*.

### State-level Filing Centers
- State Public Utility Commission dockets (PA PUC, Texas PUCT, Oregon PUC, California CPUC, etc.) — The fragmented filing centers we're systematically harvesting. Each state's system is different, limiting cross-state analysis; that's why we've built unified access.

---

## Data & Citation

**License:** The extracted findings and patterns are available under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) (attribute to this explorer). Source documents (PDFs) remain under FERC's and the state PUCs' respective licenses (typically public domain as government works).

**Cite this explorer:**
```
FERC Audit Explorer. (2026). A browsable analysis of FERC utility audit findings, 2014–present.
Retrieved from https://pranava0x0.github.io/FERCforms/
```

**Machine-readable formats:**
- **[llms.txt](llms.txt)** — Structured plain-text summary of the corpus (OpenAI llms.txt convention)
- **[llms-full.txt](llms-full.txt)** — Full findings-level corpus in llms.txt format
- **[reports.json](data/reports.json)** — Raw structured data (reports + findings + patterns)

---

## Contact & Contributing

This is an independent public-interest tool built to serve analysts, journalists, and advocates. For questions, suggestions, or to report a data error:

- **GitHub:** [github.com/pranava0x0/FERCforms](https://github.com/pranava0x0/FERCforms) (issues, discussion)
- **Data verification:** Every finding is quoted verbatim with a source PDF link. If you find an inaccuracy, open an issue.

**Not affiliated with FERC.** This explorer is an independent analysis tool; it is not an official FERC product and does not represent FERC's views.
