# Backlog

Ideas, features, enhancements. Each item: brief description + priority (**low / med / high**). Reprioritize periodically; demote stale "high" items rather than letting them rot.

---

> ## ▶ RESUME HERE — multi-source expansion (paused 2026-06-01)
>
> **Goal:** add FERC prudence reviews + state PUC/PSC/SCC audits (VA, OH, MI, IL, TX, SC, PA, NC) as new tabs. Get 3–5 docs/source to validate, then collect all. **Official `.gov` sources ONLY** (user constraint — enforced in `pipeline/sources.load_seed`, raises on non-gov). Non-fitting legal docs are **metadata-only** (source link + provenance, `structured=False` → "Listed for reference"; no findings parse, no LLM).
>
> **DONE & committed (phase 1 — 5 commits on this branch):** 3 tabs (FERC Audits / Prudence Reviews / State PUC Audits), each with own baked stats/patterns (`docs/data/patterns_by_collection.json`). Sources: **PA** (4 PA PUC Bureau of Audits), **MI** (4 Liberty Consulting U-21305), **FERC prudence** (5 eLibrary formal-challenge/ALJ orders 2015–2025). Tabs = 120 / 5 / 8 (State PUC → 13 after VA, below). Pipeline: `pipeline/sources.py` ← `data/seeds/*.json`; `python -m pipeline.sources --seed <file>` then `python -m pipeline.build`.
>
> **DONE (phase 2) — VA SCC shipped (commit `3d2fe3e`).** 5 Virginia SCC orders, metadata-only, each page-1-read & labelled: biennial review `PUR-2025-00058` (89g601), Rider T1 transmission RAC `PUR-2025-00076` (873b01), Rider DIST distribution RAC `PUR-2024-00137` (816l01, an Order for Notice & Hearing), Appalachian net metering `PUR-2024-00161` (87nd01), Chesterfield CPCN+Rider CERC `PUR-2025-00037` (89g501). Dominion ×4 + APCo ×1; tab now **13**. `data/seeds/va_scc.json`. **Gotchas for the next state:** (a) bare `scc.virginia.gov` **307-redirects to `www.scc.virginia.gov`** — seed the `www.` URL so the fetch doesn't bounce; (b) the SCC DocketSearch **search API is a hash-routed SPA, not curl-resolvable**, so the companion fuel-factor order `PUR-2025-00059` (referenced inside the biennial review) was **not** added — grab it via a browser/Chrome MCP if wanted.
>
> **NEXT — phase 2 remaining (IL / SC / TX, metadata-only).** Same discipline: docket orders/testimony with **opaque doc IDs** — each must be fetched + page-1-read to label company/date/doc_type accurately (the PGW implementation-plan-vs-audit mislabel is why). Verified-resolving candidate URLs (all `.gov`):
> - **TX PUCT** `interchange.puc.texas.gov/Documents/{control}_{item}_{docid}.PDF` — e.g. `57149_114_1483150` (El Paso Electric fuel reconciliation), `55999_168_1550025`, `58211_13_1526279`. Some scanned → OCR.
> - **IL ICC** `icc.illinois.gov/docket/P{YYYY}-{NNNN}/documents/{docId}/files/{fileId}.pdf` — e.g. `P2024-0087` (ComEd CFRA).
> - **SC** `dms.psc.sc.gov/Attachments/Matter/{guid}` + `ors.sc.gov/sites/scors/files/...` (ORS testimony; opaque guids via DMS docket search).
> Workflow per state: write `data/seeds/<state>.json` (collection `state_audit`) → `python -m pipeline.sources --seed …` → `python -m pipeline.build` → verify tab → **commit per state**.
>
> **THEN — phase 3 (OH / NC).** WAF-blocked, need browser-capture/cookie-dance: OH PUCO DIS `dis.puc.state.oh.us` (F5 ASM), NC NCUC `starw1.ncuc.gov` (Cloudflare). OH has the richest consultant audits.
>
> **Loose ends:** (1) 4/5 prudence records are **0-page** (eLibrary throttled the ingest run) — re-run `python -m pipeline.sources --seed data/seeds/ferc_prudence.json` when eLibrary is quiet to backfill page counts (idempotent; cached ISO-NE skips). (2) PA/MI **findings parser** for the clean management-audit subset is high-priority below. Full detail in the *Multi-source expansion* section. Access map per regulator in [ISSUES.md](ISSUES.md).

---

> **Policy-analyst review (2026-06-01).** Read through the eyes of a load-growth / data-center / affordability / speed-to-power analyst. Verdict: the corpus answers **affordability only, and only indirectly** — the over-recovery / costs-wrongly-charged-to-ratepayers angle. It is **silent** on load growth, data centers, co-location, and queue/speed (`data center` 0, `queue` 0, `Order 2023` 0 across all 599 findings). Items tagged *(policy 2026-06-01)* below either sharpen the affordability angle the data *can* support, or record the scope gap.

## Multi-source expansion (prudence reviews + state PUC audits)

*Added 2026-06-01. The explorer now spans three collections/tabs — FERC Audits, Prudence Reviews, State PUC Audits — each with its own baked stats/patterns. Prudence + state docs are ingested metadata-only via `pipeline/sources.py` (see [DATA_STRUCTURE.md §8](DATA_STRUCTURE.md) and [AGENTS.md](AGENTS.md)).*

