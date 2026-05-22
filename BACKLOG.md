# Backlog

Ideas, features, enhancements. Each item: brief description + priority (**low / med / high**). Reprioritize periodically; demote stale "high" items rather than letting them rot.

## Pipeline & data

- **[high] Process the full FY2015–present corpus.** v1 runs the full E2E pipeline (extract → structure → patterns) on only the **2 most-recent** reports, by design. Scale it to every downloaded PDF once the slice is proven.
- **[high] OCR fallback for scanned reports.** Born-digital PDFs extract cleanly with pdfplumber/PyMuPDF. Older/scanned reports need real OCR. Add a tesseract-based fallback (`brew install tesseract` + `pytesseract`) behind an `--ocr` flag. **Run the security sweep before installing.** Pages under `MIN_TEXT_CHARS_PER_PAGE` are already flagged as image-only.
- **[med] Incremental listing refresh.** Re-capture `/audits` and append only new reports (idempotent by docket number).
- **[med] eLibrary docket resolution.** Some reports link via an eLibrary docket rather than a static PDF. Resolve those dockets to downloadable URLs.
- **[low] Pull related Commission orders.** Audit reports cite related orders; fetch and cross-reference them.

## Analysis

- **[high] Finding taxonomy.** A controlled vocabulary of finding types (accounting misclassification, formula-rate inputs, affiliate transactions, capitalization vs expense, etc.); tag every finding.
- **[med] Cross-report trend charts.** Findings per year, per company, per category.
- **[low] Recommendation-outcome tracking.** Did the company implement the recommendation? (Annual Reports on Enforcement note status.)

## The bigger vision

- **[high] "Audit-my-document" mode.** The longer-term goal: feed in an application/filing and flag likely issues using the pattern library mined from historical audits. v1 builds that library; this feature consumes it.

## Design / UI — theme variants to A/B (user wants to test which sticks)

- **[med] Wave-style threaded theme.** Google Wave inspiration: findings as threaded/conversational items with an inbox-like reading flow. Swappable.
- **[med] Editorial + periwinkle theme.** Restrained FT/ProPublica public-record look, periwinkle accents. Swappable.
- **[low] Runtime theme switcher.** Toggle Plus-stream / Wave-threaded / Editorial to decide which the user prefers (chosen v1 = Plus-stream).

## Infra

- **[low] GitHub Pages deploy workflow.** GitHub Action to publish `docs/` on push to `main`.
