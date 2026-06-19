# Backlog

Ideas, features, enhancements. Each item: brief description + priority (**low / med / high**). Reprioritize periodically; demote stale "high" items rather than letting them rot.

---

## ▶ Done 2026-06-18 — PA M&O expansion (+4 audits, +29 findings) + 2 data-integrity fixes

**+4 verified PA PUC Bureau-of-Audits docs** (all page-1-caption-verified, PROVEN by `verify_sources`):
two **Management & Operations audits** parsed into findings via the existing Exhibit I-2 parser —
**Pike County Light & Power / Leatherstocking Gas** (1886204, 10 findings/25 recs) and
**Citizens' Electric / Wellsboro Electric / Valley Energy** (1648244, 4/5); plus two 2023
**Management Efficiency Investigations** (Duquesne Light 1799646, UGI Utilities 1785721) kept
**metadata-only** because they use an Exhibit II-1 follow-up format the M&O parser doesn't handle.
Corpus baked 655 reports / 1715 findings.

**Two pre-existing bugs surfaced + fixed** (see ISSUES.md): (1) the **PGW M&O seed pointed at the wrong
pcdocs id** (a Koloko Transportation data-request letter) — corrected to the real 95-page audit
`1775875.pdf`, restoring **11 findings/32 recs**; (2) **`verify_sources` crashed** on the non-list
`tier3_targets.json` planning file — added a shape guard + regression test.