- **[done] Collections + tabs foundation.** `collection`/`jurisdiction`/`source`/`doc_type`/`structured` on `AuditReport` (defaulted so FERC stays valid); 3 UI tabs with per-tab KPIs/patterns/trends/facets + honest per-tab empty + "Listed for reference" states; `patterns_by_collection.json`.
- **[done] State PUC: PA + MI.** PA PUC Bureau of Audits (4 management/focused audits, 2022–2025) and MI MPSC Liberty Consulting U-21305 distribution audits (Consumers + DTE, 2024). Metadata-only, verified against PA/MI press releases.
- **[done] FERC prudence (seed).** eLibrary `Search/AdvancedSearch` full-text discovery → 5 formal-challenge orders + an ALJ initial decision (2015–2025), fetched via the F5 cookie dance, metadata-only.
- **[high] Findings parser for the clean PA/MI management-audit subset.** PA M&O audits expose findings as per-chapter "Findings, Conclusions, and Recommendations" prose; PA focused audits + some others use multi-column summary tables that linearize messily (the reason these are metadata-only today). Build a `parse=True` extractor (verbatim, no LLM) **gated by a no-regression snapshot** like the FERC parser, with real table handling. Flip `parse` on a per-seed basis as coverage proves out.
- **[med] Phase-2 states — IL / SC / TX (metadata-only).** **VA SCC done** (5 orders, commit `3d2fe3e`; seed `data/seeds/va_scc.json`). Remaining are open-access but order/testimony-heavy: IL ICC e-Docket, SC PSC DMS + ORS, TX PUCT Interchange `Documents/{control}_{item}_{docid}.PDF` (some scanned → OCR). Add a seed per state. See [ISSUES.md](ISSUES.md) for access mechanics.
- **[med] Phase-3 states — OH / NC (WAF-blocked).** OH PUCO DIS (F5 ASM) and NC NCUC `starw1` (Cloudflare) reject scripted requests — same class as FERC's /audits. Needs a browser-capture / cookie-dance step (reuse the eLibrary pattern). OH has the richest consultant audits; defer until the WAF step exists.
- **[med] Automate FERC prudence discovery.** Today the prudence seed is hand-curated from `AdvancedSearch` results. Add a `pipeline/prudence.py` that queries eLibrary full-text (formal-challenge / imprudent / disallowance, by date range + `ER`/`EL` docket), filters incidental mentions, and emits the seed — the discovery is the hard part (a single month of "imprudent" returns ~2,900 hits, mostly incidental).

## Pipeline & data

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
- **[med] Full-text search across report bodies.** v1 search covers titles/summaries; index the full extracted text for deeper queries.
- **[high] Ratepayer-impact lens — dollar magnitude.** *(promoted from low — policy 2026-06-01. **Count-based half shipped** 2026-06-01: the "Cost to customers" filter + badge + a 69/120-report stat — see Finding taxonomy above. This item is now the **$ magnitude**.)* Once `amount_usd` is extracted (Section IV parsing), sum quantified impacts by theme / company / year and lead with a headline stat — e.g. *"$X improperly recovered from customers 2014–2025; $Y of it below-the-line lobbying/charity/dues."* Turns the count into a quantified over-recovery dataset — the one affordability story this corpus can actually tell. Depends on Section IV parsing above.
- **[med] Interconnection & transparency facet.** *(policy 2026-06-01.)* 27 findings touch interconnection — but as *transparency-posting* compliance ("Posting of Generator Interconnection Study Times," capability info, short-circuit data), **not** queue speed or interconnection cost. Tag + facet them so the narrow question *"do utilities even comply with the postings meant to support interconnection?"* is answerable. Honest ceiling: says nothing about how fast anyone connects.
- **[med] Filtered CSV export + stable per-report cite URLs.** *(policy 2026-06-01: analysts cite and re-analyze.)* Let a user download the currently-filtered finding set as CSV, and give each report a stable anchor/URL to cite. Pure presentation over the already-baked `docs/data/*.json`; pairs with the `[low]` per-report markdown pages under LLM-readability.

## The bigger vision

- **[high] "Audit-my-document" mode.** The longer-term goal: feed in an application/filing and flag likely issues using the pattern library mined from historical audits. v1 builds that library; this feature consumes it.
- **[med] Ingest the underlying FERC Form 1 financial data (via PUDL).** The audits scrutinize the *numbers* in Form 1/2/6. FERC publishes that data in formats needing special software — Visual FoxPro `.DBF` (1994–2020) and XBRL (2021+) — painful on macOS. Use **PUDL** (catalystcoop, pip-installable, SQLite/Parquet output) to ingest it with **no FERC installer**, then cross-reference audit findings against the reported figures.
- **[high — large] Second module: forward-looking FERC dockets (not audits).** *(policy 2026-06-01: the audit corpus is **silent** on load growth, data centers, co-location and queue/speed.)* Those decisions live in *proceedings*, not audits — Order 2023 (interconnection queue reform), Order 1920 (long-term transmission planning), large-load / co-location dockets (e.g. the PJM–Susquehanna/AWS ISA proceeding), data-center tariff filings. A **separate** module that ingests those eLibrary dockets, **not** a tweak to the Audit Explorer (the audit pattern-library doesn't transfer). Big scope; fits the multi-module north star.

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
