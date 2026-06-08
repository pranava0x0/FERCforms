# Tier 1 State Audit Programs - Research Guide

## Current Status
**Goal**: Add real audit documents from VA, NY, TX, OH (largest utilities, known audit programs)
**Blocker**: Cannot access live PUC portals directly - need browser-based research
**Approach**: Document exact search procedures for manual verification

---

## 1. VIRGINIA SCC - Audit Documents to Find

### Program Details
- **Biennial Fuel Cost Reviews**: Annual audits of fuel purchasing
- **Service Quality Audits**: Compliance with service standards
- **Affiliate Transaction Reviews**: Audits of inter-company transactions
- **Depreciation Studies**: Asset audit reviews

### Target: Dominion Energy Virginia
- Primary electric utility in VA
- 2024-2025 audit dockets available

### How to Find Dockets
1. Visit: **scc.virginia.gov/pages/Dockets-Search.aspx**
2. Search for: "Dominion" + "biennial" OR "audit" OR "fuel" OR "depreciation"
3. Filter for 2023-2025
4. Look for docket numbers like: **PUR-2024-XXXXX** or **PUR-2023-XXXXX**
5. Click docket detail page
6. Find PDF links (document codes like "89g601")

### Example Audit Types to Verify
- "Biennial Review of Electric Base Rates" → Fuel audit
- "Depreciation Study Review" → Asset audit
- "Service Quality Audit" → Compliance audit

### Documents to Seed
Need 2-3 actual audit orders (Final Orders, not rate cases)

---

## 2. NEW YORK DPS - Audit Documents to Find

### Program Details
- **Service Quality Investigations**: Annual utility compliance reviews
- **Utility Complaint Investigations**: Dispute resolutions with audit findings
- **Cost Recovery Audits**: Prudence reviews of utility costs
- **Compliance Examinations**: Regulatory requirement reviews

### Target: Con Edison Company of New York
- Largest utility in NY service area
- Frequent audit/investigation dockets

### How to Find Dockets
1. Visit: **dps.ny.gov/energy/cases**
2. Search for: "Con Edison" + "investigation" OR "audit" OR "compliance"
3. Filter for 2023-2025
4. Look for Case numbers (format varies)
5. Click case to see documents
6. Download PDF from DPS system

### Example Audit Types to Verify
- "Investigation of Service Quality" → Compliance audit
- "Investigation into Affiliate Transactions" → Transaction audit
- "Rate Audit Investigation" → Cost audit

### Documents to Seed
Need 2-3 actual audit investigation orders

---

## 3. TEXAS PUCT - Audit Documents to Find

### Program Details
- **Complaint Dockets**: Utility complaint investigations with audit elements
- **Cost Recovery Audits**: Prudence reviews of cost recovery claims
- **Compliance Investigations**: Regulatory compliance audits
- **ERCOT Disputes**: Market-related compliance investigations

### Target: Oncor Electric Delivery (or CenterPoint)
- Oncor: Largest T&D utility in TX
- CenterPoint: Large distribution utility in Houston

### How to Find Dockets
1. Visit: **interchange.puc.texas.gov/search/filings/**
2. Search for: "Oncor" + "complaint" OR "investigation" OR "audit"
3. Filter for 2023-2025
4. Look for docket numbers (numeric, 5+ digits)
5. Click "documents" tab
6. Find PDF links with pattern: `Documents/{control}_{item}_{docid}.PDF`

### Example Audit Types to Verify
- "Complaint Investigation - Fuel Cost" → Fuel audit
- "Dispute Resolution with Audit" → Compliance audit
- "Cost Recovery Investigation" → Prudence audit

### Documents to Seed
Need 2-3 actual complaint/investigation final orders

---

## 4. OHIO PUCO - Audit Documents to Find

### Program Details
- **Utility Investigations**: General compliance investigations (UNC cases)
- **Service Quality Audits**: Performance/reliability audits
- **Compliance Examinations**: Regulatory compliance reviews
- **Cost Recovery Audits**: Prudence reviews of utility costs

### Target: FirstEnergy Ohio (or AEP Ohio)
- FirstEnergy: Large incumbent utility
- AEP Ohio: Second-largest utility

### How to Find Dockets
1. Visit: **dis.puc.state.oh.us** (Docket Information System)
2. Search for: "FirstEnergy" + "UNC" (investigation) OR "audit" OR "compliance"
3. Filter for 2023-2025
4. Look for case numbers like: **XX-XXXX-EL-UNC** (UNC = Utility Notification Code)
5. Click case detail
6. Find document PDF links (Note: WAF-protected, may need browser capture)

### Example Audit Types to Verify
- Case "20-XXXX-EL-UNC": Investigation dockets
- "Compliance Audit Order" documents
- "Service Quality Review" orders

### Documents to Seed
Need 2-3 actual investigation/compliance audit orders

---

## Next Steps

1. **Manual Research** (Browser Required)
   - Open each state's PUC portal in a web browser
   - Execute search procedures above
   - Identify 2-3 real audit docket numbers per state
   - Find document detail pages
   - Note the exact PDF URLs or document IDs

2. **Verification** (Before Seeding)
   - Download PDF to verify page 1
   - Confirm it's an actual audit (not a rate case)
   - Note doc_type, company, issued_date
   - Record the PDF URL or document ID

3. **Seed Creation**
   - Create seed entries with real URLs/IDs
   - Set `fetch=true` if URL works, `fetch=false` if WAF-blocked
   - Add source_note with docket details

4. **Ingest & Commit**
   - Run `python -m pipeline.sources`
   - Rebuild with `python -m pipeline.build`
   - Commit with clear docket references

---

## Timeline
- **Estimated effort**: 30-60 minutes per state (browser research)
- **Total for 4 states**: 2-4 hours
- **Once complete**: 4-12 new audit documents added (state_audit collection)

---

## Success Metrics
- ✓ Find 2-3 real audit dockets per state
- ✓ Verify documents are actual audits (not rate cases)
- ✓ Add to seeds with proper URLs/IDs
- ✓ Ingest successfully
- ✓ Commit with clear audit docket references