**MEI Exhibit II-1 parser — assessed 2026-06-19, NOT a cheap win → deferred [low].** Examined the
extracted text of both MEIs. The Exhibit II-1 "Summary of … Recommendations and Follow-Up Findings"
is a **3-column table** (prior-audit rec | MEI follow-up finding `III-1 – …` | MEI follow-up rec)
that linearizes per row as `col1 → label+col2 → col3`. The col2/col3 boundary is **unmarked**: when
col3 is "None" (≈32 of 46 rows) it terminates cleanly, but the ~14 rows carrying a real new
recommendation merge col2+col3 (and bleed into the next row's col1) with no delimiter — three cells
concatenated, unrecoverable as clean verbatim. The `{ROMAN}-{N}` labels also appear in the TOC/List
of Exhibits as *exhibit* numbers, so they can't anchor rows without strict body-only scoping. Net
yield (~14 recs across 2 docs) doesn't justify a fragile parser that would garble per the verbatim
discipline. **Both MEIs stay metadata-only.** Revisit only if many more MEIs accumulate AND a
layout-aware (column-bbox) extractor replaces the linear-text one. New **M&O** audits (clean
Exhibit I-2, one rec per row) remain the cheapest reliable findings.

---

## ▶ Done 2026-06-19 (cont.) — +4 verified SC PSC Duke fuel-prudence docs

Added 4 page-1-verified, PROVEN metadata-only SC PSC records (all `dms.psc.sc.gov`, plain-GET
`/Attachments/{Order|Matter}/{guid}`): the annual **fuel-cost reasonableness** proceedings for the
two Duke utilities (we already had Dominion SC 2024-2-E) — **Duke Energy Carolinas 2024-3-E** Order
2024-727 (30 pp) + ORS audit-staff testimony (25 pp); **Duke Energy Progress 2024-1-E** Order 2024-500
(58 pp) + ORS proposed order (25 pp). Corpus 646 → **650**. Same proceeding exists annually for both
Duke utilities + Dominion if more breadth wanted. **NC NCUC** (Duke E-7/E-2 fuel riders) stays
browser-walled (`starw1.ncuc.gov` 403s scripts). **GA PSC** fuel orders (FCR-26/27) are **image-only
scans with no extractable text** — fetchable but can't be caption-verified per the quote discipline;
need OCR before seeding.

---

## ▶ Done 2026-06-19 (cont.) — +5 verified thin-state docs (NM/DE/NE/KS/SD)

Added 5 page-1-verified, PROVEN metadata-only records to under-covered states (each fetched 200 +
%PDF, page counts confirmed): **NM** PNM rate-case Recommended Decision (22-00270-UT, 384 pp, new
`nm_prc.json`), **DE** Delmarva Order No. 8589 (13-115, 163 pp), **NE** Black Hills NG-109 rate order
(14 pp), **KS** Evergy winter-storm **fuel-prudence Staff audit report** (21-EKME-329-GIE, 134 pp —
a 2nd doc in an existing docket, the substantive auditor report alongside the seeded stipulation),
**SD** NorthWestern EL23-016 amended settlement order (2 pp). Corpus 641 → **646** reports.
The parser-ready *findings* seam (PA Exhibit I-2, Overland "Comprehensive Listing") is confirmed
exhausted for scriptable `.gov` access — a research pass found the remaining Overland findings-rich
audits (NY NYSEG/RG&E 2018 ~81 recs, ME Versant) are behind JS portals needing browser capture; and
the Overland house format is per-chapter prose, not the consolidated listing, on most reports.

**[low] Orphan MS MPUS annual-report records lack a seed + source URL.** `data/processed/2024-06-30…`
and `…2025-06-30_mississippi-public-utilities-staff_ms-annual-report` exist (20/27 pp, baked) but have
**no seed file and `pdf_url: null`** — they can't be re-ingested or verified. The real 2024 URL is
`psc.ms.gov/sites/default/files/2024-MPUS-Annual-Report.pdf` (verified; the 2025 follows the same
pattern — confirm before seeding). Recreate a small `ms_psc.json` with proper metadata for both so
they're regenerable + provenance-complete. Fold into the crawler-seed quality audit below.

---

## ▶ Done 2026-06-19 — MEI parser assessed (deferred) + 14 crawler-junk records purged

Assessed the MEI Exhibit II-1 parser (see the dated note above — deferred [low], 3-column boundary
is unrecoverable from linear text). PA M&O corpus confirmed **exhausted** for the clean Exhibit I-2
format (a research pass verified all qualifying audits are already seeded; older 2008-2016 cycles use
a contractor "Stratified" format with no I-3 recs table). Then ran `verify_sources` and **removed 14
DEAD records** — crawler false-positives (AK traffic-crash page, GA website assets, MS PSC homepage)
and unresolved MS/LA/TX placeholders (`pdf_url` = a docket-search page; `source_note` = "requires
manual docket search"). All 0-page/0-finding. Corpus 655 → **641** reports, findings unchanged (1715).
See ISSUES.md.

**[med] Crawler-seed quality audit — `state_puc.json` (197) + `state_puc_tier2_extended.json` (143).**
These two tier-1/tier-2 web-crawl seed files are the junk source (the 14 DEAD all came from here or
their per-state offshoots). `verify_sources` still shows **NON_PDF=150** — records whose URL returns
200 but isn't a PDF; some are intentional (CA `.htm` decisions, OH/NC browser-capture `fetch=false`),
but the crawler ones point at HTML landing/index pages and several survivors are off-theme by name
(media advisories, fact sheets, eFiling memos). Do a per-record pass over these two files: keep only
records that (a) are genuine utility audit/prudence/rate documents AND (b) resolve to a real fetched
PDF or a deliberately-captured `.htm`/`fetch=false` source; drop nav-link/website-asset/placeholder
rows. Guard against regression by tightening the crawler or adding a seed-quality test (e.g. reject a
`pdf_url` that is a search/`?`-query or directory index for `parse`/`fetch` records).

---

## ▶ CURRENT STATUS — 2026-06-08

**Corpus (verified real):** 290 documents — 120 FERC audits + 26 prudence reviews + 35 state PUC audits + 109 state rate cases. ~1168 findings. State PUC Audits span **12 jurisdictions** (PA NJ NY CA OH MD MI CT MO MS TN UT) and the tab now surfaces **13 patterns of noncompliance** (was 1) mined from the parsed M&O-audit recommendations. Source of truth: `docs/data/meta.json`.

**Done this session (findings extraction):** Built an Overland Consulting parser (`parse_overland_recommendations`) for the NJ PSE&G affiliate/management audit’s "Comprehensive Listing of All Recommendations" → **17 findings / 61 verbatim recs** (868 pp). Investigated the other 12 large metadata-only audits: the Liberty Consulting docs (NJ JCP&L/ACE/NJNG, MI ×4) and the IL/CT orders have NO consolidated recommendation list — recs are prose-embedded ("We recommend …") and would garble if force-parsed, so they stay metadata-only (per the quote discipline). 1234 findings total.

**Done this session (multi-state expansion wave 2, all verified):** +14 net real records via a 2nd parallel-agent wave (VA SCC biennial/fuel, IL ICC Peoples-Gas management-audit order + Nicor PGA, IN IURC FAC/GCA, MN OAH ALJ reports, WI PSC fuel reconciliations, GA Vogtle construction-monitoring, PA Peoples 2021 M&O audit → 13 findings/47 recs). 3 agent-found duplicates of existing records caught + removed; added `test_committed_seeds_have_unique_pdf_urls` (same-URL dedup guard) and a no-clobber guard in `pipeline.sources` (fired 6× preventing re-runs wiping ComEd/MN/IN findings). Corpus → 290 records, 1217 findings.

**Done this session (multi-state expansion wave 1, all verified):** +17 real state audits/prudence orders via parallel research agents (each candidate independently re-fetched + page-1-caption-verified before seeding): NY DPS M&O orders + Central Hudson billing investigation (3); NJ BPU affiliate+management audits PSE&G/JCP&L/ACE/NJNG (4, 326–868 pp); CA CPUC Balancing-Account audits + ERRA decision (3); OH PUCO Daymark/Blue Ridge audits (2, `fetch=false`/Wayback-verified); MD BGE gas-safety order (1); WA UTC power-cost/hedging prudence orders (4). Pattern mining expanded to scan recommendation text (state M&O audits have generic functional-area titles) + 10 new THEME_RULES; `verify_sources` false-positives fixed (accession + browser-captured → CHECK, not DEAD/NON_PDF).

> **⚠️ 2026-06-08 — removed 70 FABRICATED records** (invented dockets + guessed URLs, `fetch=false`, never verified). They had inflated the count to a phantom 322. See ISSUES.md + AUDIT_STATUS.md. The old "322 / 73 state audits" numbers below are pre-cleanup and wrong.

**Done this session (real-expansion, all verified):**
- ✅ **MI Liberty distribution audits (4)** now fetched — added an honest-first browser-UA fallback to `fetch_doc` (informative UA first, browser UA only on 401/403). Consumers/DTE part1+2, 487 pp total, fully text-extractable. (was 0-page stubs)
- ✅ **PA M&O audits +2 with findings** — PECO Energy (7 findings/22 recs) + National Fuel Gas Distribution (11/23). Generalized the Exhibit-I-2 parser to handle NFG's "III Title"/"IV – 1"/Exhibit-I-3 variant without regressing the 4 existing.
- ✅ **Real rate cases restored** — IL ComEd P2024-0087 + Ameren, LA SWEPCO, NJ ACE (all fetch=true, real page counts).
- ✅ **Fabrication + phantom guards** — `pipeline.verify_sources` live sweep; offline tests for placeholder/future-date, FERC-listing trace, and **git-tracked report.json** (the gitignore-phantom trap).

## FERC Form 1 Analysis (2026-06-15 plan)

**[HIGH] Scope: Add time-series financial analysis, Part-101 account mapping, and deterministic error-flag engine to surface rate-base anomalies against audit findings.**

✅ **Phase 0 COMPLETE (2026-06-15):** Download path verified. See `docs/FORM1_PHASE0_RESULTS.md` for full findings.

**Key discovery:** Access confirmed at `https://forms.ferc.gov/` (Cloudflare-bypassed). Download mechanism identified: `forms.ferc.gov/DownloadFile.aspx?FileID={id}` (302 redirect). Both `.DBF` (pre-2021) and XBRL (2021+) formats available. **No blockers.** Recommended next: browser-capture Form 1 2023 for 1 utility (PG&E) to extract FileID pattern + validate DBF parsing.

**Remaining phases:** Phase-1 (browser-capture + DBF parse validation) → Phase-2 (time-series ETL) → Phase-3 (error-flag engine).

This leverages the **602 audit findings** we already hold as ground truth; the work is mostly ingesting Form 1 data + joining to assets we have. Three asks:

1. **Time-series rate inputs** (medium effort): ingest N years/utility; extract rate-base + COS schedules (Form 1 pages 110-117, 320-351, 930.2); per-utility time series + YoY anomaly flags.
2. **Stated reasoning per field** (structural + case-specific): Part-101 USoA (18 CFR 101) mapping + join state rate-case testimony for case-specific treatment; surfaces cost classification disputes.
3. **Error-flag engine** (high ROI): deterministic rules seeded by the 13 themes + **validated against 602 findings**:
   - Below-the-line leakage: flag Account 426.x / EEI dues in rate rollups (53 + 11 findings → top yield).
   - Ratio/anomaly: AFUDC rate, depreciation rate, affiliate charges, capitalize-vs-expense, YoY spikes (62 + 46 + 34 findings).
   - Reporting-consistency: Page 700 ↔ Form 1 cross-foots (183 findings).

**Phased path:** ✅ Phase-0 (verify download path) → Phase-1 (Part-101 table) → Phase-2 (time series) → Phase-3 (flag engine, validated against audit findings). See `docs/form1-analysis-plan.md` and `docs/FORM1_PHASE0_RESULTS.md` for details. **Owner:** high-value, deterministic, ground-truth-backed (never speculative).

**Note:** Form 1 is FERC wholesale; retail rate cases are state — state findings + Form 1 anomalies together give the full picture.

---

## High-Impact Next Work — Detailed Phased Plans

### 2. PA Audit Expansion (2 hours, HIGH priority)

**[HIGH] Scope: Add 3–5 new PA M&O audits, expected 30–100 findings.**

See detailed plan: `docs/PA_AUDIT_EXPANSION_PHASED_PLAN.md`

Current: 9 M&O + 1 MEI seeded, all with parse=True, covering major electric + gas.  
Target: Identify 3–5 additional utilities not yet seeded.  
Method: Scrape PA PUC press-release archive; verify page-1 captions; seed + parse.  
Parser: PA Exhibit-I-2 ready (both layouts working, no regressions).  
Success: 3–5 audits → 30–100 findings, zero test regressions, 1 commit.

**Phases:**
1. Discovery (30 min): Scrape PA PUC press releases for candidate audits
2. Verification (30 min): Page-1 caption checks
3. Seed & Parse (1 hour): Add to data/seeds/pa_puc.json, run pipeline.sources
4. Commit & Docs (15 min): Single commit + documentation

---

### 3. Scale to 3 New States (5 hours, MEDIUM priority)

**[MEDIUM] Scope: Expand Deep South coverage — Louisiana, Mississippi, Arkansas. Target 9–15 new documents, 50–150 findings.**

See detailed plan: `docs/SCALE_THREE_STATES_PHASED_PLAN.md`

**Target states (recommended cluster):**
- **Louisiana (LPSC):** 3–5 docs (fuel-cost reviews, Entergy audits)
- **Mississippi (MPSC):** 3–5 docs (MPLS/Dominion audits, rate cases)
- **Arkansas (APSC):** 3–5 docs (Entergy AR, Empire District)

**Rationale:** Adjacent utilities (multi-state footprint), high regulatory activity, minimal current coverage (high value), similar to existing corpus.

**Method:** Per-state 1.5-hour cycles:
1. Discover 3–5 high-value docs (audits + fuel-cost orders)
2. Verify page-1 captions (official .gov sources only)
3. Seed + run pipeline.sources
4. Spot-check extraction quality

**Success:** 9–15 new docs, 50–150 findings, 3 state-specific commits, full pipeline green.

---

### 4. MI Liberty Findings Parser Refinement (3.5 hours, MEDIUM-LOW priority)

**[MEDIUM-LOW] Scope: Extract true audit findings instead of chapter headers. Quality improvement +10–20 findings.**

See detailed plan: `docs/MI_PARSER_REFINEMENT_PHASED_PLAN.md`

Current: 4 MI audits extract 22 findings (mostly chapter/section headers, not audit findings).  
Root cause: Regex patterns capture structural markers instead of true audit findings.  
Goal: Identify real "Finding N:" markers in text; extract substantive findings ("The utility did not..." style).

**Phases:**
1. Document Analysis (45 min): Understand MI audit structure, find true-finding markers
2. Regex Refinement (1.5 hours): Update parse_mi_findings(); add unit test
3. Re-extraction (1 hour): Run updated parser on all 4 MI audits
4. Testing (30 min): Full pipeline + test suite validation
5. Commit (15 min): Clean commit with improved data quality

**Success:** MI findings now extract meaningful audit content, finding_count reasonable (5–10 per audit), zero regressions, 1 commit.

**Optional expansion:** Apply same method to NJ Liberty audits (4 docs, currently metadata-only) → additional 50–100 findings.

---

## Scale to Full State Coverage — Strategic Plan (2026-06-15)

**[MEDIUM] Scope: Systematically expand from sampling few docs per jurisdiction to exhaustive per-jurisdiction coverage.**

Current state: ~35 state PUC/audit docs across 12 jurisdictions (mostly 2-5 docs/state for validation). Full coverage would mean:

1. **Per-jurisdiction audit census** — gather all available state audit reports (M&O, rate-case, prudence, affiliate) per regulator/state. Start with the 12 we touch: PA (bureau press releases), MI (MPSC news), CA (CPUC decisions index), NJ/OH/MD/CT/NY/MO/MS/TN/UT.
2. **Targeted rate-case sampling** — not *all* rate cases (too many), but 3–5 high-value ones per state: (a) contested fuel-cost/prudence, (b) base-rate reset with affiliate scrutiny, (c) tariff/cost-recovery dispute. Filter for relevance to audit themes.
3. **Access map maintenance** — per-regulator web recipes in `docs/data-sources.md` (already started: CA CPUC, TX PUCT, IL ICC, SC PSC patterns documented). Extend to cover OK, MA, NH, WY, HI, VT, ME, AL, NM, NC, IA (the "walled" states requiring browser-capture or alternative sources).
4. **Verify→seed→ingest→commit workflow** — a repeatable agent-driven cycle (proven in prior sessions) to onboard new docs: (a) agent finds candidate, (b) verify against official source (page-1 caption), (c) seed with metadata, (d) run pipeline.sources, (e) commit per-state with provenance.

**Effort estimate:** ~2–3 docs/state × 50 states = ~150 new seeds; phased per regulator (do 5 at a time). **Owner:** bulk-ingest, pattern-scalable. **Priority:** medium (corpus depth matters for pattern confidence; breadth matters for "audit-my-doc" coverage).

**Governance:** all .gov sources only; metadata-only for non-PDF legal docs; `pipeline.verify_sources` before commit (guards against fabrication).

---

**Remaining real-expansion work (only REAL, verified docs — never fabricate; run `python -m pipeline.verify_sources` before committing):**
- **[high] More PA Bureau of Audits M&O audits** — the parser now handles both layouts, so each new one is cheap findings. Energy-scope only (skip water cos). Find via the PUC press-release archive → `pcdocs/{id}.pdf`. NY DPS focused-operations audits next (DMM guids + caption verify).
- **[med] Browser-capture genuinely-walled states** (no real data at all now): OK, MA, NH, WY, HI, VT, ME, AL, NM, NC, IA — per-state walls in docs/data-sources.md. The new browser-UA fallback may unblock some (try first).
- **[low] Browser-confirm 2 OH FirstEnergy 20-1502 records** — real but the F5 WAF blocks script re-verification (CMIDs authentic, provenance documented).

---

**[STALE — pre-2026-06-08-cleanup, kept for history]** Corpus: 322 documents, 46 states/territories, 120 FERC audits + 7 prudence + 73 state audits + 115 rate cases + 7 prudence orders.

**Latest work (extraction pipeline complete - session fix):**
- ✓ Fixed `pipeline.extract` --limit to filter before limiting (was taking first N from all docs) — commit 47fc000
- ✓ Fixed PDF lookup: try {id}.pdf before {accession_number}.pdf — commit 57aa78c  
- ✓ Fixed seed document loading in extract.main() — commits 127749d, 34757f6
- ✓ Chunked extraction strategy fully working with --limit N
- ✓ 222 text.json files extracted (39 more than session start, +5% corpus)
- ✓ 239 documents structured (up from 172)
- ✓ 44 rate cases with regulatory findings (up from 25)
- ✓ 3 state audits with findings (first-time extraction)

**Tests added & passing (95 total):**
- test_extract_limit_fix.py — validates --limit applies to documents needing extraction, not the full list
- test_extract_pdf_lookup.py — validates PDF filename lookup order ({id}.pdf before {accession_number}.pdf)
- test_extract.py — validates extraction coverage across all documents (FERC + seeds)

**Status:** Extraction pipeline now working end-to-end for seed documents. Rate Cases and State Audits tabs now display real findings.

---

> ## ▶ RESUME HERE — paused 2026-06-02 (PJM + prudence + queued asks)
>
> **Where the corpus is:** 196 records on `main` — **120 FERC audits**, **7 prudence reviews**, **69 state PUC audits across 22 jurisdictions** (incl. **expand-within-existing** work begun: +2 MO Ameren FAC docs — Staff surrebuttal on the FAC sharing mechanism (ER-2011-0028) + Commission FAC true-up order (EO-2022-0027); full next-run roadmap in the *State-PUC roadmap* section below) (PA MI VA TX IL SC OH NJ MD DE KY IN WV DC GA LA MS AR MO MN WI + **CO** — Public Service Co. of Colorado/Xcel sampler: electric rate-case advice letter (22AL-0530E) + electric decision (24AL-0275E) + gas rate hearing transcript (22AL-0046G); `dora.state.co.us` E-Filings, recipe in [docs/data-sources.md](docs/data-sources.md). Deeper CO testimony sets need the docket→filing→document 2-level walk) — incl. **Ameren Missouri Staff prudence reviews** added to MO: the Tenth FAC Prudence Review (EO-2024-0053) + Taum Sauk construction audit (ER-2011-0028), via `efis.psc.mo.gov`. **IA deferred** — efs.iowa.gov WAF-403s all non-browser clients (browser-capture + `fetch=false` next; MidAmerican RPU-2023-0001). **WI** — PSCW ERF: We Energies Very Large Customer/data-center tariff (Sierra Club testimony) + NSPW 4220-UR-127 + MGE 3270-UR-125 rate-case testimony; `apps.psc.wi.gov/ERF`, recipe in [docs/data-sources.md](docs/data-sources.md)). **MN** — Northern States Power/Xcel: ALJ report in the gas rate case (G002/GR-23-413) + ALJ findings on the 2023 electric fuel forecast (E-002/AA-22-179); `mn.gov/oah` PDFs since eDockets is WAF-walled, recipe in [docs/data-sources.md](docs/data-sources.md)). **MO** — Empire District Electric/Liberty 2024 rate case ER-2024-0261, 3 MoPSC Staff direct-testimony panels; `efis.psc.mo.gov` EFIS, recipe in [docs/data-sources.md](docs/data-sources.md). MO gold for later: Ameren Missouri FAC **prudence reviews** (EO-… cases) + the Ameren large-load/data-center tariff docket). First MISO-Midwest state; **AR** — Entergy Arkansas 2025 Rider FRP, Docket 16-036-FR: EAL application + Staff evaluation-report testimony + **Order No. 74** (Dec 12 2025); `apps.apsc.arkansas.gov` olsv2, recipe in [docs/data-sources.md](docs/data-sources.md)). Deep South sweep done **except AL** (psc.alabama.gov = scanned minutes + stale URLs + no clean per-utility orders → deferred, needs OCR/browser; recipe noted). GA = Georgia Power 2025 IRP (Docket 56002); LA = Entergy U-36959 FRP + Lake Charles prudence review; MS = MPUS staff annual reports (per-utility InSite docs cert-blocked → Kemper/$300M Grand Gulf are browser-capture targets). All gov-sourced (a corpus-wide test guards it); a `test_is_official_gov` case now asserts the new GA/LA/MS/AR hosts. Per-finding `source_page` shipped; `llms.txt` grouped by collection w/ grounded insights.
>
> **Session learnings already folded in** (see [docs/data-sources.md](docs/data-sources.md) for the per-regulator access map): the **UA no longer carries a `python-requests` token** (WV's IIS filtered it; `config.USER_AGENT`); the **eLibrary AdvancedSearch JSON API is cracked** (docket in `searchText`, accession in the typo'd `acesssionNumber`) — unblocks prudence discovery; the **gov-guard admits a narrow `.org` allowlist** (`_OFFICIAL_GOV_ORG_DOMAINS = {dcpsc.org}`, user-approved). All agent-sourced citations were **verified against the source PDFs** (MAPP ¶61,156 corrected; everything else confirmed).
>
> **QUEUED for the next session (user asks, not yet built):**
> 1. **CSV export** of files + findings → `docs/data/*.csv` (one row per finding/rec w/ provenance), **linked from `llms.txt`**. A `pipeline.build` step; add tests.
> 2. **Deep South + MISO states** — a few on-theme docs each (rate cases / fuel-cost reviews) for AL, MS, LA, GA, AR + other MISO-footprint states; same verify→seed→ingest→commit-per-state workflow. (MISO ROE complaint dockets also feed the prudence backlog.)
> 3. **FERC Form 1 raw-data analysis** — the big strategic eval is written up in [docs/form1-analysis-plan.md](docs/form1-analysis-plan.md) (3 asks: time-series of rate inputs; per-field reasoning via the Part-101 USoA; a flag engine validated against our 602 findings). Gated on a Phase-0 download-path check.
> 4. **NC NCUC** (Cloudflare — browser-capture + `fetch=false`, like OH) and **TN** (mostly TVA/federal — thin, low priority) to finish the PJM set.
> 5. **Phase 2 — "get all docs across states"**: scale each state from the validation few to full coverage.
> 6. **3 prudence candidates to pin** (NETO Opinion 531 `EL11-66`, MISO Opinion 569 `EL14-12`, NCEMC `EL18-192`) — consolidated dockets don't resolve cleanly via `searchText`; pin the order accession by date+description or browser, then seed.
> 7. **[DONE 2026-06-02] Moved all Clean Water Act content out of this project.** `docs/cwa-data-center-enforcement.md`, the `llms.txt` "Optional" link, its generator code in `pipeline/llmstxt.py`, and the BACKLOG "External research — CWA" section have all been removed and `llms.txt`/`llms-full.txt` rebuilt (done by `claude/sharp-euler`, the worktree that originally introduced it). The research was relocated to the separate **Data Center Water Use Tracker** project. The deep-research cost guardrails in `CLAUDE.md`/`AGENTS.md` were intentionally kept here — they're general tool-cost discipline, not CWA content.
>
> ---
>
> ### (historical) multi-source expansion — phase 1–3 (paused 2026-06-01)
>
> **Goal:** add FERC prudence reviews + state PUC/PSC/SCC audits (VA, OH, MI, IL, TX, SC, PA, NC) as new tabs. Get 3–5 docs/source to validate, then collect all. **Official `.gov` sources ONLY** (user constraint — enforced in `pipeline/sources.load_seed`, raises on non-gov). Non-fitting legal docs are **metadata-only** (source link + provenance, `structured=False` → "Listed for reference"; no findings parse, no LLM).
>
> **DONE & committed (phase 1 — 5 commits on this branch):** 3 tabs (FERC Audits / Prudence Reviews / State PUC Audits), each with own baked stats/patterns (`docs/data/patterns_by_collection.json`). Sources: **PA** (4 PA PUC Bureau of Audits), **MI** (4 Liberty Consulting U-21305), **FERC prudence** (5 eLibrary formal-challenge/ALJ orders 2015–2025). Tabs = 120 / 5 / 8 (State PUC → 13 VA → 17 TX → 21 IL → **24 SC; phase 2 complete**, below). Pipeline: `pipeline/sources.py` ← `data/seeds/*.json`; `python -m pipeline.sources --seed <file>` then `python -m pipeline.build`.
>
> **DONE (phase 2) — VA SCC shipped (commit `3d2fe3e`).** 5 Virginia SCC orders, metadata-only, each page-1-read & labelled: biennial review `PUR-2025-00058` (89g601), Rider T1 transmission RAC `PUR-2025-00076` (873b01), Rider DIST distribution RAC `PUR-2024-00137` (816l01, an Order for Notice & Hearing), Appalachian net metering `PUR-2024-00161` (87nd01), Chesterfield CPCN+Rider CERC `PUR-2025-00037` (89g501). Dominion ×4 + APCo ×1; tab now **13**. `data/seeds/va_scc.json`. **Gotchas for the next state:** (a) bare `scc.virginia.gov` **307-redirects to `www.scc.virginia.gov`** — seed the `www.` URL so the fetch doesn't bounce; (b) the SCC DocketSearch **search API is a hash-routed SPA, not curl-resolvable**, so the companion fuel-factor order `PUR-2025-00059` (referenced inside the biennial review) was **not** added — grab it via a browser/Chrome MCP if wanted.
>
> **DONE (phase 2) — TX PUCT shipped (commit `e7db1d8`).** 4 docs from one contested **El Paso Electric fuel-cost reconciliation** (PUC Docket 57149 / SOAH 473-25-05084, period Apr 2022–Mar 2024) — the adversarial structure of a fuel-prudence case: Preliminary Order (item 34) + OPUC, City-of-El-Paso, and Commission-Staff direct testimony (items 113/114/118). All metadata-only. `data/seeds/tx_puct.json`; tab now **17**. Of the 3 candidate doc IDs above, only `57149_114` was on-theme — `55999_168` (ERCOT large-load presentation) and `58211_13` (OPUC SGIA rulemaking comments) were **off-collection, dropped**. **How to find more TX docs:** the **PUCT Interchange filings search IS scriptable** (unlike the VA SPA) — `GET interchange.puc.texas.gov/search/filings/?ControlNumber={N}` (follow the 302, keep cookies) returns an HTML table of items; each row's `…/search/documents/?controlNumber={N}&itemNumber={M}` page exposes the real `Documents/{control}_{item}_{docid}.PDF` link. The pipeline `python-requests` UA fetches PDFs fine (the WebFetch 403 in ISSUES is a tool quirk); `interchange.puc.texas.gov` ends in `.gov` → guard passes. Note: item-1 "Application" filings are often **multi-part** (12 PDFs) and page 1 of every filing is a "Filing Receipt" cover — read page 2+ for the real caption. Case 57149 is still **open** (status reports through 2026, no Final Order yet); concluded fuel cases would yield a more authoritative order.
>
> **DONE (phase 2) — IL ICC shipped (commit `06f5741`).** 4 docs from one concluded contested **ComEd Rider CFRA (Carbon-Free Resource Adjustment) reconciliation** (ICC Docket 24-0087): Verified Petition (doc 346818, 2024-02-02) + ICC Staff and Chemical Industry Council intervenor direct testimony (docs 354448/354464, 2024-08-20) + **Final Order** (doc 370165, entered 2025-09-04). All metadata-only; `data/seeds/il_icc.json`; tab now **21**. **ICC access (server-rendered, NOT an SPA — easiest state yet for metadata):** `…/docket/P{YYYY}-{NNNN}/documents` lists filings; each doc detail page `…/documents/{docId}` exposes **Date Filed + Type** (authoritative — no page-1 read needed) and per-file links `…/documents/{docId}/files/{fileId}.pdf`. Gotchas: a doc can bundle many files — the *first* file may be a "Notice of Filing" cover (the real testimony was the 2nd file); the `www.` host serves PDFs to browser UAs but **307s the pipeline UA → non-www**, which briefly **throttled a request burst with 404s then cleared** — the pipeline's `requests` GET got all 4 on the ingest run. If throttled, back off (don't hammer) and re-run ingest later.
>
> **DONE (phase 2) — SC PSC shipped (commit `b3b0f6d`).** 3 docs from Dominion Energy South Carolina's **2024 Annual Review of Base Rates for Fuel Costs** (PSC Docket 2024-2-E) — SC's annual fuel-cost-prudence proceeding: DESC direct testimony (Hua Fang/Black & Veatch, 69p) + **Corrected Settlement Agreement** among ORS/DESC/SCEUC (25p; ORS = SC's audit/advocacy arm) + **Joint Proposed Order** on fuel-cost reasonableness (41p). `data/seeds/sc_psc.json`; tab now **24**. **SC DMS access:** docket search is a GET — `dms.psc.sc.gov/Web/Dockets/Search?Summary=fuel%20cost&NumberType=E` or `?OrganizationName=…` → results link `/Web/Dockets/Detail/{id}` → detail page lists filings (date + `/Attachments/Matter/{guid}` PDF; pipeline UA fetches directly, no cookies). Gotchas: a filing labelled "adjustment fuel electric rates" was actually a **DSM program update** (verify-before-seeding paid off again); the formal **final order is in a separate, unfiltered `/Web/Orders` index** (couldn't isolate the 2024-2-E one quickly) — the Commission-approved settlement + joint proposed order stand as the on-theme disposition. Same annual fuel docket exists for Duke Energy Carolinas (`2024-3-E`) and Duke Energy Progress (`2024-1-E`) if breadth wanted.
>
> **▶ PHASE 2 COMPLETE (VA + TX + IL + SC); PHASE 3 OH SHIPPED.** State PUC Audits tab = **26** across **7 states** (OH 2 + PA 4 + MI 4 + VA 5 + TX 4 + IL 4 + SC 3). **Phase-3 WAF mechanism built & proven:** `SourceSeed.fetch=False` (commit `c39815a`) writes a record metadata-only straight from the seed — for sources whose PDF URL is captured in a **real browser** (Chrome MCP) because scripts are WAF-rejected. **OH PUCO DIS** done (commit `e4ef85c`): 2 docs from the FirstEnergy Ohio political/charitable-spending review (Case 20-1502-EL-UNC) — URLs captured via browser (`dis.puc.state.oh.us/ViewImage.aspx?CMID=…`), `fetch=false`, 0-page. **NEXT — NC NCUC** `starw1.ncuc.gov`: confirmed **accessible** (its Cloudflare check auto-resolves in the Chrome-MCP browser — do NOT solve interactive CAPTCHAs); the docket search (`/NCUC/page/Dockets/portal.aspx`) posts back without inline results, so the remaining step is to drive that search to a docket → order → `ViewImage`-equiv URL, then seed `fetch=false` like OH. NC fuel-cost riders (Duke Energy Progress E-2, Duke Energy Carolinas E-7) are the on-theme target.
>
> **Loose ends:** (1) ~~4/5 prudence records 0-page~~ **DONE** (commit `68b0707`) — re-ran the prudence ingest with eLibrary quiet; all 5 now have page counts (Constellation 60p, Delmarva 25p, ITC Midwest 26p, Potomac-Appalachian 61p, ISO-NE 34p). (2) PA/MI **findings parser** for the clean management-audit subset is high-priority below. Full detail in the *Multi-source expansion* section. Access map per regulator in [ISSUES.md](ISSUES.md).

