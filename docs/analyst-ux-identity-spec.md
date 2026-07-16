# Spec — Analyst-grade UX, interaction model & visual identity refresh

> **Status: SPEC / not yet scheduled.** Written 2026-07-16. Backlog placeholder: BACKLOG.md → "Design / UI".
> Evaluated from two personas — a **FERC/regulatory analyst** (works with dockets daily, cites sources,
> re-analyzes data) and a **general energy-sector reader** (PM/consultant/investor/journalist who knows
> the industry but not FERC audit mechanics). Also mines the **LBNL Energy Markets & Policy**
> (emp.lbl.gov) data-product conventions for transferable ideas (Part D).
>
> Constraints inherited from CLAUDE.md/DESIGN.md and NOT revisited here: zero-backend static site,
> vanilla JS, no framework, verbatim findings only, no compliance scores, no LLM editorial, data is
> the product. Everything below is presentation + baked-JSON work on the existing pipeline.

---

## 0. Current-state audit (what the evaluation found, 2026-07-16)

Reviewed at 375 / 768 / 1280 px, light + dark, on the live worktree build (440 reports, 813 findings).

**What already works well** (keep): verbatim finding threads with theme tags; per-tab patterns band
with honest counts ("76 of 123 audits · 62%"); active-filter chips; per-tab facets; bottom-sheet
filters on mobile; `<details>` expand; citation copy; theme-before-paint; llms.txt suite; footer
provenance.

**Findings** (numbered; referenced by the work items in Parts A–C):

- **F1 — Collapsed cards have almost no information scent.** A card shows company, docket, date and
  count pills only. No audit subject, no theme chips, no dollar signal. An analyst scanning "Southern
  Electric Generating Co · 4 findings" learns nothing about *what* was found; the `.headline` style
  exists in styles.css but is never rendered by `cardNode()` (docs/js/app.js).
- **F2 — The "0 recs" pill is misleading.** Reports whose recommendations weren't parsed (e.g. Duke
  Energy Progress FA23-6, 11 findings) show "0 recs", which reads as "auditors made no
  recommendations" — false for essentially every FERC audit. Render nothing (or "recs not extracted")
  when `finding.recommendations` is absent rather than a zero count.
- **F3 — No shareable state.** Tab, filters, search, and open report are all ephemeral. Analysts
  cite and share; today there is no way to link a colleague to "affiliate findings, 2022+, gas" or to
  a specific report card. (Backlog already wants "stable per-report cite URLs" — this generalizes it.)
- **F4 — Whole-corpus DOM render.** `applyFilters()` renders every matching card at once (123 on the
  FERC tab). During the review, scrolling produced multi-second blank (checkerboard) frames and two
  30s-timeout scroll interactions. DESIGN.md §10 prescribes pagination + IntersectionObserver; the
  stream doesn't implement it.
- **F5 — First-paint payload carries the full corpus text.** `reports.json` is 1.96 MB raw / ~317 KB
  gz and includes every finding + recommendation body for all 440 reports, preloaded in `<head>`.
  Card rendering needs ~10 metadata fields; finding bodies are needed only on expand.
- **F6 — Stale build artifact ships with the site.** `docs/data/reports_pre_cost_extraction.json`
  (3.4 MB) is deployed dead weight (never fetched). Also `cross_links.json` (363 KB) is baked but no
  UI or llms.txt consumer reads it — surface it or stop shipping it (see A10).
- **F7 — No sort control.** Newest-first only. Analysts want most-findings, most-$, company A–Z,
  oldest-first (era comparisons).
- **F8 — Low scan density on desktop/tablet.** One full-width sparse card per report (~6 cards per
  1024px screen). Fine for reading, weak for scanning 123 rows. No compact/ledger view.
- **F9 — Mobile ergonomics.** The Filters toggle lives in the stream toolbar and scrolls away — from
  card #10 you can't change filters without scrolling back up. Sub-meta wraps mid-phrase
  ("Issued ⏎ September 29, 2025"). No back-to-top affordance on a 123-card page.
