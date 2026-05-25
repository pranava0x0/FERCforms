# Backlog

Ideas, features, enhancements. Each item: brief description + priority (**low / med / high**). Reprioritize periodically; demote stale "high" items rather than letting them rot.

## Pipeline & data

- **[done] Process the full corpus — all forms, all years.** Every report — electric (Form 1), gas (Form 2), oil (Form 6), FA + PA — is extracted → structured → mined. FY2014-2018 (49 reports) were backfilled from a Wayback /audits snapshot via `pipeline.backfill` (ferc.gov-origin only); the live page covers 2019+.
- **[high] FY2014-2018 findings parser.** ~9-10 backfill reports (e.g., CAISO PA17-3, PacifiCorp FA16-4, Dominion FA15-16) show 0 findings because the older format uses a combined "Summary of **Compliance** Findings and Other Matter" exec-summary and `(cid:9)` tab-leader TOCs, not the 2019+ "Summary of **Noncompliance** Findings" + dotted-leader layout. A naive header/leader extension regressed the validated 2019+ path (Cleco 12→1) and over-counted others (MISO 3→7) — see [ISSUES.md](ISSUES.md). Build a **separate** parser path for the FY2014-2018 era, selected by era/format detection so it can never alter the 2019+ output; validate against a no-regression snapshot of current finding counts.
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
- **[med] Verify the mobile layout visually.** Mobile CSS (single-column, bottom-sheet filters, KPI scroll-snap) is implemented but was **not visually confirmed** this session (the Chrome screenshot tool is fixed-width; the preview server is sandbox-blocked). Check at 375px before claiming mobile-done.
- **[low] "Compare two reports" view.** Side-by-side findings/themes for two selected reports.

## Quality & testing

- **[med] Listing↔PDF integrity check.** A test/CLI confirming every `listing.json` entry resolves to a downloadable PDF — catches eLibrary API changes early.
- **[low] Accessibility / Lighthouse pass.** Audit contrast, focus order, and performance once the site is deployed.

## LLM-readability (llms.txt)

- **[med] Absolute URLs in llms.txt once a deploy domain exists.** `llms.txt`/`llms-full.txt` currently use site-root-relative links (no domain fixed yet). The llmstxt.org convention prefers absolute URLs for portability — switch when the GitHub Pages URL is known (thread it through `pipeline/llmstxt.py`).
- **[low] Per-report markdown pages + an llms.txt link section to them.** Static `report/<id>.md` pages would give LLMs (and humans) stable per-report URLs to cite.

## Infra

- **[done] GitHub Pages deploy.** `.github/workflows/deploy.yml` publishes `docs/` to Pages on push to `main`. Repo: github.com/pranava0x0/FERCforms. (Next: revisit absolute llms.txt URLs now that the domain is known — pranava0x0.github.io/FERCforms.)
