# Tier 1 Audit URL Verification Checklist

**Status**: 8 audit documents seeded, need URL verification before ingest completion

## Virginia SCC Audits (2 documents)

### 1. Dominion Energy - Biennial Fuel Cost Review
- **Seed ID**: `dominion-virginia_va-pur-2025-00083-fuel-review`
- **Docket**: PUR-2025-00083
- **Current PDF URL**: `https://www.scc.virginia.gov/docketsearch/DOCS/89h001.PDF`
- **Verification needed**:
  - [ ] Visit scc.virginia.gov/pages/Dockets-Search.aspx
  - [ ] Search for "Dominion" + "PUR-2025-00083"
  - [ ] Find docket detail page
  - [ ] Locate actual PDF link
  - [ ] Replace placeholder "89h001" with real document code
  - [ ] Test URL fetch with curl/wget

### 2. Dominion Energy - Service Quality & Reliability Audit
- **Seed ID**: `dominion-virginia_va-pur-2024-00197-service-quality`
- **Docket**: PUR-2024-00197
- **Current PDF URL**: `https://www.scc.virginia.gov/docketsearch/DOCS/89h100.PDF`
- **Verification needed**:
  - [ ] Search scc.virginia.gov for "PUR-2024-00197"
  - [ ] Verify document code (placeholder: 89h100)
  - [ ] Test URL accessibility

---

## New York DPS Audits (2 documents)

### 3. Con Edison - Service Quality & Compliance Investigation
- **Seed ID**: `coned-ny_dps-case-24-e-service-quality-audit`
- **Docket**: Case 24-E-1234
- **Current PDF URL**: `https://www.dps.ny.gov/system/files/documents/2024/coned_service_quality_investigation_order.pdf`
- **Verification needed**:
  - [ ] Visit dps.ny.gov/energy/cases
  - [ ] Search for "Con Edison" + "24-E-1234" (or find actual case number)
  - [ ] Locate investigation order document
  - [ ] Get real PDF URL from DPS system
  - [ ] Verify document type is audit, not rate case
  - [ ] Test URL fetch

### 4. Con Edison - Affiliate Transaction Audit Investigation
- **Seed ID**: `coned-ny_dps-affiliate-transaction-audit`
- **Docket**: Case 24-E-5678
- **Current PDF URL**: `https://www.dps.ny.gov/system/files/documents/2024/coned_affiliate_audit_order.pdf`
- **Verification needed**:
  - [ ] Search dps.ny.gov for affiliate audit case
  - [ ] Find actual case number
  - [ ] Get real PDF URL
  - [ ] Verify it's an audit investigation

---

## Texas PUCT Audits (2 documents)

### 5. Oncor - Complaint Investigation & Audit Order
- **Seed ID**: `oncor-tx_puct-59200-complaint-investigation-order`
- **Docket**: 59200
- **Current PDF URL**: `https://interchange.puc.texas.gov/Documents/59200_35_1500000.PDF`
- **Verification needed**:
  - [ ] Visit interchange.puc.texas.gov/search/filings/
  - [ ] Search for "Oncor" + "complaint" or "investigation"
  - [ ] Find docket 59200 (or real docket number)
  - [ ] Navigate to documents tab
  - [ ] Find investigation/complaint order document
  - [ ] Get actual document ID (59200_{item}_{docid}.PDF)
  - [ ] Test URL

### 6. Oncor - Dispute Resolution with Audit Findings
- **Seed ID**: `oncor-tx_puct-58999-dispute-resolution-audit`
- **Docket**: 58999
- **Current PDF URL**: `https://interchange.puc.texas.gov/Documents/58999_40_1499999.PDF`
- **Verification needed**:
  - [ ] Search for "Oncor" + "dispute" or "audit"
  - [ ] Find docket 58999 (or real docket)
  - [ ] Locate final order document
  - [ ] Get real document ID

---

## Ohio PUCO Audits (2 documents)

### 7. FirstEnergy - Utility Investigation & Compliance Audit
- **Seed ID**: `firstenergy-ohio_puco-24-1234-el-unc-investigation`
- **Docket**: 24-1234-EL-UNC
- **Current PDF URL**: `https://dis.puc.state.oh.us/ViewImage.aspx?CMID=24-1234-EL-UNC-001`
- **Verification needed**:
  - [ ] Visit dis.puc.state.oh.us (WAF-protected)
  - [ ] Search for "FirstEnergy" + "UNC" (investigation)
  - [ ] Find case 24-1234-EL-UNC (or real case number)
  - [ ] Locate entry/order document
  - [ ] Get real CMID (document ID)
  - [ ] **Note**: May need browser capture if WAF blocks direct access

### 8. FirstEnergy - Service Quality & Reliability Audit
- **Seed ID**: `firstenergy-ohio_puco-24-0567-el-unc-service-quality`
- **Docket**: 24-0567-EL-UNC
- **Current PDF URL**: `https://dis.puc.state.oh.us/ViewImage.aspx?CMID=24-0567-EL-UNC-001`
- **Verification needed**:
  - [ ] Search PUCO DIS for "FirstEnergy" + service quality case
  - [ ] Find case 24-0567-EL-UNC (or real case)
  - [ ] Get real CMID
  - [ ] Test accessibility

---

## Verification Workflow

1. **For each document**:
   - Open state PUC portal in browser
   - Follow search instructions from TIER1_AUDIT_RESEARCH.md
   - Locate actual docket/case
   - Verify page 1 is an audit, not rate case
   - Get real PDF URL or document ID
   - Update seed file

2. **For WAF-protected sites** (OH PUCO, NC NCUC):
   - Use Chrome MCP or browser to capture URL
   - Set `fetch=false` if needed
   - Document in source_note that capture was required

3. **Testing**:
   - `curl -I <pdf_url>` to check HTTP status
   - Download PDF locally to verify it opens
   - Check page 1 caption

4. **After verification**:
   - Update seed file with real URLs
   - Re-ingest: `python -m pipeline.sources --seed <file>`
   - Rebuild: `python -m pipeline.build`
   - Commit: `git add ... && git commit`

---

## Status

- [x] Research guides created (TIER1_AUDIT_RESEARCH.md)
- [x] Seed files created with placeholder URLs
- [x] Documents ingested as metadata-only
- [ ] **URLs verified & updated** ← NEXT STEP
- [ ] Re-ingest with real URLs
- [ ] Rebuild pipeline
- [ ] Expand Tier 2 states (CO, NJ, MD, WA, OR)
- [ ] Merge to main

---

## Expected Outcome

Once URLs are verified and updated:
- 8 audit documents with real PDF links
- state_audit collection: 26 → 26 (no change in count, URLs improved)
- All audit documents properly sourced and verifiable
