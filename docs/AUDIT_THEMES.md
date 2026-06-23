# FERC Audit Themes & Noncompliance Patterns

> **Auto-generated from `docs/data/patterns.json`** (regenerate with `python3 -m pipeline.build && python3 -m pipeline.patterns`).
> Every count below is mined directly from the structured corpus — keyword-tagged finding/recommendation
> text, never an LLM editorial call. If a number here disagrees with `patterns.json`, `patterns.json` wins.

**Generated:** 2026-06-22  
**Corpus:** 494 structured reports · 1727 verbatim findings · 2185 recommendations  
**Collections:** ferc_audit 123, prudence_review 29, state_audit 221, state_rate_case 121  
**Themes identified:** 25

---

## Summary

Cross-analysis of 494 historical FERC (Form 1/2/6) audits, FERC prudence orders, and
state PUC audit/rate-case documents surfaces **25 recurring noncompliance themes**. Themes are
assigned by transparent keyword rules (`pipeline/patterns.py` `THEME_RULES`) scanning finding titles and
recommendation text — no paraphrase, no compliance score, no model judgement. A report counts once per
theme regardless of how many of its findings match.

## All themes by frequency

| # | Theme | Reports | Findings | Description | Example finding titles |
|---|-------|--------:|---------:|-------------|------------------------|
| 1 | **Accounting misclassification** | 68 | 182 | Costs or revenues booked to the wrong FERC account. | Prepayments; Accounting Misclassifications; Allowance for Funds Used During Construction |
| 2 | **Form reporting (Form No. 1/2/6, Page 700)** | 58 | 155 | Errors or omissions in the annual FERC forms utilities file. | Prepayments; Excess and Deficient Accumulated Deferred Income Tax; FERC Form No. 1 Reporting |
| 3 | **Fuel & purchased-power cost recovery** | 54 | 28 | Fuel, purchased-power, and energy-cost recovery or prudence matters. | Recovery of Fuel Contract Buyout Costs; Accounting for Fuel Storage and Handling; Auxiliary Fuel Costs in Nuclear Power Generation |
| 4 | **Cost of service & rates** | 47 | 85 | Errors in rate-base or return inputs to cost-of-service rates. | Approval: $1,277,051,206. ; Approval: $35.7 million; Annual Membership Dues |
| 5 | **Depreciation** | 47 | 68 | Unapproved or incorrect depreciation rates applied to plant. | Computation of Depreciation Rates; Allowance for Funds Used During Construction; Depreciation Rates and Study |
| 6 | **Below-the-line costs (lobbying, charitable, etc.)** | 43 | 51 | Non-recoverable costs (lobbying, charity, ads) charged to ratepayers. | Annual Membership Dues; Nonoperating and Operating Expenses; Accounting for Lobbying Expenses |
| 7 | **Property & plant records** | 42 | 76 | Incomplete or inaccurate utility plant and property records. | Allowance for Funds Used During Construction; Prepaid Pension AFUDC; Noncarrier Property Revenue, Expenses, and Net Income |
| 8 | **Affiliate / intercompany transactions** | 40 | 145 | Transactions with affiliated companies mis-priced or mis-reported. | Accounting for Distribution and Meter-Related Costs; Cost Allocations and Affiliated Interests; Settlement: agreement |
| 9 | **AFUDC / cost of capital** | 40 | 53 | Mis-stated AFUDC — the financing cost capitalized during construction. | Allowance for Funds Used During Construction; Capitalization of Vegetation Management Costs; Prepaid Pension AFUDC |
| 10 | **Tariff administration & oversight** | 37 | 63 | Not following the utility's own FERC-approved tariff. | Settlement: Agreement; Renewable Natural Gas Quality Specifications; Tariff Administration and Oversight |
| 11 | **Internal audit & internal controls** | 32 | 32 | Weak internal controls, compliance programs, or internal-audit coverage. | Corporate Governance; Cost Allocations and Affiliated Interests; Affiliated Interests and Cost Allocations |
| 12 | **Capitalization vs. expense** | 21 | 22 | Costs capitalized that should be expensed, or the reverse. | Accounting for Replacement of Minor Items of Property; Capitalization of Vegetation Management Costs; Property Unit Listing |
| 13 | **Service reliability & vegetation management** | 15 | 35 | Electric reliability (SAIDI/CAIDI), outages, or vegetation-management programs. | Capitalization of Vegetation Management Costs; Settlement: terms; Settlement: Agreement |
| 14 | **Customer service & billing** | 14 | 28 | Customer-service performance, billing accuracy, or call-center issues. | Customer Service; Customer Service (continued); Financial Management |
| 15 | **Storm cost recovery & securitization** | 13 | 29 | Storm restoration costs, storm riders/reserves, or securitization. | Approval: $69.8 million; Approval: $78 million; Approval: $85.7 million |
| 16 | **Inventory, materials & fleet** | 13 | 20 | Inventory accuracy, materials management, or fleet/vehicle management gaps. | Auxiliary Fuel Costs in Nuclear Power Generation; Purchasing and Materials Management; Accounting for Materials and Supplies |
| 17 | **Workforce, training & succession planning** | 12 | 34 | Staffing, training, span-of-control, or leadership-succession shortcomings. | Executive Management, Organizational Structure, and Safety; Human Resources and Diversity (continued); Cost Allocations and Affiliated Interests |
| 18 | **Emergency preparedness & business continuity** | 11 | 14 | Weak emergency response, storm readiness, or business-continuity planning. | Emergency Preparedness; Emergency Preparedness (continued); 2. s |
| 19 | **Membership dues & industry associations** | 11 | 11 | Trade-association dues (e.g., EEI) improperly charged to ratepayers. | Annual Membership Dues; Accounting for Edison Electric Institute Membership Dues; Industry Trade Association Dues |
| 20 | **Information technology & systems** | 10 | 14 | IT governance, systems, budgets, or project-management deficiencies. | Approval: $156.9 million; Information Technology; s .................................................................................................................... 424 |
| 21 | **Informational postings** | 9 | 15 | Required public postings (e.g., OASIS) missing, late, or incomplete. | Renewable Natural Gas Quality Specifications; Informational Postings; Public Access to Monthly and Yearly Capability Information |
| 22 | **Cybersecurity & physical security** | 8 | 20 | Gaps in cyber defenses or physical security of facilities and systems. | Emergency Preparedness; Emergency Preparedness (continued); s .................................................................................................................... 461 |
| 23 | **Dividend policy & capital management** | 6 | 8 | Dividend-policy or capital-management practices flagged by auditors. | Financial Management; s - - Dividend Policy and Capital Structure ................................................... 78; s - - Dividend Policy and Capital Structure ....................................................... 78 |
| 24 | **Gas safety & pipeline integrity** | 3 | 3 | Gas leak backlogs, corrosion control, or pipeline-integrity practices. | Electric Operations; Gas Operations |
| 25 | **Creditworthiness** | 2 | 2 | Customer credit standards not applied as the tariff requires. | Creditworthiness Standards; Settlement: Agreement |

## Coverage & provenance

- **Reports:** 494 structured (260 electric, 42 gas, 18 oil by identified industry signal).
- **Collections:** FERC audits 123, prudence reviews 29, state PUC audits 221, state rate cases 121.
- **State reach:** 342 state-level records across 45 jurisdictions.
- **Issuance years (where dated):** 2005–2026; recent volume — 2022:21, 2023:26, 2024:46, 2025:65, 2026:8.
- **Source attribution:** every record carries a `source_note` + source URL + capture date; FERC-audit
  findings are extracted verbatim, state audits are listed for reference (metadata-only) unless a gated
  parser exists (PA Exhibit I-2, NJ).

## Methodology notes

- **Keyword-tagged, not LLM-judged.** Themes come from `THEME_RULES` substring matches; adding/renaming a
  theme is a code change with tests (`tests/test_themes.py`), not a prompt.
- **Verbatim quotes.** Example titles and all findings preserve exact report language.
- **Dedup by report.** A report with 5 matching findings counts as 1 report for the theme, 5 for findings.
- **Metadata-only records contribute to corpus + collection counts but not to theme finding-counts** (no
  extracted finding text to match) — so theme tallies track the *parsed* findings universe, not raw report count.

