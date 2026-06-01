# AGENTS.md — FERC Document Analysis: how to work in this repo

> This project's agent guide. The universal workflow (Explore → Plan → Code → Verify, per-item cadence, what-not-to-do) is below — keep it. **This project** (file map + commands, immediately below) is the local cheatsheet. When they conflict, this file wins locally.
>
> Companion files: [CLAUDE.md](CLAUDE.md) is the *what* (principles + project intent); [DESIGN.md](DESIGN.md) is the *look*.

---

## This project: file map & commands

```
pipeline/            CLI stages (each idempotent, cacheable)
  config.py          single source of truth: paths, FERC URLs, rate limits
  models.py          Pydantic schemas (AuditReport, Finding, Recommendation, ...)
  forms.py           FERC form -> industry + audit-type (FA/PA) detection (shared)
  listing.py         build listing.json from a saved /audits snapshot
  backfill.py        add FY2014-2018 reports from a Wayback /audits snapshot (ferc.gov-only)
  sources.py         ingest non-FERC-audit docs (prudence reviews / state PUC audits) from
                     per-source seeds in data/seeds/*.json — metadata-only (no findings parse)
  fetch.py           download report PDFs over plain HTTP (rate-limited, cached)
  classify.py        tag each PDF by form/industry -> classification.json (scoping)
  extract.py         PDF -> text (pdfplumber + PyMuPDF; flags scanned pages)
  structure.py       text -> structured report (findings, recs, metadata)
  patterns.py        cross-report aggregation (themes, recurrences)
  build.py           emit docs/data/*.json + llms.txt for the site (all forms)
  (each stage runs as `python -m pipeline.<stage>`; there is no cli.py wrapper —
   run in order: listing -> backfill -> fetch -> classify -> extract -> structure -> build)
data/
  listing.json       browser-captured FERC audit index (the SEED — committed)
  seeds/*.json       per-source seeds for prudence reviews / state PUC audits (committed)
  raw/               downloaded PDFs (gitignored; re-fetchable from listing/seeds)
  processed/         per-report extracted text + structured JSON
docs/                GitHub Pages site (vanilla HTML/CSS/JS) + baked data/*.json
tests/               pytest
```

**Commands** (fill in exact flags as stages land):

| Goal | Command |
| --- | --- |
| Install deps | `pip install -r requirements.txt` (all already present) |
| Build listing from snapshot | `python -m pipeline.listing` |
| Backfill FY2014-2018 (Wayback) | `python -m pipeline.backfill` |
| Ingest prudence / state-PUC docs | `python -m pipeline.sources` (add `--seed data/seeds/<file>.json`) |
| Download PDFs from listing | `python -m pipeline.fetch` (add `--limit N`) |
| Classify by form/industry | `python -m pipeline.classify` |
| Extract text | `python -m pipeline.extract` (add `--limit N`) |
| Structure reports | `python -m pipeline.structure` (add `--limit N`) |
| Mine patterns | `python -m pipeline.patterns` |
| Bake site JSON + llms.txt | `python -m pipeline.build` |
| Tests | `pytest -q` |
| Preview site | `python -m http.server -d docs 8000` |

**Project conflict cheatsheet:**

