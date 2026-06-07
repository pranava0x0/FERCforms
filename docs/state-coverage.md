# State PUC coverage — completeness audit

State of the **State PUC Audits** collection as of 2026-06-07. Snapshot: **30 jurisdictions, 90 documents**,
all metadata-only ("Listed for reference") **except PA**, the only state with parsed verbatim findings
(3 Management & Operations audits via `pipeline/state_structure.py`). Access mechanics per state live in
[data-sources.md](data-sources.md); the expansion roadmap in [../BACKLOG.md](../BACKLOG.md).

This is a **deliberately sampled** corpus — the goal is a few *on-theme* (cost recovery / prudence / audit / rate
case) documents per state, not every filing. "Completeness" below is judged against that goal: does the sample
cover the state's **major investor-owned utilities (IOUs)** and its **signature on-theme proceeding type**?

## Rating legend

- **Complete** — single-IOU jurisdiction fully covered, *or* all major IOUs + the signature doc type present.
- **Good** — most major IOUs covered and an on-theme doc type captured; a sampler that does its job.
- **Partial** — the dominant IOU(s) covered but a major IOU or key doc type is missing.
- **Thin** — only 1–2 docs / one IOU / generic docs; a placeholder more than a sample.

## Per-state

| State | RTO | Docs | IOU coverage | Focus / doc types | Rating | Top gap |
|-------|-----|-----:|--------------|-------------------|--------|---------|
| **DC** | PJM | 2 | Pepco (the only IOU) ✓ | MYRP order + reconsideration | **Complete** | — (single-IOU) |
| **VA** | PJM | 5 | Dominion + Appalachian (both IOUs) ✓ | biennial review, RAC, CPCN, net metering | **Complete** | deeper Dominion fuel/RAC sets |
| **PA** | PJM | 4 | PPL, FirstEnergy PA, PGW (gas) | **parsed** M&O audits + efficiency investigation | **Complete** ⭐ | PECO, Duquesne; focused-audit parser |
| **KY** | PJM/MISO | 3 | Duke KY, Kentucky Power, LG&E/KU | base-rate orders + FAC | **Good** | — broad already |
| **IN** | MISO | 3 | Duke, AES/IPL, NIPSCO | fuel-cost-adjustment (FAC) orders | **Good** | rate cases (only FAC so far); I&M, CenterPoint |
| **MI** | MISO | 4 | Consumers + DTE (both dominant) ✓ | Liberty distribution-reliability audits (Pt 1+2) | **Good** | rate-case / PSCR fuel orders |
| **MO** | MISO/SPP | 7 | Ameren MO, Empire/Liberty | **staff prudence-review reports** + testimony | **Good** | Evergy (KCP&L); more FAC prudence years |
| **WI** | MISO | 3 | MGE, NSP-WI, We Energies | direct testimony (rate / large-load) | **Good** | WPS, Alliant/WPL; final orders |
| **ND** | MISO | 4 | Montana-Dakota, NSP, Otter Tail (all 3) ✓ | rider updates (RRCA/TCA), dual-fuel, testimony | **Good** | Commission *orders* (have filings) |
| **FL** | (non-RTO) | 7 | FPL, Duke FL, TECO, FPUC (collectively) | cost-recovery **clause** final orders (fuel/nuclear/storm/env/conservation) | **Good** | per-utility base-rate cases |
| **AR** | MISO/SPP | 3 | Entergy Arkansas | FRP order + application + testimony | **Partial** | SWEPCO, OG&E, Empire |
| **CO** | (non-RTO) | 3 | Public Service Co (Xcel) — dominant | rate-case advice letter, decision, gas transcript | **Partial** | Black Hills; deeper testimony walk |
| **IL** | MISO/PJM | 4 | ComEd | final order + testimony + reconciliation | **Partial** | Ameren Illinois (2nd major IOU) |
| **LA** | MISO | 3 | Entergy Louisiana | settlement + testimony | **Partial** | SWEPCO, Cleco, Entergy New Orleans; Grand Gulf refund |
| **MD** | PJM | 2 | BGE, Potomac Edison | MYRP + rate-case orders | **Partial** | Pepco MD, Delmarva MD |
| **NJ** | PJM | 3 | PSE&G, JCP&L (+ BGS) | base-rate + BGS procurement orders | **Partial** | Atlantic City Electric (ACE) |
| **SC** | (non-RTO) | 3 | Dominion Energy SC | fuel-cost review (proposed order, settlement, testimony) | **Partial** | Duke Energy Carolinas/Progress SC |
| **SD** | MISO/SPP | 3 | Otter Tail, MidAmerican, Montana-Dakota (3 of 6) | rider petition + TCR cost-recovery applications | **Partial** | NSP, Black Hills, NorthWestern |
| **WV** | PJM | 2 | Appalachian/Wheeling Power | ENEC fuel-cost review orders (incl. $231.8M disallowance) | **Partial** | Mon Power / Potomac Edison (FirstEnergy) |
| **GA** | (non-RTO) | 4 | Georgia Power (dominant) | direct testimony only (IRP / rate) | **Partial** | a final **order** (all testimony today) |
| **TX** | ERCOT/(SPP) | 4 | El Paso Electric | fuel reconciliation testimony + preliminary order | **Thin** | Oncor, CenterPoint, AEP TX, SWEPCO, Entergy TX (huge state, 1 of ~7) |
| **MN** | MISO | 2 | NSP/Xcel | ALJ reports (gas rate + electric) | **Thin** | Minnesota Power, Otter Tail; only 1 IOU |
| **OH** | PJM | 2 | FirstEnergy Ohio | ESP stipulation + commission entry | **Thin** | AEP Ohio, Duke Ohio, AES Ohio (WAF-limited → browser-capture) |
| **DE** | PJM | 1 | Delmarva (main IOU) | one base-rate order | **Thin** | only 1 doc; DP&L gas, more orders |
| **MS** | MISO/SERC | 2 | — (MPUS *staff annual reports*, not utility-specific) | utilities-staff annual reports | **Thin** | Entergy MS, Mississippi Power proceedings; InSite TLS-broken |
| **ID** | (WECC, non-RTO) | 2 | Idaho Power | annual **PCA** orders (36618, 35421) | **Partial** | Avista, Rocky Mountain Power PCA |
| **OR** | (WECC, non-RTO) | 2 | PGE + PacifiCorp | **PCAM** power-cost orders | **Partial** | Idaho Power, Avista; GRCs |
| **WA** | (WECC, non-RTO) | 1 | Puget Sound Energy | deferred-accounting order (UE-220066) | **Thin** | Avista, PacifiCorp; the actual power-cost order |
| **MT** | WECC/(MISO) | 1 | NorthWestern Energy | general rate-case final order (PCCAM base) | **Thin** | 2024/25 rate case; Montana-Dakota |
| **NV** | (WECC, non-RTO) | 1 | NV Energy | 2025 GRC notice (25-02016) | **Thin** | the annual **DEAA** fuel-prudence order (higher value) |

