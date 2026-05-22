# Backlog

Ideas, features, enhancements. Each item: brief description + priority (**low / med / high**). Reprioritize periodically; demote stale "high" items rather than letting them rot.

## Pipeline & data

- **[high] Process the full FY2015–present corpus.** v1 runs the full E2E pipeline (extract → structure → patterns) on only the **2 most-recent** reports, by design. Scale it to every downloaded PDF once the slice is proven.
- **[high] OCR fallback for scanned reports.** Born-digital PDFs extract cleanly with pdfplumber/PyMuPDF. Older/scanned reports need real OCR. Add a tesseract-based fallback (`brew install tesseract` + `pytesseract`) behind an `--ocr` flag. **Run the security sweep before installing.** Pages under `MIN_TEXT_CHARS_PER_PAGE` are already flagged as image-only.
- **[med] Incremental listing refresh.** Re-capture `/audits` and append only new reports (idempotent by docket number).
- **[med] eLibrary docket resolution.** Some reports link via an eLibrary docket rather than a static PDF. Resolve those dockets to downloadable URLs.
- **[med] Detailed-section (Section IV) parsing.** v1 parses the Executive Summary (clean + consistent). The *detailed* findings carry dollar impacts, CFR / USofA-account citations, and "Pertinent Guidance" — extract these into `amount_usd`, `regulations[]`, and richer per-finding text.
- **[med] Capture the company-response section.** Each report ends with the audited entity's response (agree/disagree + remediation plan). Parse it onto each report/finding.
- **[med] Listing freshness vs. live.** The seed is the 2026-02-03 Wayback snapshot (covers 2019–2025). Anything FERC issued after that is missing. Refresh via a real browser to catch newer reports, then re-sort "most recent."
- **[low] Multi-docket reports.** The listing parser captures one docket per report; some reports cite several. Handle the multi-docket case.
- **[low] Pull related Commission orders.** Audit reports cite related orders; fetch and cross-reference them.

## Analysis

- **[done] Audit-type facet (FA vs PA).** Two types per FERC: **FA = Financial Audit**, **PA = Non-Financial Audit** (compliance/operational). Derived from the docket prefix; shipped as `audit_type` + a site filter.
- **[high] Form/industry is a mix, not all Form 1.** Audited entities span electric utilities (Form 1), gas pipelines (Form 2), oil pipelines (Form 6), and market operators (ISOs/RTOs). A true "Form 1 tool" would filter to electric FA audits; decide whether to scope down or keep the broader explorer (current). Industry is already parsed; surface it + a Form-1-only view.
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