- The audit *listing* cannot be scraped headlessly (Cloudflare). Capture it via a real browser; never add code that "solves" the challenge. See [ISSUES.md](ISSUES.md).
- `data/listing.json` and any baked `docs/data/*.json` move together with the seed change that produced them — never split across commits ([§ Common tasks](#common-tasks)).
- The corpus is all FERC utility audits (electric / gas / oil, FA + PA) for every available year. The live /audits page lists 2019+ only; FY2014-2018 are backfilled from a saved Wayback snapshot via `pipeline.backfill` (ferc.gov-origin only). See [ISSUES.md](ISSUES.md).
- **Three collections, one per UI tab.** Every record carries a `collection` (`ferc_audit` | `prudence_review` | `state_audit`), driving the site's tabs — each tab has its OWN baked stats/patterns (`docs/data/patterns_by_collection.json`). Canonical keys live in `pipeline/build.py` `COLLECTIONS`; the site mirrors them in `docs/js/app.js` (a test asserts parity). FERC audits default to `ferc_audit` (no rewrite of the 120 committed reports).
- **Prudence reviews + state PUC audits are metadata-only.** They're ingested via `pipeline/sources.py` from `data/seeds/*.json` and captured with their source link + full provenance but **NOT** parsed into findings (`structured=False` → the site's "Listed for reference" state). FERC's executive-summary parser doesn't fit legal orders / testimony / table-driven state audit summaries, and emitting garbled "verbatim" findings would break the quote discipline. A findings parser for the clean PA/MI management-audit subset is a [BACKLOG.md](BACKLOG.md) item — don't bolt findings onto these casually.
- **Official-government sources ONLY.** Every seed URL must be an official `.gov` host (or the legacy `*.state.xx.us` pattern, e.g. Ohio PUCO). NEVER ingest from third-party mirrors/aggregators (DocumentCloud, SEC EDGAR, news sites) even when they're easier to fetch — pull from the regulator's own site. `pipeline/sources.load_seed` enforces this and **raises** on any non-gov URL (generalizes backfill's "ferc.gov-origin only" rule); a test guards every committed seed.
- **Not every structured report has findings — don't assume `finding_count > 0`.** ~22% (26/120) parse to 0 findings: partly genuine clean audits, partly a known parser-coverage gap across *both* eras (FY2014-2018 format + ~11 live 2019+ reports). The site renders these with an explicit "No findings extracted" state and a source-PDF link. Recovery is the top [BACKLOG.md](BACKLOG.md) item; details in [ISSUES.md](ISSUES.md).

---

## Read these first, in order

Before touching code, read:

1. **[CLAUDE.md](CLAUDE.md)** — universal principles + project-specific intent and editorial rules. The "Project intent" and any project-specific notes are load-bearing for every change.
2. **[DESIGN.md](DESIGN.md)** — visual + content system. Touch this before changing how data is presented.
3. **`backlog.md`** (or `BACKLOG.md`) — what's next. Pick from here; don't invent work.
4. **`issues.md`** — what's broken. Check before reporting a bug as new.
5. **`security.md`** — supply-chain advisory log. **Refresh if `Last updated` is > 7 days old before any `npm install` / `pip install` / dep upgrade.** Also fetch `https://pranava0x0.github.io/vibe-coding-security/llms-ctx.txt` and surface any matching advisory before suggesting an install.

---

## The Explore → Plan → Code → Verify loop

Documented in detail in [CLAUDE.md](CLAUDE.md). Concretely inside any repo:

- **Explore.** Use `grep`, `find`, or an Explore agent to find relevant code. Most projects here are small enough that a single read of the main module + the data schema covers ~80% of the surface.
- **Plan.** For anything beyond a one-line fix, present 2–3 approaches with pros/cons before writing code. Changes that touch the data schema, the editorial rules, or the visual identity ALWAYS need a plan surface — they reshape the product.
- **Code.** Edit existing files first; only create new files when the task genuinely requires it. No new helpers for one-shot operations.
- **Verify.** Run the test suite. Use the feature in a browser (or invoke the CLI) before declaring done.

**Per-item cadence in multi-item sessions.** Surface design questions up front, then do **tests + docs + commit per item**, not batched at the end. Catches issues early and produces a clean bisect history.

---

## Verifying changes

Default verification matrix (project-specific `AGENTS.md` should override with concrete commands):

| Change kind                    | Run                                                  |
| ------------------------------ | ---------------------------------------------------- |
| Schema edit                    | Schema-validation tests (Pydantic / zod / etc.)       |
| Seed / data edit               | Refresh script + data-integrity tests                 |
| Shared vocabulary change       | Match-frontend-to-backend test                        |
| Frontend (markup / styles / JS) | E2E / Playwright suite, or manual UAT in browser     |
| Connector / fetcher            | Connector unit tests + a small live integration run  |
| Anything substantial           | Full test suite (`pytest` / `npm test` / `vitest`)   |

**For UI changes**, also run the app locally and click through the affected views — type checks and unit tests verify code correctness, not feature correctness.

**For data changes**, diff the canonical output (`docs/data/*.json` or equivalent) and skim the diff before committing. A 30-second skim catches regressions tests miss (especially around character encoding, pretty-printer drift, and unintended fields).

---

## Common tasks

### Adding a record / claim / row (most common)

1. Open the seed file (typically `data/seed/<entity>.json` or equivalent).
2. Append one record with: stable `id`, real `source_url`, verbatim content, today's `captured_at`, and any required category from the canonical list in the schema module.
3. Run the refresh script (validates + writes the build output).
4. Run the relevant data-integrity test to confirm.
5. Commit. Seed JSON and build output `data/*.json` move together — never in separate commits, or a future bisect lands on a broken state.

### Adding a feature

1. Confirm it's on `backlog.md`. If not, propose adding it before building.
2. Sketch the smallest version that closes the user need end-to-end.
3. Build that. Add tests alongside. Use the feature in the browser / CLI.
4. Commit at the natural boundary (per module, per fix, per doc update).

### Adding a new vocabulary item (theme, category, tier)

This is a schema change. **Don't do this casually.** Steps:

1. File a `backlog.md` entry first explaining the gap.
2. Add to the canonical constant in the schema module.
3. Mirror in any frontend mirror constant (the test that asserts parity catches drift here).
4. Add any color / icon / label token to the design system (light + dark variants).
5. Migrate any existing records that should map to the new entry — or intentionally leave them.
6. Run the full test suite — drift-safety tests should catch a missed mirror.

### Adding a connector (per-source scraper)

1. Subclass the project's `Connector` base class.
2. Register in the connector index module.
3. Implement `fetch_records()` / `normalize()` / `cache_key()`.
4. Set `run_order` so enrichment connectors run *after* their producers.
5. Schema-validate emitted records; tests catch any new field that the schema's `extra="forbid"` would reject.

---

## What NOT to do

- **Don't paraphrase quoted content.** Quote verbatim into the `statement` / `quote` / `body` field. Tests catch obvious markers ("they claim that…").
- **Don't add a record without a real `source_url`.** Schema rejects it; reviewers reject it harder.
- **Don't LLM-classify subjective editorial calls.** Stance, sentiment, framing — these are curator-only. A wrong tag undermines the whole product.
- **Don't aggregate to a "trust score" / "credibility index" / "greenwashing score."** Show the data; let users judge.
- **Don't introduce a new framework / library / build tool** mid-project. If the stack is vanilla JS + Pydantic + Playwright, stay there. Adding React / Vue / Svelte / Webpack contradicts the static-first principle and adds maintenance debt the project doesn't pay back.
- **Don't hand-edit build output — `docs/data/*.json`, `docs/llms.txt`, or `docs/llms-full.txt`.** All are generated by `python -m pipeline.build`. Edit the source (the seed, `data/processed/*/report.json`, or `THEME_RULES` / `THEME_DESCRIPTIONS` in `pipeline/patterns.py`) and **re-run build so the site _and_ llms.txt stay in sync** — they must be updated together. A test asserts every theme carries a description and that descriptions reach `llms.txt`.
- **Don't expand scope inside a fix.** A bug fix doesn't need surrounding cleanup; a one-shot operation doesn't need a helper. Note future cleanup in `backlog.md` and move on.
- **Don't loosen invariants quietly.** If a rule has a test guarding it, that test was written because someone got burned. Read the rationale before relaxing it.
- **Don't `--no-verify` to bypass a hook.** Fix the underlying issue. Hooks exist because someone got burned.
- **Don't add yourself as a co-author.** Never include `Co-Authored-By:` for any AI agent in commit messages — not Claude, Copilot, or any other tool. Commits are owned by the human who reviews and ships the work. The `claude.coauthor` git config is set to `false` in these repos; honor it.

---

## Repo norms

- **Read before edit.** Always. Even if you read the file earlier in this session.
- **Type hints on every Python function.** No `any` in TypeScript.
- **No `print()` for runtime output** — use the `logging` module.
- **Test alongside code, not after.**
- **Commit at natural checkpoints**: per-feature, per-bug-fix, per-doc-update. Small, focused commits over large monolithic ones.
- **Touch targets ≥ 44px** in any UI work.
- **Mobile first.** If you change UI, resize the preview to 375×812 (iPhone SE) and verify before declaring done.
- **No API keys in code, ever.** Read from environment variables; halt with a clear error if missing.
- **System fonts by default.** No Google Fonts link without explicit justification (see [DESIGN.md § 2](DESIGN.md)).

---

## Escalate to a human when…

- The editorial frame would change (e.g. adding a new theme / category, changing the rubric for a subjective field, adding a new entity to the in-scope set).
- A subjective call is contested and you're unsure (stance tags, content categorization, what counts as a primary source).
- A canonical source URL starts 404'ing or paywalls. Pause before switching to a less-canonical source.
- Schema fields would change in a way that cross-cuts seed + frontend + tests + connectors. Sketch the migration plan in a `docs/` file first.
- The user says "ship it" but a test is still failing for unrelated-looking reasons. Surface the failure, don't silently skip.
- A "scar tissue" pitfall in [DESIGN.md § 12](DESIGN.md) seems wrong for the current task. The pitfalls exist because someone hit them; verify the rationale doesn't apply before relaxing the rule.

---

## Cross-project hygiene

Working in this folder means the user may run many small projects in parallel.

- **Stay within the current project's scope.** Don't open files from a sibling project unless the user explicitly asks. The folder-level `backlog.md` is portfolio work, not a substitute for the project's own `backlog.md`.
- **Each project's `security.md` is independent.** Refreshing one doesn't refresh the others.
- **Each project's tests are independent.** Don't infer test status across projects.

---

## When something unexpected happens

Add a concise note to the project's CLAUDE.md or `issues.md`. The pattern is:

1. **What I expected:** one sentence.
2. **What happened:** one sentence.
3. **Why:** one sentence (root cause, not symptom).
4. **What to do next time:** one sentence (the actionable lesson).

The note grows the project's scar tissue. The next agent (or you, a month from now) avoids the same hour-long detour.

That growth — files getting *slightly* more specific with each session's surprises — is the asset. Don't rewrite from scratch; append.