## Fully missing (no seed yet)

- **MISO gaps:** **IA** (`efs.iowa.gov`, WAF → browser-capture + `fetch=false`); **MT** now cracked (see below).
- **Southwest + Pacific Northwest (recipes in [data-sources.md](data-sources.md)):** **WA, OR, ID, NV, MT** now seeded (7 docs — in the table above); deepen each with its power-cost-adjustment / DEAA / PCA / PCCAM order. **AZ** (broken TLS on the eDocket image host → browser-capture) and **NM** (new PRCe360 registration wall) remain blocked.
- **Large untapped:** **CA** (CPUC — PG&E/SCE/SDG&E, huge), **NY** (DPS DMM — Con Ed/National Grid), plus KS, OK, NE, MA, CT, TN, AL. The corpus is currently **East / Midwest / South** weighted.

## Headline reads

- **Strongest:** PA (only parsed-findings state), VA, DC — full IOU coverage + on-theme orders.
- **Best on-theme depth:** MO (staff prudence reviews), WV (ENEC disallowances), FL (5 cost-recovery clauses), IN/KY (FAC).
- **Single-IOU samplers needing a 2nd IOU:** IL (+Ameren), LA (+SWEPCO/Cleco), SC (+Duke), NJ (+ACE), CO (+Black Hills).
- **Thinnest, highest upside:** TX (1 of ~7 IOUs in the largest market), MS (generic staff reports, no utility proceeding), DE (1 doc), MN/OH (1 IOU each).
- **Common shape:** most states are 2–4 docs / 1–2 IOUs / one doc type. Deepening *within* cracked portals (proven recipes) is higher-yield than new states — except CA/NY, whose scale justifies the portal work.
