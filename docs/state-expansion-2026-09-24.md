# Seven-state document expansion — September 24, 2026

14 new official documents across VA, TX, PA, NY, OH, GA and OR. Selected evidence,
not complete dockets or a ranking of state performance. All remain metadata-only.

| State | Added | Evidence and limits |
|---|---:|---|
| VA | 1 | Dominion Rider DIST final order, PUR-2024-00137, May 1, 2025. Distribution-grid transformation and undergrounding cost recovery. The 2025 biennial final order was already held. |
| TX | 2 | CenterPoint Houston base-rate order 56211 and energy-efficiency recovery order 58185. Separate mechanisms: the former reduces approved revenue; the latter permits annual program-cost recovery. Do not combine their dollar figures as a net bill change. |
| PA | 3 | PECO 2026 Management Efficiency Investigation, PECO billing-system tariff order, PPL April 17, 2026 ALJ recommended rate decision. The recommended decision is not the final Commission order. PECO audit cover states February 2026; exact issue day is unknown, public release March 12. |
| NY | 1 | National Grid August 14, 2025 final order, 24-E-0322/24-G-0323. Complements the already-held joint proposal and summary; covers both electricity and gas. |
| OH | 1 | Auditor of State's September 15, 2026 PUCO performance audit. Reviews the regulator, including rate-case processing. Classified as reference, not a utility audit. |
| GA | 3 | Georgia Power alternate-rate-plan extension, storm-recovery order, and annual earnings-surveillance disposition, all under 44280. These are distinct documents in one docket, not three independent cases. |
| OR | 3 | PacifiCorp UE 433 rate order and reconsideration denial; PGE UE 435 rate order. Wildfire prudence, capital spending, expense controls, affordability and large-load allocation are prominent. |

## What connects these records

The shared evidence questions are **which costs belong to customers, whether those costs are
supported, and whether controls prevent recurrence**. FERC financial audits check reported
accounts and compliance; rate cases decide recoverable costs and rates; management audits
examine operations and follow-through. They overlap in subject matter, but their findings,
legal standards, reporting periods and remedies are not interchangeable.

PECO now has a useful sequence: the existing 2022 management audit, the 2024 billing-system
tariff order, and the 2026 follow-up investigation. This supports studying implementation,
not inferring that tariff approval proved the billing system performed well. Oregon's
PacifiCorp final order and reconsideration order similarly preserve both the initial decision
and the challenge to it. National Grid's final order completes a proposal-to-decision chain.

Storm and wildfire costs recur in OR, GA and TX documents. Large-load allocation appears in
OR and PPL's PA proceeding. These are research connections, not newly extracted findings or
proof of identical failures. Compare cited passages only after checking utility, period,
requested versus approved amounts, and the document's procedural role.

## Evidence and refresh

Seeds: `data/seeds/{va,tx,pa,ny,oh,ga,or}_expansion_20260924.json`.
Receipts: `data/sources/eastern-*.json`, `ga-expansion-20260924.json`,
`oh-expansion-20260924.json`, `or-pacificorp-20260924.json`, `or-pge-20260924.json`.
Each PDF has SHA-256, page count, official URL, caption-page text and reviewed metadata.
Image-only GA orders and OR reconsideration were visually inspected; PA's image cover and
TX signature dates were also inspected. No unsupported findings parser was enabled.

Reusable commands and access limits: [source guide](data-sources.md#seven-state-refresh--2026-09-24).
The scripts cache PDFs, cap downloads at 45 MB, stream bytes, verify redirects, and ingest
one PDF at a time. Discovery never publishes candidates. Explicit caption review and a
matching reviewed seed are required before ingestion. Existing cached bytes are hash-checked;
held records are skipped rather than silently refreshed or replaced.

## Research-agent review

One Sol discovery agent covered four pre-screened states and returned six usable PDFs.
All six were independently caption-checked, deduplicated and fetched again with the pipeline
User-Agent. Parent found the PPL date on page 288 and added PECO's new MEI inline. Agent usage
counters were not exposed, so no token-per-document estimate is claimed. A follow-up hardened
cache validation, deadlines and failure exits. A live NY rerun then caught duplicate Download
anchors replacing document titles; a regression preserves the observed docTitle parameter.
NY docket searches still returned no matching final order in their first 50 rows; the seeded
order came from a separately observed official PDF link, not exhaustive discovery. No further research agents were needed.

Lesson: page 1–3 checks establish identity but may not establish date. Check signature or
transmittal pages before leaving dates unknown. The regression test now preserves the PPL
signed date and keeps its recommended status distinct from a final order.

## Runtime check

Repeat ingestion of PA's three PDFs (374 pages) took 1.73 seconds with 87.3 MB maximum
resident memory on the local machine. GA repeat discovery returned 0 new / 3 held / 0 failures.
The compressed report index grew by 873 bytes (26,585 to 27,458); detail collections remain
lazy-loaded. These are local measurements, not service-level guarantees.
