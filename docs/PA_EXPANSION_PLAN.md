# PA PUC M&O Audit Expansion Plan

## Current Seeded Audits (9 M&O + 1 MEI = 10 total)

All with `parse=True` for findings extraction:

### Electric Utilities
- **PPL Electric Utilities** (2024-07)
- **PECO Energy** (2022-08)  
- **FirstEnergy PA Companies** (2022-06) — covers Met-Ed, Penelec, Penn Power, West Penn Power
- **Duquesne Light** (2019-07)

### Gas Utilities
- **National Fuel Gas Distribution** (2024-11)
- **Peoples Natural Gas** (2021-05) — covers Peoples Gas, Peoples NG
- **Columbia Gas of Pennsylvania** (2020-07)
- **UGI Utilities** (2019-10)

### Mixed Utility
- **Philadelphia Gas Works** (2023-03)

### Management Efficiency Investigation
- **FirstEnergy PA Companies** (2025-09) — MEI instead of M&O

## Coverage Gaps

**Major utilities potentially without recent audits:**
- Equipower (smaller independent generator)
- Susquehanna Electric Company
- Pike County Light & Power
- Equitable Gas Company (if still operating)
- Various municipal electric systems

## Next Steps

1. **Scrape PA PUC press releases** (https://www.puc.pa.gov/press-release/) for "management and operations audit" or "management efficiency investigation" terms
2. **Filter for energy companies only** (exclude water, wastewater, telecommunications)
3. **Verify against existing seeds** (deduplicate by URL)
4. **Download & verify page-1 caption** via browser or cached snapshot
5. **Seed with metadata** (follows existing format in data/seeds/pa_puc.json)
6. **Run pipeline.sources** on new seeds
7. **Commit per-batch** (5 new audits = 1 commit)

## Expected Yield

~3-5 additional PA M&O audits based on historical PUC audit cadence (typically 1–2/year for major utilities). Each audit adds 10–50 findings depending on the audit scope and parser coverage.

## Parser Status

The PA Exhibit-I-2 parser (in `pipeline/state_structure.py:parse_pa_exhibit_i2_findings`) handles both known layouts (PPL/PECO style and NFG variant). New audits should parse successfully without modifications unless a utility uses a novel format (would require new variant handler).

See `docs/pa-findings-parser-plan.md` for parser technical details.
