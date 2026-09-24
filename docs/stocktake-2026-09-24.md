# FERC Document Analysis — stocktake, September 24, 2026

**Useful source library; incomplete evidence system.** FERC audit coverage and the reading UI are the strongest parts. State extraction is concentrated in three states. Themes support discovery, but do not yet support reliable comparisons of violations, customer harm, or docket outcomes.

This review started at remote `main` **66d0119** after a 14-commit fast-forward. It checked every tracked report and seed, the discovery/download paths, both structuring paths, aggregate logic, backlog, and all five UI collections. A targeted refresh added **four documents, 15 findings, one other matter, and 73 recommendations**. Existing 440 baked report objects remained unchanged. No broad re-structure or legacy crawler run was used.

## Corpus after refresh

| Collection | Documents | Documents with extracted findings | Findings | Recommendations |
|---|---:|---:|---:|---:|
| FERC audits | 126 | 114 | 678 | 1,552 |
| State utility audits | 83 | 14 | 146 | 547 |
| Prudence reviews | 29 | 1 | 37 | 0 |
| State rate cases | 122 | 0 | 0 | 0 |
| State reference documents | 84 | 0 | 0 | 0 |
| **Total** | **444** | **129** | **861** | **2,099** |

There are also **11 other matters**, excluded from the finding totals above. The 12 zero-finding FERC reports are previously reviewed clean audits, not automatically presumed parser failures. State findings come from **PA: 11 audits; NY: 2; NJ: 1**. The prudence findings all come from one California ERRA decision.

These are different units: FERC findings are noncompliance issues; state M&O “findings” often group recommendations by functional area; CPUC Findings of Fact include background facts and favorable determinations. Adding them together is a content count, **not a count of equivalent violations**. The state rate-case tab is a document library, not yet an extracted docket-analysis product.

[Machine-readable counts and comparisons](stocktake-2026-09-24.json) use the refreshed baked corpus. The state sample is neither jurisdiction-complete nor a statistical sample of industry compliance.

## Commonalities supported by the data

The strongest shared question is **which costs belong in which accounts, which assets enter rate base, and which costs can enter rates**. Form 1, Form 2 and Form 6 audits share accounting and reporting issues; their institutional settings differ.

Report counts below use finding-derived keyword tags only, exclude “other matters,” and count each report once per theme. Forms are detected mentions, not exclusive cohorts; some existing form tags still need scope verification.

| Shared theme | Form 1: 71 reports | Form 2: 11 reports | Form 6: 17 reports |
|---|---:|---:|---:|
| Accounting misclassification | 50 | 10 | 15 |
| Form reporting | 38 | 7 | 17 |
| Property and plant records | 20 | 6 | 16 |
| Below-the-line costs | 22 | 9 | 13 |

Form 6 has a particularly strong Page 700/property/depreciation emphasis. Form 1 connects accounting errors to wholesale transmission formula rates; Form 2 adds gas tariff, fuel and pipeline-accounting issues. The new Houston report concerns **Form 549D**, not Form 2: intrastate transportation terms, fuel retention and reporting. A three-form-only narrative misses part of the corpus.

The bridge to state M&O audits is **affiliate costs, controls, assets and service execution**. Finding-derived affiliate themes occur in 27 FERC reports and 10 state audits; internal-control themes in 3 and 12; property-record themes in 42 and 2. State recommendations also emphasize customer service (13 audits), workforce (13), and inventory/materials/fleet (10). Those differences partly reflect what the respective audit programs examine and what the parsers retain.

Rate cases and prudence reviews share the cost-recovery subject, but the present evidence is shallower: **34 rate-case documents and 8 metadata-only prudence documents** have fuel/purchased-power descriptor tags. These are topic matches from document descriptions, **not extracted adverse findings**. Do not compare their rates of “noncompliance” against FERC audit statistics.

A useful next comparison should distinguish **audit observation → recommendation → utility response → commission disposition → implementation**, with separate source passages for every step. A filed claim, staff recommendation, ALJ finding, settlement and final commission order must remain different evidence types.

## Accuracy and traceability

