# Backlog

Ideas, features, enhancements. Each item: brief description + priority (**low / med / high**). Reprioritize periodically; demote stale "high" items rather than letting them rot.

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
- **[med] Detailed-section (Section IV) parsing.** v1 parses the Executive Summary (clean + consistent). The *detailed* findings carry dollar impacts, CFR / USofA-account citations, and "Pertinent Guidance" — extract these into `amount_usd`, `regulations[]`, and richer per-finding text.
- **[med] Capture the company-response section.** Each report ends with the audited entity's response (agree/disagree + remediation plan). Parse it onto each report/finding.
- **[done] Listing freshness vs. live.** Re-checked the live /audits page via a real browser on 2026-05-25 — byte-identical to the 2026-02-03 snapshot (no audits issued since Sept 2025). Re-run when FERC publishes new reports (incremental by accession).
- **[low] Multi-docket reports.** The listing parser captures one docket per report; some reports cite several. Handle the multi-docket case.
- **[low] Pull related Commission orders.** Audit reports cite related orders; fetch and cross-reference them.

## Analysis

- **[done] Audit-type facet (FA vs PA).** Two types per FERC: **FA = Financial Audit**, **PA = Non-Financial Audit** (compliance/operational). Derived from the docket prefix; shipped as `audit_type` + a site filter.
- **[done] Form/industry mix → broad explorer.** Decision: keep the broad explorer covering electric (Form 1), gas (Form 2) and oil (Form 6) rather than scoping to Form 1 only. Industry is parsed and shipped as a site filter (Electric / Gas / Oil).
- **[low] FERC-form facet lists incidentally-cited forms.** `detect_forms()` captures every "FERC Form No. X" mention, so the site's Form filter shows forms a report merely *cites* (No. 549, 552, 714, …) next to the audited form — noisy and a bit confusing. Distinguish the report's primary/audited form from cited forms and facet on the former.
- **[high] Finding taxonomy.** A controlled vocabulary of finding types (accounting misclassification, formula-rate inputs, affiliate transactions, capitalization vs expense, etc.); tag every finding.
- **[med] Cross-report trend charts.** Findings per year, per company, per category.
- **[low] Recommendation-outcome tracking.** Did the company implement the recommendation? (Annual Reports on Enforcement note status.)
- **[med] Full-text search across report bodies.** v1 search covers titles/summaries; index the full extracted text for deeper queries.
- **[low] Dollar-impact aggregation.** Once `amount_usd` is extracted, sum quantified impacts by theme / company / year.

## The bigger vision

- **[high] "Audit-my-document" mode.** The longer-term goal: feed in an application/filing and flag likely issues using the pattern library mined from historical audits. v1 builds that library; this feature consumes it.
- **[med] Ingest the underlying FERC Form 1 financial data (via PUDL).** The audits scrutinize the *numbers* in Form 1/2/6. FERC publishes that data in formats needing special software — Visual FoxPro `.DBF` (1994–2020) and XBRL (2021+) — painful on macOS. Use **PUDL** (catalystcoop, pip-installable, SQLite/Parquet output) to ingest it with **no FERC installer**, then cross-reference audit findings against the reported figures.

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