- **F10 — Search is opaque.** Substring match over company+docket+finding text, but no highlighting,
  no indication of *why* a report matched, no findings-only toggle. (Full-text body search is already
  a backlog [med] — this is about the UX of the search that exists.)
- **F11 — The dollar story is invisible at stream level.** 60 findings carry cited `amount_usd`
  ($ pill on the finding), but nothing aggregates them; dollar figures sitting verbatim inside
  finding text (e.g. Duke FA23-6 "$3,500,000") are invisible until a card is opened. The corpus's
  one affordability headline ("$X improperly recovered") has no surface. (Depends on the
  `amounts_enrich` scale-out already queued as P1 #4.)
- **F12 — No company lens.** The same utilities recur across FERC audits, state audits, and rate
  cases (that's what `cross_links.json` was built for), but there's no company facet, no "other
  documents about this company", no repeat-audit signal.
- **F13 — Jargon walls for the general reader.** "FA/PA", "Docket No.", "Prudence Reviews",
  "State Reference Docs" are unexplained in the chrome (About covers some, one click away).
  Tab labels are long and overflow-scroll on mobile. No plain-English "what is a FERC audit, why
  should I care" on the main page beyond one lead sentence.
- **F14 — Identity reads "generic AI-pastel dashboard".** Rounded pastel cards + circle avatars +
  soft purple wash is the default look of a thousand LLM-generated dashboards (and adjacent to
  Anthropic/Claude's own soft-serif-on-wash aesthetic the user explicitly wants distance from).
  The periwinkle anchor is right; the *treatment* needs to become unmistakably "public record".
- **F15 — Semantic color drift.** Recommendation blue (#2F73C4) is analogous to the periwinkle
  brand accent (hue 212° vs 240°) — at pill/dot size they read as the same family, so "staff
  recommendation" markers look like links/brand chrome. DESIGN.md §3.1 (meaning ≠ brand) argues for
  more hue distance.

---

## 1. Personas & jobs-to-be-done

**P-A: FERC/regulatory analyst** (rates analyst, regulatory affairs, enforcement counsel, PUC staff).
Jobs: (1) "What has FERC flagged about {company / theme / account}?" (2) "Cite this finding in a
memo" (3) "Get the underlying data into my own spreadsheet" (4) "What's new since I last looked?"
(5) "Is this issue systemic or one-off?" Needs: permalinks, exports, dollar figures, docket links,
precision about what's parsed vs listed-for-reference, dense scannable views, trust cues
(methodology, coverage, as-of dates).

**P-B: General energy-sector reader.** Jobs: (1) "What do utilities most often get wrong?"
(2) "Has {my company / my counterparty} been audited, and what happened?" (3) "Give me the headline
numbers for a deck." Needs: plain-English framing, glossary-on-hover, strong headline stats, a
shareable link/graphic, no acronym walls.

Design rule of thumb used below: **P-A gets density, precision, and export; P-B gets orientation,
narrative, and headlines. Neither gets paraphrased findings.**

---

## Part A — Content & analysis features

### A1. URL state + permalinks (fixes F3) — the highest-leverage analyst feature
- Encode tab, filters, search, sort, and open-report id in the URL hash
  (`#/state_audit?theme=Depreciation&year=2024&open=<report-id>`), restored on load. Hash (not
  query) keeps GitHub Pages cache-friendly and avoids server 404s.
- Every card gets a visible **Link** action (copies the deep link; sits beside "Copy citation").
  Findings get `id="f-<report>-<n>"` anchors so a citation can point at one finding.
- The already-planned per-report markdown/HTML pages (backlog [low]) become the crawlable/citable
  twin of the hash deep-link; `citationText()` should append the permalink.
- Acceptance: reload restores exact view; opening a shared link scrolls to + expands the report;
  copy-citation includes the permalink; browser back/forward walks filter states.

### A2. Card information scent (fixes F1, F2)
- Add a one-line **subject** to the collapsed card: FERC audits already have a subject implicit in
  scope/`functions`/`audit_period`; state docs have `doc_type`. Compose mechanically (no LLM):
  `"{audit_type} audit — {audit_period}"` for FERC; `doc_type` title-cased for the rest. Never
  paraphrase findings.
- Show up to 3 **top theme chips** on the collapsed card (`report.themes` already exists), + a
  `+N more` count. Themes are the single best scent for both personas.
- Show the report-level **$ pill** (max or sum of its findings' `amount_usd`) when present.
- Fix F2: recommendation pill renders only when any finding has parsed recs; otherwise omit.
- The "Cost to customers" amber badge, currently only a finding tag + filter, gets a compact card
  presence (small amber dot/edge tick) — the highest-salience axis for P-B.

### A3. Sort + view density (fixes F7, F8)
- Sort control in the stream toolbar: Newest (default) · Oldest · Most findings · Largest $ ·
  Company A–Z. Pure client-side; persists in URL state (A1).
- **View toggle: Stream | Ledger.** Ledger is a compact table (Issued · Company · Docket ·
  Type · Findings · Recs · $ · top themes) — one row per report, `<details>`-free, click opens the
  stream card via A1 deep-link. This is the analyst scan mode and the single biggest P-A ergonomic
  win after permalinks. Ledger reuses the same baked data; ~150 lines of JS + a table stylesheet.
- Density stays per-device sane: Ledger is desktop/tablet-first; on mobile it renders as the
  existing stream (no duplicated DOM trees — same data, one renderer per viewport class).

### A4. Company lens (fixes F12; consumes `cross_links.json` or retires it)
- **Company facet** (top ~20 by report count + search-within-facet) per tab.
- On an open card: a mechanical **"More on {company}"** row — counts of other records for the same
  normalized company across collections ("3 FERC audits · 2 state rate cases"), each a deep link
  (A1). Company normalization already exists in the pipeline (`company_tokens`).
- If `cross_links.json` isn't consumed by this (or slimmed to what this needs), stop baking it (F6).

### A5. Theme drill-down
- Clicking a pattern card today just filters the stream. Add a **theme header panel** when a theme
  filter is active: the theme's description (exists in patterns.json), report/finding counts,
  a per-year sparkline (from `by_year` × theme — needs a small `themes_by_year` addition to
  `pipeline/patterns.py`), and top 5 companies. All mechanical counts; renders above the stream.
- This turns "Top patterns" from a filter shortcut into the analyst's systemic-vs-one-off answer
  (P-A job 5).

### A6. The dollar lens (fixes F11; gated on `amounts_enrich` scale-out, BACKLOG P1 #4)
- Once `amount_usd` covers most FERC findings: a **"$ quantified" KPI** in the strip (e.g.
  "$XXXM in cited dollar figures across N findings"), a "Has cited $" filter chip, the A3 sort, and
  per-theme/per-year $ columns in the trends band.
- Every aggregate keeps the discipline: only sums of **cited** verbatim figures, labeled "as stated
  in reports, not adjusted/deduplicated" — never an estimate. Tooltip methodology link.

### A7. Data & downloads page (analyst trust surface; see also Part D)
- A dedicated `data.html`: what's in the dataset (per-collection counts + as-of dates), download
  links — `findings.csv` (already baked but unlinked from the UI), `reports.json`, llms.txt trio —
  a **data dictionary** (column → meaning → provenance field), the **suggested citation** block,
  known limitations (verbatim-only, parse coverage per collection, nondeterministic-extraction
  caveat), and a lightweight **changelog** (dataset version = build date + corpus counts; the last
  ~10 builds, hand-maintained or emitted by `pipeline/build.py`).
- Add `findings.csv` + `data.html` to the footer's machine-readable line. Include `amount_usd`
  columns in `findings.csv` when A6 lands (today the CSV has none).
- **Filtered CSV export** (backlog [med]) lives here architecturally but ships in the toolbar: an
  "Export view as CSV" button serializing the current filter result client-side.

### A8. Orientation for the general reader (fixes F13)
- One-line **glossary tooltips** (`<abbr>`/title + a tap-friendly popover) on FA/PA, docket,
  prudence, rate case, AFUDC, below-the-line — a ~15-term dictionary baked as a tiny JSON, reused
  by About.
- Tab micro-copy: keep labels short ("State Audits", "Rate Cases", "Reference") with the full
  explanation in the per-tab lead (already exists).
- A compact **"Start here"** strip for first-time visitors (3 suggested entry points: "Biggest
  pattern", "Latest audit", "Costs charged to customers") — replaces nothing, sits inside the
  existing how-to `<details>`.

### A9. Coverage & freshness transparency
- A small **coverage table** on About (or data.html): per collection — jurisdictions covered,
  parsed-vs-reference counts, latest document date, last-checked date. Most of this exists in
  `meta.json`/`patterns_by_collection.json`; add `latest_issued` + `last_verified` per collection to
  the bake. Analysts must know "is silence absence-of-data or absence-of-issues" — say explicitly
  that FERC has issued no audits since FA24-3 (2026-05) and states are sampled, not exhaustive.
- Surface `captured_at`/"as of" on each card's KV grid (exists in data; only source_note shows now).

### A10. RSS/Atom feed of new reports
- `feed.xml` emitted by `pipeline/build.py` from `reports.json` (newest 50; title = company +
  docket + finding count; link = A1 permalink). Zero-backend "what's new" for P-A job 4; pairs with
  the llms.txt convention for agents.

### A11. Search UX (fixes F10)
- Highlight match context: when search is active, each card shows a one-line `…matched text…`
  excerpt (from the same fields `matches()` scans) with `<mark>`.
- Scope toggle: All fields | Findings only | Company/docket only.
- Debounce 150 ms (currently renders per keystroke over 440 cards — compounds F4).

---

## Part B — Interaction model, performance, responsive

### B1. Incremental stream render (fixes F4)
- Render 20 cards, append 20 more via IntersectionObserver sentinel **with the scroll-position
  guard** (DESIGN.md §12.3). Result count stays exact (filtering is cheap; only DOM append is
  chunked). Ledger view (A3) renders rows, which are ~10× cheaper — same chunking.
- Acceptance: no blank frames scrolling the FERC tab on a mid-range device; Lighthouse TBT < 200 ms.

### B2. Split index vs. detail payload (fixes F5, F6)
- Bake `reports_index.json` (card/ledger fields only: id, collection, company, docket, dates,
  counts, themes, pills, amount rollup — ~150–250 KB raw) and per-collection detail files
  (`findings_<collection>.json`) fetched lazily on first card-expand (or idle-prefetched after
  first paint, `priority: "low"` per DESIGN.md §10).
- Preload switches to the index. Search over finding bodies falls back to the lazy file — with A11's
  scope toggle, "company/docket" search needs no detail fetch at all.
- Delete `reports_pre_cost_extraction.json` from docs/data (keep under `data/` history if wanted);
  decide `cross_links.json` per A4. Keep `reports.json` as the stable full-corpus download for
  machines (A7) — it just stops being the runtime payload.
- Guard: a build test asserting index+details reconstruct exactly to `reports.json` (single source
  of truth discipline).

### B3. Mobile/tablet ergonomics (fixes F9)
- **Sticky bottom bar on mobile** (safe-area padded): Filters · result count · sort · back-to-top.
  Replaces the scroll-away toolbar button; ≥44px targets. Bottom sheet unchanged.
- **Tablet (640–1023) filters become a left slide-in panel** rather than a phone bottom sheet
  (bottom sheets feel phone-y at 768px and hide the stream being filtered).
- Sub-meta line: use short dates ("Sep 8, 2025") below 560px and keep "Issued <date>" atomic
  (`white-space:nowrap` per segment, wrap between segments).
- Card tap target: whole summary already toggles; keep, but move the chevron into the source line
  (top-right) at all widths — at 375px it currently floats oddly mid-card.

### B4. Keyboard & a11y pass (folds in backlog [low] Lighthouse item)
- `j/k` (or ↑/↓ when stream focused) moves card focus, `Enter`/`Space` toggles, `c` copies citation
  — documented in the how-to. Cheap and analyst-flavored.
- Focus management: expanding a card moves focus into the thread; Escape collapses back to summary.
- Audit pill text sizes (10.5px is below comfortable minimum — move to 11.5–12px), verify 4.5:1 on
  all pill/tag/muted combos in BOTH themes (F15 changes shift several), add `aria-expanded` mirror
  on the summary for SRs that don't map `<details>` well.
- Add loading skeletons (3 shimmer cards) instead of the bare "Loading…" count, and an error retry
  state (currently a dead "Failed to load data.").

---

## Part C — Visual identity: "public record, periwinkle" (fixes F14, F15)

**Design intent in one line:** keep the stream+thread model and the periwinkle anchor, but shift the
treatment from *pastel social feed* to **regulatory ledger** — the FT/ProPublica end of DESIGN.md's
own influence list. Distinctive = restraint + typographic confidence + honest data furniture, not a
louder palette.

### C1. Color system (color-theory derivation from the periwinkle anchor)

Anchor: **periwinkle `#5B5BD6`** (≈ hue 240°). The system is built on deliberate hue relationships:

| Role | Hue logic | Light | Dark | Notes |
|---|---|---|---|---|
| Brand accent | anchor, 240° | `#5B5BD6` | `#9393F2` | unchanged; CTAs, links, focus |
| Ink (text) | anchor-tinted near-black | `#191930` | `#ECECF6` | slightly deeper than today for ledger contrast |
| Paper (bg) | 3–4% anchor wash | `#F5F5FB` | `#12121E` | keep cool; **never** warm cream (that's Claude's territory) |
| Hairline/rule | anchor at low chroma | `#D9D9EC` | `#31314A` | replaces most box borders (see C3) |
| **Finding / noncompliance** | **near-complement ≈ 38°** (amber-ochre) | `#A8690A` (AA on paper) | `#E3A84E` | max hue distance from brand → "flagged" reads instantly |
| **Recommendation** | **split-complement family → teal ≈ 185°** | `#0E7A83` | `#5BC4CE` | moves off the current 212° steel blue that collides with brand (F15) |
| Resolved / implemented | triadic green ≈ 150° | `#20794D` | `#6FC795` | unchanged role |
| Cost-to-customers | finding amber, filled treatment | same as finding | same | one axis, one hue — badge = filled, theme tag = outline |
| Dollar figures | ink + tabular nums, **no hue** | ink | ink | money is data, not status; hue stays reserved for meaning |
| Categorical (charts: electric/gas/oil, collections) | even-spaced desaturated wheel around anchor: 240° / 185° / 38° / 300° / 150° | periwinkle · teal · ochre · violet · green (all ~45% sat) | lightened equivalents | category ≠ status per DESIGN.md §3.1; sits visually *between* brand and semantic saturation |

- All tokens stay CSS custom properties; add the categorical family (`--cat-1…5`) and a
  `--rule` token. Every pair ships with a contrast check (extend the manual check into a tiny
  script/test over the token file — DESIGN.md §9 makes it non-negotiable, F15 changes touch many).
- Periwinkle usage gets **stricter**: chrome, interaction, and selection only. Findings/recs/status
  never borrow it (today `.pill.kind` and the amount pill both borrow accent — reassign to ink).

### C2. Typography (system-stack, treatment-led)
- Keep DESIGN.md §2 stacks (no render-blocking font by default). Distinctiveness comes from
  **scale + case + numerals**, not a font download:
  - Display/serif (`Charter/Source Serif`) for: brand, section titles, KPI numerals, **finding
    titles** (currently sans — moving them to serif makes the *content* editorial while chrome stays
    sans, per §2's own rule).
  - **Mono for every docket, accession, form number, and $ figure** (`--font-mono`). Dockets are
    identifiers analysts copy — mono + `user-select: all` is both a trust cue and the single
    cheapest "this is a records tool, not a chatbot" signal.
  - Uppercase letterspaced eyebrows (11px/0.08em) for KPI labels, facet legends, collection names —
    already half-present; make it systematic.
  - Type scale: 12 · 13.5 · 15 (body) · 17 · 21 · 26 · 34, `clamp()` on the two display sizes.
- **Decision gate (explicitly deferred):** one self-hosted variable serif (e.g. Source Serif 4
  subset, ~35 KB woff2, `font-display: swap`) *only if* the C3 restyle still feels generic in
  review. Ships behind a measured before/after (DESIGN.md §2 audit rule).

### C3. Surface language: from cards to ledger
- **Hairlines over boxes:** stream cards keep a container but drop to 1px `--rule` borders, radius
  12→8, shadow only on hover/open. Between findings inside a thread, use full-width hairlines +
  the existing left connector (which stays periwinkle — it's chrome).
- **Stamp pills:** status pills become uppercase, letterspaced, 1px-bordered "stamps"
  (`FINDINGS · 11`, `LISTED FOR REFERENCE`) — outline by default, filled only for the two semantic
  states (finding amber, resolved green). Kills the pastel-pill field that reads "AI dashboard".
- **Square monogram** replaces the circle avatar (circle avatar = social feed; square plate + serif
  initial = record). Or drop the monogram entirely in Ledger view.
- Charts (trends band) adopt the categorical palette + hairline gridlines; bars get value labels at
  ends (already present) in mono.
- Motion budget unchanged (§5); the identity is static confidence, not animation.

### C4. Fit with the existing theme-variant backlog
This spec **is** the "Editorial + periwinkle" variant the backlog A/B wanted, applied as the default
rather than a toggle — the Plus-stream information architecture survives; only the skin and the two
new views (Ledger, theme panel) are added. The `data-theme-variant` hook stays for a future
Wave-threaded experiment; the runtime theme-switcher item stays [low].

---

## Part D — LBL EMP (emp.lbl.gov) conventions worth adopting

*(Researched live 2026-07-16 — emp.lbl.gov 403s scripts, so pages were browser-captured. LBNL
"Energy Markets & Planning" publishes the canonical annual data-product suite for the US power
sector: Utility-Scale Solar, Land-Based Wind Data Update, Tracking the Sun, **Queued Up**
(interconnection queues — the closest structural analogue to this corpus), Hybrid Plants, Retail
Price Trends, ReWEP, plus a Tools & Data hub including two FERC-Form-1-based tools (VUE utility
expenditures, IOU Distribution Cost Explorer). Product URLs in the research log.)*

Their conventions, mapped to this project:

1. **Annual, versioned "editions" with explicit data vintage.** Titles carry both edition year and
   coverage year ("Queued Up: 2025 Edition … As of the End of 2024") and a "What's new this
   edition" section (method changes, new sources) → **D1: an annual "FERC & State Utility Audit
   Findings — {YEAR} Edition" briefing page**: one static page per year, mechanically composed
   (counts + YoY deltas, new reports, theme movers, top cited $ figures, coverage changes), titled
   with the edition/vintage split (fits the existing `captured_at` discipline). Gives P-B the
   deck-ready headline surface and P-A the "what changed" digest. No LLM narrative — numbers +
   verbatim excerpts with citations.
2. **Key-highlights bullets lead every product** (5–8 quantified takeaways with YoY deltas, e.g.
   "gas +86%, solar −19%") → the D1 page and the About page open with a mechanical highlights
   block.
3. **The three-artifact release: browsable tool + downloadable data file + summary briefing.**
   LBNL never ships a dashboard without the underlying file and a slide-style summary; the Queued
   Up Excel bundles the full project dataset **with a codebook tab and ~35 summary-pivot tabs** →
   A7's data page + a findings bundle whose data dictionary travels *inside* the download (a
   `README`/dictionary sheet or sidecar), plus D1 as the briefing analogue.
4. **Coverage-denominator statements.** Every LBL dataset states what fraction of the universe it
   covers ("~98% of installed U.S. capacity") → A9 says explicitly: "all 123 FERC audit reports
   published 2014→present; N state audits across K states; X% of records carry parsed findings."
5. **Cohort/outcome funnels.** Queued Up's signature stat follows request cohorts to terminal
   states (13% built / 77% withdrawn) and median duration → the audit analogue is
   **recommendation-outcome tracking** (already backlog [low]): findings per issuance-year cohort
   that were resolved / repeat-cited / unknown, median time to closure where follow-up documents
   exist. Promoted conceptually to the D1 page once the data exists.
6. **Distributions, not just totals** (project-level scatter + capacity-weighted average + 20th/80th
   percentile bands is the house chart style) → cheap adoption now: findings-per-audit distribution
   chip in trends ("median 5 findings/audit, max 14"), computed at bake time; when A6 lands, a $
   scatter-with-median-band per year is the house-style chart to copy.
7. **State choropleth with drill-down** (their capacity/interconnection maps run
   national→state→county) → a small SVG state map on the coverage surface (A9) showing audits +
   findings per jurisdiction; doubles as the honest "sampled, not exhaustive" disclosure.
8. **Canonical stable URLs per product** ("the most recent edition is always at
   emp.lbl.gov/queues"; prior editions archived on a Publications tab, each cite-formatted) → keep
   the site root as "latest," archive D1 editions at stable paths, list them with suggested
   citations (pairs with A1 permalinks).
9. **The dataset is itself a citable publication** (LBNL biblio has "Database" as a publication
   type; tools carry version numbers like "ReWEP 2024.1") → version the baked dataset (build date +
   corpus counts as the version string) and give it its own suggested-citation block (A7).
10. **Suggested-citation + named-contact block on every page; release notifications** (topic-
    segmented mailing list + webinar + news post per edition) → zero-backend analogues: citation
    blocks (A7), a contact line, and the Atom feed (A10) — feed entries per collection mirror their
    topic segmentation.

---

## Phasing, effort, acceptance

**Phase 1 — Analyst quick wins + perf floor (1–2 sessions).**
A2 (card scent, 0-recs fix) · A3 sort · B1 incremental render · B2 payload split + stale-file
removal · B3 mobile bar + wrap fixes · A11 debounce.
*Acceptance:* card shows subject + themes + honest pills; FERC tab scrolls jank-free; first-paint
data ≤ ~300 KB raw; sticky mobile controls; all existing tests green + new build-parity test (B2).

**Phase 2 — Identity refresh (1 session, pure CSS/markup + token test).**
C1 palette + contrast script · C2 type treatment · C3 surface language · B4 pill-size/contrast fixes.
*Acceptance:* zero hardcoded hex outside `:root`; contrast test green both themes; before/after
screenshots at 375/768/1280 reviewed by the user (the "doesn't feel like Claude" check is theirs).

**Phase 3 — Share & lenses (1–2 sessions).**
A1 URL state/permalinks · A3 Ledger view · A4 company lens (+ cross_links decision) · A5 theme
panel (+ `themes_by_year` bake) · A7 data page + filtered CSV export · A10 feed.
*Acceptance:* deep link restores exact view; ledger sorts; theme panel sparkline matches
patterns.json; feed validates; data dictionary covers every findings.csv column.

**Phase 4 — Storytelling (gated).**
A6 dollar lens (gated on amounts scale-out, BACKLOG P1 #4) · D1 annual briefing page · A8 glossary
+ start-here · A9 coverage table.
*Acceptance:* every $ aggregate traces to cited `amount_usd_quote`s; briefing page is 100%
mechanically generated; glossary popovers keyboard-accessible.

**Non-goals (explicit):** no backend/search service; no LLM-generated summaries or scores; no
framework or build step; no new font without the C2 gate + measurement; no change to the verbatim
discipline; no third theme variant beyond the C4 hooks.

**Test plan themes:** build-parity test for the payload split (B2); token contrast script (C1);
URL-state round-trip unit test (A1, pure function); existing `test_no_garbled_findings` etc. remain
the data floor; perf re-check via the `perf-audit` skill after Phases 1 & 3.