**What holds up:** all 317 pre-refresh state/prudence seed IDs mapped to a published report. Company, collection, jurisdiction, docket, exact date, source URL and capture date matched between seed and report. No exact duplicate document URLs existed among the 440 published records. Schema, quote-noise, source-host and curated snapshot tests provide useful protections.

**What does not hold up yet:**

1. **Rebuild contamination risk.** Main contains 68 untracked processed records and four remaining untracked seed files. Several explicitly say “Placeholder URL pending verification.” The build loader reads every `data/processed/*/report.json`, irrespective of Git/seed status. A local rebuild can resurrect rejected material. Verification therefore ran in a clean managed worktree. The original five untracked seeds were preserved under `/tmp/ferc-sync-20260924`; the untracked WA filename collided with a newly tracked remote file, so its saved copy must not be mistaken for the reviewed remote seed.
2. **Two incompatible structuring routes.** `sources.py` has source-specific, bounded parsers. `structure.py` separately routes state documents and can erase valid content. A read-only call reproduced the CA prudence record changing from **37 findings to zero and losing its docket**. Its “management” branch also routes by a generic title rather than the verified source format. Do not follow the old blanket `extract → structure` refresh recipe.
3. **Quotes still contain layout debris.** A diagnostic comparison checked 638 summaries and 1,551 recommendations across 111 locally cached finding-bearing reports. **68 summaries and 46 recommendations across 56 reports** failed a full normalized substring match. Fifteen finding-bearing reports lacked cached text. These 114 mismatches are a review queue, not 114 proven false quotes: extractor differences and page breaks also cause mismatches. Direct PDF inspection confirmed real defects, including Kern River's trailing `D.` section label and Medallion's unrelated footnotes inside a finding. Another screen found 96 fields ending in a possible lettered heading. [Review queue and method](../data/sources/quote-screen-20260924.json).
4. **Customer-harm inference is too strong.** `RATEPAYER_HARM_THEMES` marks every AFUDC/depreciation/affiliate/cost-of-service match as an overcharge class. [PacifiCorp FA16-4](https://elibrary.ferc.gov/eLibrary/filelist?accession_number=20170829-3016), PDF pages 7 and 45, describes offsetting errors resulting in net **underbilling**; finding 6 still receives “Cost to customers.” Other findings explicitly say only that disclosure accuracy suffered. This axis needs an approved neutral label or separately verified effect/direction fields.
5. **Page-level provenance is sparse.** Before refresh, only 280 of 2,026 recommendations had printed-page citations; 60 findings had page-cited dollar sentences. General finding summaries have no page field. There is no corpus-wide PDF hash, parser version, extraction configuration, or latest-verification timestamp. Source links often lead to an index or eLibrary landing page. The refresh adds a separate receipt with source hashes, exact quote hashes, and PDF page ranges for all **89 new FERC summary/recommendation quotes**. That improves these records, not the entire corpus.
6. **Date/docket gaps need honest semantics.** 126 records lack exact dates and 126 lack dockets; all 84 reference records lack both. Some documents have only a month/year or are not docketed, so filling invented dates/numbers is not a fix. Preserve published date, issue date, audit period and proceeding ID separately when available. The refreshed SCE record explicitly labels `AL 5660-E` as an advice letter, not an application docket.
7. **Form/industry inference can mislead comparisons.** The current regex truncates `549D` to `549`; incidental statutory references caused Houston to parse as electric/generation. The new record was corrected from its signed scope to gas/Form 549D. The two new electric records explicitly retain Forms 1 and 3-Q. Existing records were not bulk-retagged.
8. **CSV was stale.** Rebuilding removed four discarded CA boilerplate rows and added 37 valid ERRA findings already present in JSON. JSON and CSV were describing different corpora. Build all generated surfaces together and add a parity gate.

## Scraper and architecture assessment

The Python stages plus static JSON/vanilla JS remain an appropriate architecture. A new framework or backend would not solve the current problems. Keep discovery, source verification, extraction, curation and publication distinct.

| Path | Assessment | Required improvement |
|---|---|---|
| `listing.py` | Saved-browser-snapshot parser; useful and deliberately not a headless scraper | Preserve dated snapshots; append verified discoveries; do not overwrite historical backfill with a current-page-only rebuild |
| `backfill.py` | Historical Wayback/eLibrary resolver with official-source restriction | Retain accession-pair evidence; treat API result limits and ambiguous results explicitly |
| `fetch.py` | Useful eLibrary session handling, cache and backoff | Stream with byte/time limits, validate cache contents, atomic writes, failure exit status |
| `sources.py` | Preferred path for reviewed state seeds; metadata-only default is sound | Prevent stale richer reports surviving a changed source identity; hash/version source, validate redirect destination, avoid double extraction |
| `verify_sources.py` | Valuable screening, not proof of document identity | Replace optimistic `PROVEN`; check ID/accession pairs, docket/date/type as well as company; oversize must be unverified, not success |
| `state_puc_crawler.py` | Unsafe as a refresh publisher | Placeholder records, broad keyword classification, positional IDs, ignored year bounds; output discovery candidates only |
| `state_puc_crawler_v2.py` | Unsafe as a refresh publisher | Commission self-audits and generic PDFs can become utility audits; review candidates before ingest |
| `state_puc_crawler_tier2.py` | Unsafe as a refresh publisher | Broad PDF harvesting and set-order IDs; stable source IDs and caption/type verification required |
| `scripts/ingest_state_puc_seeds.sh` | Success counts can mean metadata written, not PDF fetched | Report fetched/verified/reference-only/failed separately; stop blanket re-ingest |
| `scripts/batch-extract-rate-cases.sh` | Batch size helps memory; downstream generic structure remains unsafe | Explicit selected IDs, source-specific dispatch, no silent overwrite |

Code evidence: `patterns.py:199` loads all on-disk records; `structure.py:496–532` contains the divergent dispatch; `sources.py:470` preserves existing findings without source-identity comparison; `verify_sources.py:204–209` treats oversize content as no failures. `extract.load_from_reports()` looks for `data/reports.json`, while the actual bake is `docs/data/reports.json`; locally it fell back to 123 listing records. The later processed-directory loop rescues seed extraction but also admits stray files.

Memory: the three small new FERC reports (39–53 pages) took approximately 4–8 seconds each to extract/structure in one process, reaching **307 MB peak RSS** on this Mac. This is not a large-PDF benchmark. Fetchers buffer complete responses; pdfplumber retains page objects; fallback can reopen a PDF once per page; parse-enabled source ingestion can extract twice. Bound one large document at a time, close page caches, reuse a single fallback handle, and checkpoint by document. Do not increase worker count to mask these costs.

## UAT and performance

Before refresh, all five collections were clicked at 1280×900 and 375×812: cards, source links, collection counts and desktop Ledger worked; no document-level horizontal overflow or uncaught JS errors appeared. Mobile source subtitles truncate, and reference names such as `BiAnnualReportFuelMix-2017` remain poor reader-facing labels.

The new data exposed a real cold-load finding-permalink race: scrolling waited for the fetch, not DOM insertion. Fixed by explicitly starting/awaiting thread rendering and targeting the heading. A separate anchor test picked a clean audit by fixed position; its fixture now selects a deep report with findings.

The index is about 25 KB gzip. After refresh, first-party runtime assets total about **91 KB gzip before details / 258 KB with the active FERC detail file**, excluding external analytics. These are compression estimates, not production transfer measurements. Initial local Resource Timing showed 11 entries, including the detail prefetch and Google Analytics. Full `reports.json` is not fetched; the split still helps. However, “lazy details” means **idle-prefetched per active tab**, not only fetched on expansion. The June performance skill's “7 requests, no third parties” baseline is obsolete.

Validation: **341 passed, 15 skipped** (`python3 -m pytest -q`, September 24). Skips require
cached PDFs/text absent from the clean worktree, including real-source state-parser fixtures;
synthetic/parser, corpus-integrity and desktop/mobile E2E checks passed. This does not certify
every old quote against freshly downloaded source bytes.

## Refresh evidence and limits

- **[Niagara Mohawk FA25-3](https://elibrary.ferc.gov/eLibrary/filelist?accession_number=20260918-3038)** — September 18, 2026; 53 pages; 7 findings and 35 recommendations.
- **[Atlantic City Electric FA25-4](https://elibrary.ferc.gov/eLibrary/filelist?accession_number=20260806-3006)** — August 6, 2026; 39 pages; 5 findings and 22 recommendations.
- **[Houston Pipe Line PA24-7](https://elibrary.ferc.gov/eLibrary/filelist?accession_number=20260721-3030)** — July 21, 2026; 53 pages; 3 findings, 1 other matter, 16 recommendations.
- **[SCE quarterly procurement AUP report](https://www.cpuc.ca.gov/-/media/cpuc-website/divisions/utility-audits--risk--and-compliance-division/reports/energy/2026/energy_2026-03-20_sce_qp.pdf)** — March 20, 2026; 17 pages; verified reference record, no unvalidated findings parser.

The real-browser FERC 2026 index was checked; it was last updated August 13 and listed ACE/Houston but not the newer Niagara report. Fourteen eLibrary prefix searches (FA20–26, PA20–26) independently found the three additions. Several older prefixes return only ten hits out of larger totals: this was **not exhaustive paginated discovery**. Source captions were checked before ingest. Existing PA PPL (93 pages) and NY NYSEG/RG&E (439 pages) were re-downloaded and caption/docket-checked; both matched expected page counts. No 50-state live link sweep was performed.

The ordinary parser initially produced **zero of 35/22 recommendations** on Niagara/ACE because the intro changed to “DAA’s recommendations,” and it retained page furniture. This refresh therefore uses source-specific, count-checked curated excerpts; no generic parser was loosened. Regenerating these three records through the current generic structurer would lose those corrections. The no-cache regression test now guards the signed counts, quote hashes, industry/forms and page citations.

[Discovery and live-check receipts](../data/sources/refresh-discovery-20260924.json) · [New-document verification](../data/sources/refresh-verification-20260924.json).

## Recommended order of work

1. **P0 — stop unsafe publication.** Gate the published corpus by approved seed/record inventory; quarantine discovery candidates; unify structuring dispatch; fail on source identity changes. Acceptance: a stray processed record never reaches a bake, and re-running each accepted format preserves verified content/provenance.
2. **P1 — repair evidence quality.** Fix quote boundaries and missing recommendations with source snapshots; add PDF hash, extractor/parser version, PDF/printed pages and verified quote ranges. Distinguish partial parsing, no findings, scanned/unreadable, and not attempted. Calibrate form tags from audit scope. Add JSON/CSV parity.
3. **P1 — make insight claims honest.** Separate descriptor matches from finding matches; distinguish fact/recommendation/allegation/order/outcome. Remove directional harm claims unless explicitly supported. Do not sum dollar mentions into ratepayer impact.
4. **P2 — deepen one state.** Start with CA or NY already represented here. For CA, develop a bounded UAB report parser alongside the accepted ERRA Findings-of-Fact parser. For NY, connect audit, response, implementation plan and relevant final orders. Add stable document IDs and docket roles before harvesting more documents.
5. **P2 — cross-document comparison.** Expose question-led comparisons with denominators, evidence types, matched passages and page links. Track exact utility identities/aliases rather than assuming string-equal company names capture corporate relationships.
6. **P3 — broader discovery, OCR, dollar briefing and audit-my-document.** Resume only after the evidence gates above. Keep the static frontend; optimize active-tab prefetch only if measured user conditions justify it.

Three options: **guardrails first** (recommended; limits repeat corruption), **parser/state depth first** (more visible insights, but fragile until reruns are safe), or **broad recrawl** (more documents, highest noise/memory cost, least useful now). Significant schema/editorial changes require the plan approval described in CLAUDE.md; this stocktake does not silently change those rules.

One bounded **Sol** agent reviewed the scraper paths while the primary agent checked corpus, source text, refresh and UAT. Its findings were checked against code and folded into this report/backlog. Token/tool usage was not exposed, so no cost ratio is claimed. The useful pattern was one batched read-only audit, not one agent per state; no discovery fan-out was used.