---

> **Policy-analyst review (2026-06-01).** Read through the eyes of a load-growth / data-center / affordability / speed-to-power analyst. Verdict: the corpus answers **affordability only, and only indirectly** — the over-recovery / costs-wrongly-charged-to-ratepayers angle. It is **silent** on load growth, data centers, co-location, and queue/speed (`data center` 0, `queue` 0, `Order 2023` 0 across all 599 findings). Items tagged *(policy 2026-06-01)* below either sharpen the affordability angle the data *can* support, or record the scope gap.

## Multi-source expansion (prudence reviews + state PUC audits)

*Added 2026-06-01. The explorer now spans three collections/tabs — FERC Audits, Prudence Reviews, State PUC Audits — each with its own baked stats/patterns. Prudence + state docs are ingested metadata-only via `pipeline/sources.py` (see [DATA_STRUCTURE.md §8](DATA_STRUCTURE.md) and [AGENTS.md](AGENTS.md)).*

- **[done] Collections + tabs foundation.** `collection`/`jurisdiction`/`source`/`doc_type`/`structured` on `AuditReport` (defaulted so FERC stays valid); 3 UI tabs with per-tab KPIs/patterns/trends/facets + honest per-tab empty + "Listed for reference" states; `patterns_by_collection.json`.
- **[done] State PUC: PA + MI.** PA PUC Bureau of Audits (4 management/focused audits, 2022–2025) and MI MPSC Liberty Consulting U-21305 distribution audits (Consumers + DTE, 2024). Metadata-only, verified against PA/MI press releases.
- **[done] FERC prudence (seed).** eLibrary `Search/AdvancedSearch` full-text discovery → 5 formal-challenge orders + an ALJ initial decision (2015–2025), fetched via the F5 cookie dance, metadata-only.
- **[done] Findings parser — PA M&O audits (Exhibit I-2).** `pipeline/state_structure.py` parses the PA Bureau of Audits **Management & Operations** audits' Exhibit I-2 "Summary of Recommendations" verbatim (no LLM) → Finding per chapter + numbered Recommendations; gated by a synthetic + real-report no-regression snapshot (`tests/test_state_structure.py`); `parse=True` flipped for PPL / PGW / FirstEnergy in `pa_puc.json` (commits `34d4d29`, `61fe023`; 30 findings / 77 recs). Uses `extract.pymupdf_pages` (fitz linearizes the table; pdfplumber interleaves it). Plan: [docs/pa-findings-parser-plan.md](docs/pa-findings-parser-plan.md).
- **[med] Findings parser — remaining state formats (`parse=False` today).** Extend the per-seed parser to: **PA focused audits** (multi-column summary tables that linearize messily), the **PA Management Efficiency Investigation** (FirstEnergy 2025 — different structure), and **MI** Liberty Consulting reports (consultant format). Each needs its own table/prose handler behind the same `parse=True` + no-regression-snapshot pattern; flip per-seed as coverage proves out. Don't emit garbled "verbatim" text — fall back to metadata-only when a format isn't cleanly handled (the parser already does).
- **[done] Phase-2 states — VA / TX / IL / SC (metadata-only).** All shipped: VA SCC (5 orders, `3d2fe3e`), TX PUCT (4, El Paso Electric fuel reconciliation, `e7db1d8`), IL ICC (4, ComEd Rider CFRA reconciliation, `06f5741`), SC PSC (3, Dominion Energy SC fuel-cost review, `b3b0f6d`). State PUC Audits tab = 24. Access mechanics per state captured in [ISSUES.md](ISSUES.md) and the *resume here* note above.
- **[done→med] Phase-3 states — OH done, NC remaining (WAF-blocked).** Mechanism shipped: browser-capture (Chrome MCP bypasses the WAF) + `SourceSeed.fetch=False` (metadata-only, no scripted fetch). **OH PUCO DIS** ingested (2 docs, `e4ef85c`). **NC NCUC** `starw1.ncuc.gov` (Cloudflare) is accessible in the browser; remaining work is driving its docket search to a doc URL (see the resume note above for specifics) then seeding `fetch=false`. OH also has far richer **consultant management/financial audits** beyond the one case seeded — DIS Full-Text/Advanced Search by purpose can surface them (each is a browser-capture + `fetch=false` record, or a future parser target if the F5 fetch is ever cracked).
- **[med] Automate FERC prudence discovery.** The `AdvancedSearch` JSON recipe is now cracked (docket in `searchText`, `categories:["Issuance"]`, accession in `acesssionNumber`; see [docs/data-sources.md](docs/data-sources.md)) and added 2 prudence reviews (MAPP `ER13-607`, PATH Opinion 554 `ER12-2708`, `4d…` batch). Remaining: a `pipeline/prudence.py` that queries it by date range + `ER`/`EL` docket, filters incidental mentions, and emits the seed — discovery is still the hard part (a month of "imprudent" returns ~2,900 hits, mostly incidental; consolidated ROE dockets bleed siblings).
- **[low] Verified prudence candidates to resolve + ingest.** Found 2026-06-02 (well-documented, but the consolidated ROE/complaint dockets don't resolve cleanly via the `searchText` API — pin the exact order accession by date+description or via a browser before seeding): **NETO Opinion 531** (`EL11-66`, 2014-06-19, 147 FERC ¶ 61,234 — base-ROE found unjust, refunds); **MISO Opinion 569** (`EL14-12`/`EL15-45`, 2019-11-21 — ROE cut + refunds); **NCEMC v. Duke Energy Progress** (`EL18-192`, 2019-01-17 — formula-rate complaint denied); plus Transource IEC abandonment and SERI/Grand Gulf refund (dockets/dates need pinning).

### ▶ State-PUC roadmap — next runs (added 2026-06-02; corpus at 22 state jurisdictions / 67+ state records)

*This session added 8 jurisdictions (GA LA MS AR MO MN WI CO) + MO Ameren FAC prudence, all metadata-only, `.gov`, verify-before-seeding, each with an access recipe in [docs/data-sources.md](docs/data-sources.md) and a `test_is_official_gov` assertion. Per-state mechanics + traps live in data-sources.md. Below is what's left.*

**Per-state completeness audit (2026-06-07): [docs/state-coverage.md](docs/state-coverage.md)** — 25 jurisdictions / 83 docs, rated Complete/Good/Partial/Thin with each state's top gap. Use it to pick the next run: single-IOU samplers needing a 2nd IOU (IL+Ameren, LA+SWEPCO, SC+Duke, NJ+ACE, CO+Black Hills) and the thinnest/highest-upside (TX 1-of-7, MS generic, DE 1-doc, MN/OH 1-IOU) are the cheapest wins; CA/NY are the big untapped portals.

- **[high] Expand within the 22 existing jurisdictions** (the cleanest near-term value — portals already cracked, recipes proven). Concrete per-state on-theme targets:
    - **GA** (FACTS, search-harvest): Georgia Power's *own* 2025 IRP direct testimony + the **July 15, 2025 IRP final order** (Docket 56002); the 2025 rate case.
    - **MO** (EFIS, scriptable): more Ameren **FAC prudence reviews** (earlier `EO-2013-0407`…`EO-2019-0257` Staff Reports; the **EO-2024-0053 Commission order** completing the Tenth-review pair) + the **Ameren large-load / data-center tariff docket** (`ET-…`, doc 848430); Evergy/KCP&L FAC (doc 68073).
    - **WI** (ERF, scriptable): the **We Energies "Very Large Customer & Bespoke Resources Tariffs"** decision + WEPCO's own filing (the data-center docket) — only intervenor testimony seeded so far.
    - **MN** (`mn.gov/oah`): the **GR-24-320** electric rate-case ALJ report (only gas rate case + fuel forecast seeded).
    - **AR** (olsv2, scriptable): more EAL FRP years; the **26-001-U** 2026 base rate case.
    - **LA** (ViewFile): the **Grand Gulf / SERI $300M-class refund** + more Entergy LA; pin the Lake Charles review docket (font-obscured).
    - **CO** (E-Filings): deeper PSCo rate-case **testimony** sets via the docket→filing→document 2-level walk (only a sampler seeded).
    - **Earlier states** (VA TX IL SC PA MI OH NJ MD DE KY IN WV DC): scale each from the validation few to fuller coverage (old "Phase 2 — get all docs across states").
- **[med] WAF-walled new states — browser-capture + `fetch=false`** (OH/NC pattern; scripts get 403/Cloudflare/cert errors): **IA** (`efs.iowa.gov` 403s all non-browser — MidAmerican RPU-2023-0001), **NC** (NCUC `starw1.ncuc.gov` Cloudflare — Duke Energy Progress/Carolinas fuel riders), **AL** (`psc.alabama.gov` scanned minutes + stale URLs — Dec 2025 rate-freeze/Lindsay Hill data-center minutes), **MS InSite** (`psc.state.ms.us` broken TLS — **Kemper IGCC** + **$300M Entergy Grand Gulf** settlements — highest remaining prudence value).
- **[partly done 2026-06-07] New states beyond the original set.** **CA + NY done** (33 jurisdictions / 101 docs). CA: 3 ERRA fuel/purchased-power prudence decisions (PG&E/SCE/SDG&E), `fetch=false` HTML (`ca_cpuc.json`). NY: 3 §66(12)(l) rate-case summaries (National Grid/Con Ed/NYSEG, static `dps.ny.gov/system/files` PDFs; `ny_dps.json`). *Remaining (recipes in [docs/data-sources.md](docs/data-sources.md)):*
    - **KS done** — Evergy 25-EKCE-294-RTS base-rate Order (88 pp, approving settlement) + Winter Storm Uri cost-investigation stipulation (21-EKME-329-GIE); `ks_kcc.json`. *Deepen:* a RECA/ACA fuel-true-up order; Evergy Metro.
    - **NY DMM partly done** — harvested the National Grid rate-case Joint Proposal (149 pp, guid `90E66D96`) via `ViewDoc.aspx?DocRefId=%7B{guid}%7D` (fetchable). *Deepen:* the final "Order Adopting Terms of Joint Proposal" — its guid lives on the SPA `MatterManagement/CaseMaster.aspx?MatterCaseNo={case}` (browser-harvest); Google-indexed guids for a case are mostly off-theme (securities, Article VII siting, testimony). RG&E / O&R / Central Hudson; fuel.
    - **OK** (OCC `imaging.occ.ok.gov/AP/CaseFiles/occ{id}.pdf`, `.ok.gov` ✓): search-indexed ids **404**; harvest live ids from the OCC cause-search. OG&E/PSO Fuel Cost Adjustment + 2021 Winter Storm Uri.
    - **MA** (`eeaonline.eea.state.ma.us/DPU/Fileroom`, `.state.ma.us` ✓): fileroom is a **SPA** — reverse-engineer its download API (OGAF/PGAF gas-adjustment dockets).
    - **CA deepen:** recent (2020+) ERRA decisions are real PDFs under the opaque `docs.cpuc.ca.gov/PublishedDocs/Published/G000/M.../K.../{id}.PDF` paths.
    - **UT done** — Rocky Mountain Power base-rate Report & Order (24-035-04) + EBA fuel-cost audit (24-035-01); static `pscdocs.utah.gov/electric/{YY}docs/{docket}/…pdf`. *Deepen:* recent ECAM/EBA orders.
    - **CT done** — PURA Tropical Storm Isaias performance decision (20-08-03) + rate-design decision (17-12-03RE011); static `portal.ct.gov/-/media/pura/…pdf`. *Deepen:* Eversource base-rate (22-08-01) + RAM cost-recovery decisions.
    - **RI done** — RI Energy 2024 Gas Cost Recovery (24-29-NG) + PUC Order 25247 (24-38-GE); static `ripuc.ri.gov/sites/g/files/…pdf`. *Deepen:* a GCR Report & Order; base-rate case 25-45-GE.
    - **NH** (`puc.nh.gov/VirtualFileRoom/ShowDocument.aspx?DocumentId={guid}`, `.nh.gov` ✓): **Akamai WAF** ("Access Denied" to scripts) → browser-capture + `fetch=false` (Eversource Energy Service DE 24-046, distribution DE 24-070).
    - **WY** (`dms.wyo.gov` DMS) + **HI** (`dms.puc.hawaii.gov` DMS, `.hawaii.gov` ✓): both behind Docket-Management-System search portals — harvest the download-URL pattern (browser). On-theme: WY RMP **ECAM** (20000-671-ER-24); HI Hawaiian Electric **ECRC** (D&O 40044). High fuel-prudence value.
    - **VT** (`epuc.vermont.gov` ePUC / `greenmountainpower.com`): orders are in ePUC or on the (non-gov) utility site; `puc.vermont.gov` static PDFs are plans/procedures only. Harvest from ePUC.
    - **ME** (`mpuc-cms.maine.gov/CQM.Public.WebUI/Common/ViewDoc.aspx?DocRefId={guid}`, `.maine.gov` ✓): the CMS viewer **returns an HTML "Message" page to a plain GET** (needs a session/browser). CMP `2025-00218`, Versant 2023 rate case, CMP/Versant service-quality `2022-00279`.
    - **AL** (`psc.alabama.gov` WAF; only `alabamapower.com` non-gov copies): Alabama Power Rate ECR / RSE. Browser-capture.
    - **NE done** — Black Hills gas-cost hedge agreement DENIED (NG-0086) + SourceGas contract-buyout cost recovery (NG-0088); static `nebraska.gov/psc/orders/natgas/NG-{docket}.{seq}.pdf`. NE rate-regulates only its **gas** IOUs (electric is public power). *Deepen:* Gas Supply Cost Review NG-119.
    - **TN done** — Kingsport (AEP) rate case (21-00107) + Atmos WNA gas audit (25-00044); static `tpucdockets.tn.gov/archive/filings/{yr}/{docnum}.pdf`. Mostly gas IOUs + small electric. *Deepen:* TPUC orders; Piedmont.

> **Boundary (2026-06-07, corrected):** static-`.gov`-PDF states are seeded out to **39 jurisdictions** (NE/TN included — gas-only-IOU states a first pass wrongly dismissed). The genuinely walled remainder — **OK, MA, NH, WY, HI, VT, ME, AL, NM, NC, IA** — each sits behind a DMS/CMS viewer, SPA, WAF, or login wall → the next expansion is a **browser-capture pass (Chrome MCP)**, exact wall per state in [docs/data-sources.md](docs/data-sources.md). Only **AK** (tiny IOUs) + US territories remain out of scope.
- **[done 2026-06-07] ND + SD seeded — plain-GET `.gov`, no WAF.** MISO-footprint coverage now 12/~14 states (AR IL IN LA MI MN MS MO WI KY + **ND SD**); remaining gaps **IA** (WAF) + **MT** (unprobed). Shipped **ND ×4** (`nd_psc.json`: NSP/Xcel rate-case testimony PU-24-376, Otter Tail Dual Fuel Riders PU-23-342, Montana-Dakota RRCA PU-25-279 + TCA PU-25-225) and **SD ×3** (`sd_puc.json`: Otter Tail Phase-In Rider EL25-026, MidAmerican TCR reconciliation EL25-004, Montana-Dakota TCR EL25-006); `test_is_official_gov` assertions added for both hosts; state tab 76→83. Recipes (verified live, HTTP 200 / real `%PDF` / pipeline UA / `is_official_gov` ✓) in [docs/data-sources.md](docs/data-sources.md):
    - **ND PSC** — fully predictable PDF path `https://www.psc.nd.gov/webdocs/case/{CASE}/{NNN-010}.pdf` (`{CASE}` = `YY-NNNN`, e.g. `23-0342`; `{NNN}` = per-case sequential doc number; the docket index lists them). On-theme: Otter Tail Dual Fuel Riders (PU-23-342), Xcel/NSP fuel cost rider (PU-24-376), Montana-Dakota RRCA/TCA riders (PU-25-279 / PU-25-225). IOUs: Montana-Dakota, NSP/Xcel, Otter Tail.
    - **SD PUC** — per-year docket index `puc.sd.gov/Dockets/Electric/{YEAR}/default.aspx` → docket page `…/{DOCKET}.aspx` → document PDFs at `puc.sd.gov/commission/dockets/electric/{YEAR}/{DOCKET}/…pdf` (filenames are descriptive, harvested from the docket page; docket = `EL{YY}-{NNN}`). On-theme: Xcel/NSP fuel-clause + transmission-cost-recovery riders, MidAmerican TCR reconciliation, Otter Tail energy-adjustment rider, Black Hills, NorthWestern. Next: seed 3–5 on-theme docs each + a `test_is_official_gov` case per host, verify page-1 before labelling.
- **[med] Remaining MISO gap — IA (WAF).** **IA** `efs.iowa.gov` 403s all non-browser → browser-capture + `fetch:false` (OH/NC pattern; MidAmerican RPU-2023-0001) — see WAF-walled item above. (**MT** now cracked — see the Western item below.)
- **[done 2026-06-07] Southwest + Pacific Northwest (Western Interconnection) — 5 states seeded.** Investigated all 7; recipes in [docs/data-sources.md](docs/data-sources.md). Shipped **7 docs across 5 states** (state tab 83→90), all page-1 verified, metadata-only, `test_is_official_gov` per host:
    - **WA UTC** (`apiproxy.utc.wa.gov/cases/GetDocument`) — **deepened to 3** (PSE Order 38 UE-220066; Avista order UE-220053; PacifiCorp order UE-230172). Harvest order docIDs from `utc.wa.gov/casedocket/{yr}/{dk}/orders`.
    - **OR PUC** (`apps.puc.state.or.us/orders/{YEAR}ords/{ORDER}.pdf`) — **deepened to 3** (PGE PCAM 21-457, PacifiCorp PCAM 18-449, Idaho Power APCU 22-191). *Deepen:* Avista.
    - **ID PUC** (`puc.idaho.gov/Fileroom/.../OrdNotc/…pdf`) — Idaho Power PCA orders 36618 + 35421. *Deepen:* Idaho Power 2024 PCA (36133); Rocky Mountain Power (PAC). NB: Avista's recent `AVU-E-24-13` is an IRP (off-theme) — pick an AVU PCA/GRC case instead.
    - **NV PUCN** — **stuck at 1 (deepen-blocked).** The annual **DEAA** order (explicit fuel-prudence review, NRS 704.187) is the high-value target, but NV's docket PDFs (`pucweb1.state.nv.us/PDF/AxImages/…`) are **scanned/image-only** (no text layer) — can't page-1-verify a caption without OCR; the born-digital `pdf/CS{id}.pdf` files are sparse. Needs an OCR pass or the newer `puc-onbase.nv.gov` search.
    - **MT PSC** — **stuck at 1 (deepen-blocked).** Only the 2023 rate case (Final Order 7860y) is a static `News/Special` PDF; the **2024/25 NWE rate case** (docket 2024.05.061) final order lives in the **browser-only eDocket** (no static link surfaced). Needs the eDocket doc-search (browser) or a `_docs/Documents/{slug}_DOC-{id}.pdf` id.
- **[done 2026-06-07] AZ ACC — cracked (valid-cert host alias).** The broken-TLS `images.edocket.azcc.gov` has a valid-cert sibling **`docket.images.azcc.gov/{DOCID}.pdf`** (path without `/docketpdf/`) that serves the real born-digital docs (verified). Shipped `az_acc.json`: APS rate-case order (E-01345A-03-0437) + TEP Decision 79065 (E-01933A-22-0107). *Deepen:* APS Decision 79293 / recent PSA prudence; UNS; more TEP. Harvest `{DOCID}` via `WebSearch site:images.edocket.azcc.gov/docketpdf` then swap host.
- **[med] NM PRC — still blocked (login wall).** PRCe360 (2026-01) at `edocket.prc.nm.gov` 302-redirects to `Login.aspx`; the old `edocket.nmprc.state.nm.us` is dead. No anonymous document access — needs a Public Guest Account + browser (then `fetch=false`), or a public URL pattern to surface. PNM/EPE/SPS; FPPCAC fuel prudence. This is the last unseeded Southwest state.

## Pipeline & data

- **[med] Partial-date (year/month-known) support for metadata-only records.** *(PR #6 review, 2026-06-07.)* Some legal docs publish only a year+month, not a day — e.g. CPUC decisions, whose number `D.YY-MM-NNN` authoritatively encodes the adoption *month* but whose HTML doesn't carry the adoption-*day* caption (D.06-01-007, D.03-12-063). Today `issued_date` is a full `date`, so these are seeded **null** (no fabricated day) — which **drops them out of the by-year facet / timeline sort**. Add an `issued_date_precision` (`day`|`month`|`year`) or a derived `issued_year`/`issued_month` so the year facet and chronological sort can include month-known docs without implying a false day. Touches `models.AuditReport`, `pipeline/patterns.summarize` (by_year), and the site's year facet. Until then these records carry the month in `source_note`.
- **[low] Surface the per-collection doc-type breakdown in the site tabs.** `llms.txt` now derives a grounded doc-type histogram per collection (e.g. State PUC: direct testimony ×6, RAC order ×2, …) directly in `pipeline/llmstxt.py`. The site tabs only facet by industry/year/theme — adding a doc-type facet/insight chip (from a `by_doc_type` Counter, computed like the others in `pipeline/patterns.summarize`) would give the metadata-only collections, whose main signal IS doc_type, a real "insights" panel like FERC's themes. Keep it mechanical (counts only).
- **[low] Absolute URLs in `llms.txt`/`llms-full.txt`.** Links are relative to the site root (the deploy domain isn't pinned). Once the GitHub Pages domain is fixed, make them absolute per the llmstxt.org convention (`pipeline/llmstxt.py` has the note).

- **[high — TOP PRIORITY] Recover findings from the 26 zero-finding reports.** A corpus audit (2026-05-31) found **26 of 120 reports (22%) structure to 0 findings** despite being born-digital and text-extractable. The site now renders an honest *"No findings extracted — read the source PDF"* state on these (so they no longer look like broken empty cards); **this item recovers the underlying data**, which is the whole "more documents" lever now that FERC has published no new audits since Sept 2025 (re-verified 2026-05-25). Two tracks, **both gated by a no-regression snapshot test** of current per-report finding counts so the 42 validated reports cannot break (the documented overfit trap: Cleco 12→1, MISO 3→7):
    1. **~15 FY2014-2018 (backfill) reports** (e.g. CAISO PA17-3 — has 5 findings, PacifiCorp FA16-4, Dominion FA15-16). Older format: combined "Summary of **Compliance** Findings and Other Matter" exec-summary + `(cid:9)` tab-leader TOCs, vs the 2019+ "Summary of **Noncompliance** Findings" + dotted-leader layout. Add a **separate** `structure_report_legacy()` path in `pipeline/structure.py`, selected by docket era, that **cannot alter** the validated 2019+ output. ~half of these are genuinely brief/clean small-entity letters (expected 0).
    2. **~11 live 2019+ reports** — *newly identified*, not previously documented: e.g. **SDG&E FA19-3 (85pp)**, **WEC Business Services FA21-2 (65pp)**, National Grid USA (53pp), NYISO PA19-1, MidAmerican FA19-2 (full list in [ISSUES.md](ISSUES.md)). These share the validated path, so fixing them is regression-prone — extend header/TOC variants **additively** and re-validate against the snapshot. The large ones near-certainly contain findings.
  - **Re-run:** eLibrary is reachable from here (filelist `GET` → 200), so re-fetch the 26 PDFs (`pipeline/fetch.py`, cached/idempotent, 2 s rate-limit) → `extract` → `structure` → `patterns` → `build`. Keep the seed and baked `docs/data/*.json` in the **same** commit ([AGENTS.md](AGENTS.md)).
- **[done] Process the full corpus — all forms, all years.** Every report — electric (Form 1), gas (Form 2), oil (Form 6), FA + PA — is extracted → structured → mined. FY2014-2018 (49 reports) were backfilled from a Wayback /audits snapshot via `pipeline.backfill` (ferc.gov-origin only); the live page covers 2019+.
- **[med] Improve `_body_summary` precision.** For TOC-fallback reports it occasionally grabs a nearby regulatory citation instead of the finding's opening sentence (titles that recur in cited orders). Anchor more tightly on the section heading.
- **[low] Handle remaining no-TOC report formats.** A few reports lack a parseable TOC "Findings and Recommendations" block (different wording) and show 0 findings even if they have some.
- **[high] OCR fallback for scanned reports.** Born-digital PDFs extract cleanly with pdfplumber/PyMuPDF. Older/scanned reports need real OCR. Add a tesseract-based fallback (`brew install tesseract` + `pytesseract`) behind an `--ocr` flag. **Run the security sweep before installing.** Pages under `MIN_TEXT_CHARS_PER_PAGE` are already flagged as image-only.
- **[med] Incremental listing refresh.** Re-capture `/audits` and append only new reports (idempotent by docket number).
- **[done] eLibrary docket resolution.** Backfill resolves docket → accession via the eLibrary Docket Search API, then downloads via the existing DownloadPDF path (`pipeline/backfill.py`; recipe in ISSUES.md).
- **[high] Detailed-section (Section IV) parsing → dollar impacts.** *(promoted from med — policy 2026-06-01: the single most decision-relevant fact an audit yields is "$X disallowed / refunded to customers," and the site currently surfaces **zero dollars** despite 1,000+ "refund" mentions in the corpus.)* v1 parses the Executive Summary (clean + consistent). The *detailed* findings carry dollar impacts, CFR / USofA-account citations, and "Pertinent Guidance" — extract these into `amount_usd`, `regulations[]`, and richer per-finding text. Inputs aren't committed (`data/raw/` PDFs + `data/processed/*/text.json` are gitignored, regenerable), so it's a **re-fetch → re-extract → parse-detailed-section** pass on the same idempotent path as the 26-report recovery — not a local-only job. The structured `report.json` (committed) is findings-only.
- **[med] Capture the company-response section.** Each report ends with the audited entity's response (agree/disagree + remediation plan). Parse it onto each report/finding.
- **[done] Listing freshness vs. live.** Re-checked the live /audits page via a real browser on 2026-05-25 — byte-identical to the 2026-02-03 snapshot (no audits issued since Sept 2025). Re-run when FERC publishes new reports (incremental by accession).
- **[low] Multi-docket reports.** The listing parser captures one docket per report; some reports cite several. Handle the multi-docket case.
- **[low] Pull related Commission orders.** Audit reports cite related orders; fetch and cross-reference them.

## Analysis

- **[done] Audit-type facet (FA vs PA).** Two types per FERC: **FA = Financial Audit**, **PA = Non-Financial Audit** (compliance/operational). Derived from the docket prefix; shipped as `audit_type` + a site filter.
- **[done] Form/industry mix → broad explorer.** Decision: keep the broad explorer covering electric (Form 1), gas (Form 2) and oil (Form 6) rather than scoping to Form 1 only. Industry is parsed and shipped as a site filter (Electric / Gas / Oil).
- **[low] FERC-form facet lists incidentally-cited forms.** `detect_forms()` captures every "FERC Form No. X" mention, so the site's Form filter shows forms a report merely *cites* (No. 549, 552, 714, …) next to the audited form — noisy and a bit confusing. Distinguish the report's primary/audited form from cited forms and facet on the former.
- **[done] Finding taxonomy + ratepayer-harm axis.** Shipped 2026-06-01 (commits e212be1, dc5de5e). Every finding is tagged with its `themes` (the existing keyword rules, now baked per-finding) and a `cost_to_customers` flag; reports carry the union + an OR flag. Site: per-finding theme chips + an amber "Cost to customers" badge, and a "Ratepayer impact" filter (69/120 reports, 207/602 findings). The harm axis is a conservative curated subset in `patterns.py` (`RATEPAYER_HARM_THEMES`): below-the-line, membership dues, affiliate, depreciation, AFUDC, cost-of-service. *(Excess-ADIT isn't a theme yet — a future THEME_RULES entry could add it.)*
- **[done] Cross-report trend charts.** Shipped 2026-06-01 (commit c6d239e): a "How the corpus breaks down" section charting reports by year issued, by industry, and by function — vanilla CSS bars over the baked aggregates, no deps, responsive + reduced-motion-safe. *(Per-company chart not done; low-value follow-up.)*
- **[low] Recommendation-outcome tracking.** Did the company implement the recommendation? (Annual Reports on Enforcement note status.)
- **[low] Technology/asset tag (nuclear, hydro, storage, RTO/ISO) — NOT a new sector.** Q raised 2026-06-07: should sectors expand to nuclear/batteries? **No** — `industry` tracks the FERC accounting *form* (1→electric, 2→gas, 6→oil), and nuclear/hydro/storage/solar/wind are *generation technologies within electric*, not FERC audit categories (FERC audits the Form-1 filer's books/tariff; reactor safety is NRC). Confirmed in-corpus: scanning all 120 audit captions returns **0** nuclear/battery/solar/wind, **6** RTO/ISO (MISO, PJM, NYISO, CAISO, ISO-NE — all Form 1 → electric), **16** pipeline. So a generation-technology *sector* would have ~no signal and isn't source-grounded. The legitimate version is a **secondary asset/entity tag** (RTO-ISO vs vertically-integrated vs transmission-only; nuclear/hydro *only if* the audit text names it verbatim) layered on the existing `functions` facet (generation/transmission/distribution) — keyword-derived like `themes`, never LLM-judged. Weak caption signal means it needs full-text scanning; low priority.
- **[low] Reclassify the 3 `industry: unknown` FERC audits.** Emera Maine (PA15-4, an electric transmission utility), Cargill (FA14-6) and Occidental Energy Marketing (FA14-8) — the latter two are market-based-rate power/commodity **marketers** that don't file a clean Form 1/2/6, so `primary_industry()` scores 0. They're FERC electric-jurisdiction MBR sellers; either add an MBR-seller signal to `forms._INDUSTRY_SIGNALS["electric"]` or relabel the bucket "electric (power marketer)" so the UI doesn't show a bare "unknown."
- **[med] Full-text search across report bodies.** v1 search covers titles/summaries; index the full extracted text for deeper queries.
- **[high] Ratepayer-impact lens — dollar magnitude.** *(promoted from low — policy 2026-06-01. **Count-based half shipped** 2026-06-01: the "Cost to customers" filter + badge + a 69/120-report stat — see Finding taxonomy above. This item is now the **$ magnitude**.)* Once `amount_usd` is extracted (Section IV parsing), sum quantified impacts by theme / company / year and lead with a headline stat — e.g. *"$X improperly recovered from customers 2014–2025; $Y of it below-the-line lobbying/charity/dues."* Turns the count into a quantified over-recovery dataset — the one affordability story this corpus can actually tell. Depends on Section IV parsing above.
- **[med] Interconnection & transparency facet.** *(policy 2026-06-01.)* 27 findings touch interconnection — but as *transparency-posting* compliance ("Posting of Generator Interconnection Study Times," capability info, short-circuit data), **not** queue speed or interconnection cost. Tag + facet them so the narrow question *"do utilities even comply with the postings meant to support interconnection?"* is answerable. Honest ceiling: says nothing about how fast anyone connects.
- **[med] Filtered CSV export + stable per-report cite URLs.** *(policy 2026-06-01: analysts cite and re-analyze.)* Let a user download the currently-filtered finding set as CSV, and give each report a stable anchor/URL to cite. Pure presentation over the already-baked `docs/data/*.json`; pairs with the `[low]` per-report markdown pages under LLM-readability.

## The bigger vision

- **[high] "Audit-my-document" mode.** The longer-term goal: feed in an application/filing and flag likely issues using the pattern library mined from historical audits. v1 builds that library; this feature consumes it.
- **[med] Ingest the underlying FERC Form 1 financial data (via PUDL).** The audits scrutinize the *numbers* in Form 1/2/6. FERC publishes that data in formats needing special software — Visual FoxPro `.DBF` (1994–2020) and XBRL (2021+) — painful on macOS. Use **PUDL** (catalystcoop, pip-installable, SQLite/Parquet output) to ingest it with **no FERC installer**, then cross-reference audit findings against the reported figures.
- **[high] New collection: FERC Office of Enforcement actions (the real "other type of FERC stuff").** *(Q raised 2026-06-07: are there FERC categories beyond electric/gas/oil audits?)* The honest answer to "what else does FERC produce that flags noncompliance" isn't a new *sector* — it's a new *document type*: **OE civil-penalty settlements, Show Cause orders, market-manipulation cases, and self-reports** (the annual *Report on Enforcement* + the underlying eLibrary issuances). This is the most mission-aligned expansion — literally "issues a FERC regulator raised," complementing the audit pattern library — and it's where technology-specific matters (a battery/storage market-manipulation case, a nuclear cost dispute) would actually surface. Fits the existing multi-collection model (a 4th tab, metadata-only "Listed for reference", same `pipeline/sources.py` + eLibrary `AdvancedSearch` discovery). Adjacent but lower-priority cousins: **NERC reliability Notices of Penalty** (NERC-authored, filed at FERC) and **hydropower (Part I) license-compliance** matters (Office of Energy Projects, not DAA audits — niche).
- **[high — large] Second module: forward-looking FERC dockets (not audits).** *(policy 2026-06-01: the audit corpus is **silent** on load growth, data centers, co-location and queue/speed.)* Those decisions live in *proceedings*, not audits — Order 2023 (interconnection queue reform), Order 1920 (long-term transmission planning), large-load / co-location dockets (e.g. the PJM–Susquehanna/AWS ISA proceeding), data-center tariff filings. A **separate** module that ingests those eLibrary dockets, **not** a tweak to the Audit Explorer (the audit pattern-library doesn't transfer). Big scope; fits the multi-module north star.

## Competitive analysis & improvement themes

- **[med] Learn from similar regulatory/audit document projects.** *(Added 2026-06-07.)* Research identified 8 comparable public-interest tools (see [About — Related Projects](docs/about.md#related-projects)): PUDL (energy data integration), FERC eLibrary (official archive), ProPublica Data Store (curated datasets), LegiScan (legislative tracking), Ballotpedia (agency reference), State PUCs (fragmented filing centers), InvestigateWest (investigative journalism). Key improvement themes to extract:
    - **Multi-source corpus integration** — PUDL's approach to unifying data from multiple agencies (like our planned FERC + state PUC + prudence expansion) — how they handle schema mismatch, update cycles, deduplication.
    - **Narrative accessibility** — ProPublica + InvestigateWest's story-first framing (connect findings to impact, not just metrics); apply to our findings summary cards.
    - **Investigative scaffolding** — how journalism-backed tools guide users from a pattern to deeper investigation (bill tracking, donor links, related cases). Our "audit-my-document" feature needs this.
    - **API + machine-readability** — PUDL's Python API + llms.txt sufficiency; is there a programmatic access pattern users expect?
    - **State/regional expansion** — how state PUC centers fragment access; our metadata-only multi-state expansion should learn from their access patterns + pain points.
    - **Update discipline** — PUDL's quarterly cadence + FERC's real-time + legiScan's live polling. Our refresh strategy (FERC dormant since Sept 2025; state runs ad-hoc) should be documented with expectations.
    - **Visualization & trends** — how these tools rank/chart (ProPublica's explainers, Ballotpedia's tables). Our trends band is a start; deepen with narrative context.
- **[low] Cite inspiration in About + footer.** Link [About — Related Projects](docs/about.md#related-projects) from the footer, so users see the ecosystem. Not a competing list, but an honest "if you want more context, also read X."

---

## Design / UI — theme variants to A/B (user wants to test which sticks)

- **[med] Wave-style threaded theme.** Google Wave inspiration: findings as threaded/conversational items with an inbox-like reading flow. Swappable.
- **[med] Editorial + periwinkle theme.** Restrained FT/ProPublica public-record look, periwinkle accents. Swappable.
- **[low] Runtime theme switcher.** Toggle Plus-stream / Wave-threaded / Editorial to decide which the user prefers (chosen v1 = Plus-stream).
- **[done] Verify the mobile layout visually.** Confirmed at **375px** on 2026-05-31 via the Preview MCP — single-column, collapsed how-to, KPI + Top-patterns **horizontal scroll-snap** rails, bottom-sheet filters. Shipped with the trends/clarity/mobile redesign.
- **[low] "Compare two reports" view.** Side-by-side findings/themes for two selected reports.

## Quality & testing

- **[med] Listing↔PDF integrity check.** A test/CLI confirming every `listing.json` entry resolves to a downloadable PDF — catches eLibrary API changes early.
- **[low] Accessibility / Lighthouse pass.** Audit contrast, focus order, and performance once the site is deployed.

## LLM-readability (llms.txt)

- **[med] Absolute URLs in llms.txt once a deploy domain exists.** `llms.txt`/`llms-full.txt` currently use site-root-relative links (no domain fixed yet). The llmstxt.org convention prefers absolute URLs for portability — switch when the GitHub Pages URL is known (thread it through `pipeline/llmstxt.py`).
- **[low] Per-report markdown pages + an llms.txt link section to them.** Static `report/<id>.md` pages would give LLMs (and humans) stable per-report URLs to cite.

## Infra

- **[done] GitHub Pages deploy.** `.github/workflows/deploy.yml` publishes `docs/` to Pages on push to `main`. Repo: github.com/pranava0x0/FERCforms. (Next: revisit absolute llms.txt URLs now that the domain is known — pranava0x0.github.io/FERCforms.)
