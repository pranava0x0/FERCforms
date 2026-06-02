# UAT Baseline — FERC Audit Explorer

_Created: 2026-05-31_
_Last run: 2026-06-02_

## Project Info
- **Stack**: static vanilla HTML/CSS/JS (no framework, no build). Python CLI pipeline bakes `docs/data/*.json`.
- **Dev server**: Preview MCP, launch config `ferc-site` → `python -m http.server 8766 -d docs` (`.claude/launch.json`). Or `python -m http.server -d docs 8000`.
- **Entry point**: `docs/index.html` · logic `docs/js/app.js` · styles `docs/css/styles.css` · data `docs/data/{reports,patterns,meta}.json`.
- **Routes**: single page (the explorer). No client router.

## Critical Flows (run every time)
1. **Load** → KPIs (120 / 599 / 1505 / 13), Top-patterns band renders ranked cards, stream lists reports newest-first (Kern River, Sept 2025 first). No console errors.
2. **Pattern filter** → tap a band card (e.g. Depreciation) → stream narrows (40 reports), active chip appears, card shows `aria-pressed=true`, "Filters · 1".
3. **Active chip remove** → tap the chip's ✕ (or "Clear all") → resets to 120/599, band card un-pressed.
4. **Filter algebra** → within a group OR (Electric+Gas = 100), across groups AND (+Depreciation = 24).
5. **Empty state** → nonsense search → "No reports match…" card + "Clear filters".
6. **Zero-finding card** → open SDG&E (FA19-3) → muted "No findings extracted" pill + honest note + working eLibrary link (26 such reports).
7. **Mobile filter sheet** (≤1023px) → "Filters" opens bottom sheet; close via **backdrop tap**, **Done**, or **Escape**. (Regression guard for UAT fix below.)
8. **Theme toggle** → light/dark swap persists to `localStorage` (`ferc-theme`).

## Sections & Last Tested
| Section | Last Tested | Notes |
|---------|-------------|-------|
| Desktop (1280) | 2026-06-02 | Stable; load + pattern filter + empty state re-verified |
| Tablet (768) | 2026-05-31 | Stable; band = horizontal scroll-snap; bottom-sheet filters |
| Mobile (375) | 2026-06-02 | Stable; no horizontal overflow at 375px; dark mode renders cleanly |
| Top-patterns band | 2026-06-02 | Stable; Depreciation→40 reports, aria-pressed sync verified |
| Filters (rail + sheet) | 2026-06-02 | Empty state ("No reports match… Clear filters") verified |
| Theme toggle | 2026-06-02 | Persists (`ferc-theme`); light↔dark, `data-theme` flips |

## Known Stable Areas
Filter algebra (OR within / AND across), active chips, empty state, zero-finding rendering, default newest-first sort, theme persistence.

## Known Flaky / Unstable Areas
- None observed. (Preview MCP screenshots render blank at large scroll offsets — a tooling quirk, not a site bug; capture near scroll 0 or hide upper sections.)

## Exploration Notes
- **FERC-form facet is noisy** — lists incidentally-cited forms (No. 549/552/714…), not just the audited form. Low-pri BACKLOG item, not a UAT bug.
- The patterns band shows corpus-wide counts (not the filtered subset) by design — it's a global nav, per its heading.
- Next runs: try keyboard-only nav end-to-end; rapid pattern toggle; very long search strings; `prefers-reduced-motion`.

## Performance (audited 2026-06-02)
- **7 requests, no third-party/font/framework calls.** Wire payload ≈ **207 KB gzip** (raw ≈ 1.31 MB): `reports.json` 1.23 MB→185 KB, `app.js` 29 KB→8.8 KB, `styles.css` 21 KB→5.2 KB, `index.html` 8.9 KB→3.1 KB, three small JSONs. GitHub Pages serves gzip, so the wire cost is fine for a data-heavy explorer.
- **`reports.json` preload is correct — do NOT "fix" the `crossorigin`.** Resource Timing confirms it's fetched **once** (`initiatorType: "link"`); `app.js`'s same-origin `fetch()` reuses the preload (no double-download, no "preloaded but not used" warning). A static read of `index.html` makes the `crossorigin="anonymous"` preload look like a CORS mismatch, but the browser reuses it here — verified, leave it.
- Run perf the same way next time: serve docs, `performance.getEntriesByType('resource')` for fetch counts; `gzip -c <file> | wc -c` for wire sizes.
