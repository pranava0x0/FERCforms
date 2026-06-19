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
- **Prudence reviews + state PUC audits are metadata-only by default.** They're ingested via `pipeline/sources.py` from `data/seeds/*.json` and captured with their source link + full provenance but **NOT** parsed into findings (`structured=False` → the site's "Listed for reference" state). FERC's executive-summary parser doesn't fit legal orders / testimony, and emitting garbled "verbatim" findings would break the quote discipline. **Exception (live):** PA PUC **Management & Operations** audits are parsed verbatim from their Exhibit I-2 "Summary of Recommendations" (`pipeline/state_structure.py`, `parse:true`, snapshot-gated). Only flip `parse:true` for a format with a clean enumerable structure + a no-regression test; everything else stays metadata-only. Remaining formats (PA focused/MEI, MI Liberty) are a [BACKLOG.md](BACKLOG.md) item — don't bolt findings onto these casually.
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

### Adding a source (per-regulator scraper)

The full per-regulator access recipes and the step-by-step workflow live in
**[docs/data-sources.md](docs/data-sources.md)** and the **refresh-ferc-data** skill
(`.claude/skills/refresh-ferc-data/`). In short:

1. Find the doc + its stable **`.gov`** URL (per-source recipe in the guide).
2. **Verify before seeding:** fetch + read page 1–2 (skip "Filing Receipt" covers) to label
   `company`/`issued_date`/`doc_type` accurately; drop off-theme docs.
3. Write `data/seeds/<source>.json` (`SourceSeed` per doc, `collection:"state_audit"`, full
   `source_note`, `parse:false`, `fetch:false` only for WAF-blocked browser-captured URLs).
4. `python -m pipeline.sources --seed data/seeds/<source>.json && python -m pipeline.build`,
   then `pytest` + preview the tab. Commit seed + processed + baked `docs/data` together.

`SourceSeed`'s `extra="forbid"` + `load_seed`'s `.gov` guard catch bad fields/hosts; a test
validates every committed seed.

### Dispatching a research-finder agent (web discovery of new docs)

Finding NEW real `.gov` documents to seed is the one task where a `general-purpose` agent *earns
its cost* — it's open-ended discovery that **requires fetching + page-1 verification per candidate**
(unlike a bounded "find docket X" lookup, which stays inline per § "What NOT to do"). The agents in
the 2026-06-19 session performed well on rigor (every candidate fetched + caption-verified, zero
fabrication, walled/exhausted targets reported honestly). Rules learned that session:

1. **Pre-flight the hypothesis against our OWN data before spawning.** Before sending an agent to
   "find more docs matching format/format X," confirm X is real with a near-free local check (grep
   the parser's anchor string across `data/seeds` / `data/processed`; re-read the parser). The
   2026-06-19 Overland-finder agent (~85k tokens) was launched on the premise that Overland audits
   share the "Comprehensive Listing of All Recommendations" our parser keys on — it returned `[]`
   *and* claimed our own seeded PSE&G doc lacks that listing, contradicting the parser that extracts
   17 findings from it via that exact anchor. A 1-minute local grep would have shown the premise was
   shaky and saved the run.
2. **Batch by breadth, don't multiply by unit.** One agent covering 8–10 states beats eight
   single-state agents (each re-loads the system prompt + tools). Sequence agents only when the prior
   result genuinely informs the next direction — don't fan out five in parallel "to be thorough."
3. **Record exhausted / walled seams durably** in BACKLOG.md and [docs/data-sources.md](docs/data-sources.md)
   so no future session re-spends an agent confirming the same dead end (e.g. "PA M&O Exhibit-I-2
   corpus exhausted"; "NC NCUC `starw1.ncuc.gov` 403s scripts → browser-capture only"; "GA PSC fuel
   orders are image-only scans → need OCR"). A confirmed-negative is a real deliverable — capture it.
4. **The non-negotiable verification template** (every finder-agent prompt must include): give the
   already-seeded list to dedupe against; define "on-theme" narrowly; require the agent to **fetch
   each PDF (HTTP 200) and read pages 1–3** to confirm caption/utility/docket/date; **never guess or
   construct a URL** (a search/`?`-query or directory index does NOT qualify — only the document PDF);
   **`.gov`/official host only**; return a strict JSON array; **honesty over quantity, `[]` is a
   valid answer**; and report which targets were walled/unfetchable. This template caught GA
   image-scans, off-theme docs, and mislabeled filings — keep it verbatim.

After the agent returns: **dedupe every candidate** (`grep` its docket + pcdocs/guid id across
`data/seeds`) and **re-verify the URL fetches from the pipeline UA** (`curl` → `%PDF` + page count)
before seeding — agents occasionally surface a doc already seeded under a different id, or a URL that
200s for a browser but not the pipeline.

### Extracting text from seed documents (rate cases, state audits, etc.)

The extraction pipeline works across both FERC audits (from listing.json) and seed documents (from reports.json):

1. **Seed documents are loaded alongside FERC audits.** `pipeline/extract.py` calls both `load_from_reports()` (which reads reports.json — containing all documents including seeds) and loads FERC documents from listing.json.

2. **PDF lookup tries multiple filenames.** `extract_report()` tries `{id}.pdf` first (seed documents use this naming) and falls back to `{accession_number}.pdf` (FERC audits). This dual lookup ensures both naming conventions work.

3. **Chunked extraction with --limit.** For large batches, use `python -m pipeline.extract --limit N` to extract N documents. The limit is applied *after* filtering to documents that have PDFs but no text.json, so `--limit 20` extracts 20 documents that actually need work, not the first 20 from the full list.

4. **Batch strategy.** Memory constraints on full-corpus extraction require batching. ~20-30 documents per batch works well; chain multiple `--limit` runs and re-run structure + build on the accumulated text.json files.

**Examples:**
```bash
# Extract first 20 documents (from any collection) that need work
python -m pipeline.extract --limit 20

# After extraction batches, structure all documents
python -m pipeline.structure --limit 100

# Regenerate patterns and baked JSON
python -m pipeline.patterns && python -m pipeline.build
```

Key insight: seed documents are identified by their presence in reports.json with `collection:state_rate_case` or `collection:state_audit`, not by any special path convention. The extraction pipeline treats all documents uniformly once loaded.

### Running long pipeline commands (fetch/extract) in the background — DO NOT hand-roll waiters

`pipeline.sources` / `pipeline.extract` runs can take many minutes (large PDFs, F5/Cloudflare backoff). Hard-won rules from the 2026-06-08 session (these failures cost real time):

- **Launch with `run_in_background: true` and wait for the completion notification.** The harness notifies you when the process exits — that IS your signal. Do other independent work meanwhile, or end the turn. **Do not write a `while pgrep …; do sleep N; done` waiter** to block on it.
- **`pgrep -f "pipeline.sources"` matches the waiter shell itself** (the loop's own command line contains that string) → the loop never exits and spins forever; you'll have to `pkill -f "while pgrep"` it. If you *must* poll a process, match the real invocation: `pgrep -f "python.* -m pipeline.sources"`, never the bare module string. To wait on a condition, use the **Monitor** tool, not inline `sleep`.
- **`sleep N; <cmd>` chains are blocked by the harness** — don't chain a sleep before reading output.
- **Never run two instances of the same stage on overlapping seeds concurrently** — they write the same `data/processed/<id>/` and race. Finish one, then start the next.
- **Before declaring done**, run `pgrep -fl "<project-path>"` and `pkill`/`kill` any lingering waiter shells.
- **Don't gate a commit on a piped filter:** `pytest … | grep passed && git commit …` silently skips the commit when `grep` finds nothing on the piped line. Run tests, read the summary, then commit as a separate step.
- **Committing a NEW processed record?** `data/processed/*/report.json` is gitignored by default — a plain `git add data/processed` skips new records (baked-but-uncommitted = phantom). Use `git add -f data/processed/<id>/report.json`; the test `test_every_processed_report_is_git_tracked` enforces committed == baked.


---

## Agent checkpointing & failure logging (multi-step ingest tasks)

When spinning off agents for data ingest, processing loops, or state-backfill work, the agent MUST implement:

**1. Incremental saves.** After processing each logical unit (one seed doc, one state, one utility), immediately:
   - Write the `data/processed/<id>/report.json` record
   - Update the seed file (mark as `fetched=true`, add `captured_at`, update `page_count`)
   - Commit or checkpoint the working directory

   **Why:** If the agent times out, hits a rate limit, or encounters an error midway, all work after the last checkpoint is lost. Incremental saves let the next run resume from the last successful checkpoint without redoing work.

**2. Failure logging.** Write all failures (HTTP errors, auth walls, parsing failures, timeouts) to a **`data/ingest_log.jsonl`** file with one JSON record per line:
   ```json
   {"timestamp": "2026-06-07T20:18:00Z", "doc_id": "swepco-la-u37794", "status": "failed", "error": "HTTP 502", "reason": "LPSC portal temporarily down", "retryable": true, "url": "https://...", "next_steps": "Retry on next refresh when portal is available"}
   ```
   
   **Why:** Failures that aren't logged become "ghost issues" — the same doc fails silently on every refresh, consuming time and giving no hint why. A detailed log identifies which failures are retryable, which need a URL pivot, which need browser capture, and which are terminal (so the human doesn't waste time re-trying them).

**3. Exit status report.** Agent's final message MUST include:
   ```
   ✓ Ingested: 3 docs (IL Ameren ×2, LA SWEPCO ×1)
   ✗ Failed: 1 doc (SWEPCO, HTTP 502 — retryable, LPSC portal recovering)
   → Next: Re-run SWEPCO on next refresh; move to TX/CO on new session
   ```
   
   This tells the human (or the next agent) what succeeded, what failed and why, and the resume point.

**Example workflow:**
```python
for doc_id, seed in seeds.items():
    try:
        pdf = fetch_pdf(seed['url'])
        record = process_pdf(pdf)
        write_json(f"data/processed/{doc_id}/report.json", record)
        seed['fetched'] = True
        seed['page_count'] = len(record['pages'])
        seed['captured_at'] = today_iso()
    except HTTPError as e:
        log_failure(doc_id, error=str(e), retryable=(e.status == 429 or e.status == 502))
        seed['last_error'] = str(e)
        seed['last_error_time'] = today_iso()
    # commit after each doc or every N docs
    if doc_count % 5 == 0:
        write_seed_file(seed_path, seeds)
        git_commit(f"data: ingest {seed['company']} ({doc_id}) — {doc_count}/{len(seeds)}")
```

---

## Tracking state/jurisdiction refresh progress

To avoid re-scanning the same state unnecessarily and to resume quickly after interruptions, maintain a **`data/ingest_manifest.jsonl`** file (one record per state/jurisdiction touched):

```json
{"jurisdiction": "IL", "utility": "Ameren Illinois", "docket": "25-0084", "last_run": "2026-06-07T20:11:00Z", "docs_ingested": 2, "stopping_point": "completed; move to next state", "next_target": "TX Oncor"}
{"jurisdiction": "LA", "utility": "SWEPCO", "docket": "U-37794", "last_run": "2026-06-07T20:18:00Z", "docs_ingested": 1, "stopping_point": "portal 502 error; retry on next refresh", "next_target": "LA Cleco OR move to CO"}
```

**When starting a new session:**
1. Check `data/ingest_manifest.jsonl` for recent runs (last 7 days)
2. Pick a jurisdiction NOT in the manifest (cold start), or one with `stopping_point: "completed"` (move to next tier)
3. Avoid starting TX if LA is still pending (dependencies)
4. Update the manifest after each jurisdiction is done

**Why:** Without this, the human has to re-read BACKLOG.md and state-coverage.md every session, re-figure out which states are thin, and might start duplicate work on a state that just failed.

---

## What NOT to do

- **Don't paraphrase quoted content.** Quote verbatim into the `statement` / `quote` / `body` field. Tests catch obvious markers ("they claim that…").
- **Don't add a record without a real `source_url`.** Schema rejects it; reviewers reject it harder.
- **Don't LLM-classify subjective editorial calls.** Stance, sentiment, framing — these are curator-only. A wrong tag undermines the whole product.
- **Don't aggregate to a "trust score" / "credibility index" / "greenwashing score."** Show the data; let users judge.
- **Don't introduce a new framework / library / build tool** mid-project. If the stack is vanilla JS + Pydantic + Playwright, stay there. Adding React / Vue / Svelte / Webpack contradicts the static-first principle and adds maintenance debt the project doesn't pay back.
- **Don't hand-edit build output — `docs/data/*.json`, `docs/llms.txt`, or `docs/llms-full.txt`.** All are generated by `python -m pipeline.build`. Edit the source (the seed, `data/processed/*/report.json`, or `THEME_RULES` / `THEME_DESCRIPTIONS` in `pipeline/patterns.py`) and **re-run build so the site _and_ llms.txt stay in sync** — they must be updated together. A test asserts every theme carries a description and that descriptions reach `llms.txt`.
- **Don't auto-launch the `deep-research` skill / `Workflow` fan-out for a lookup.** It spawns **~100 subagents** (1 scope + 5 search + ≤15 fetch + ≤75 verify + 1 synth) and costs **multiple millions of tokens** per run — measured 2026-06-02: **104 agents, ~9.6M total tokens** (cache_read 6.2M + cache_creation 2.5M dominate; the verify phase alone fanned to 75 agents and that run's verifiers all failed StructuredOutput, killing every claim → **the report came back empty despite 9.6M tokens spent**). Default to a direct `WebSearch` + a few `WebFetch` calls inline for any bounded factual ask. Only reach for the harness on a genuinely deep, multi-source, fact-checked report, **with explicit user opt-in and a stated cost estimate first**, and turn the knobs down (`MAX_VERIFY_CLAIMS`↓, `VOTES_PER_CLAIM=1` for well-sourced `.gov` facts). See [CLAUDE.md § AI / API cost optimization](CLAUDE.md).
- **Don't spawn a general-purpose agent for a simple bounded lookup.** Audit of 2026-06-07 session found 4 agents spawned to find dockets ("search for <utility> docket at <regulator>") when inline `WebSearch` + maybe one `WebFetch` would have sufficed. Each agent costs ~25–40k tokens; inline WebSearch ~5–10k. **Rule: try WebSearch inline first; only spawn an agent if WebSearch fails or the query is open-ended / requires adversarial verification.** Measured case: "find Ameren Illinois ICC docket" spawned an agent (30k tokens) when `WebSearch "Ameren Illinois" site:icc.illinois.gov 2025 rate` would have landed it in 2 calls. Update the threshold: span agents for *synthesis, adversarial checks, or multi-step workflows*, not routine lookups.
- **Don't spawn an Explore agent for data analysis on files you control.** Session 2026-06-15 review: spawned Explore for "find cost examples in reports.json" (~3-4K tokens, good examples but incomplete). Should have written Python directly (~1-2K tokens, exhaustive + iterable). **Rule for Explore agent:** Use for *codebase architecture questions, finding symbol definitions, understanding unfamiliar patterns*. **Not for:** data extraction from JSON/code you control — write Python inline instead. Threshold: if you could write a quick grep/Python script faster than explaining the task to an agent, do it. Explore is for "where is X / which files reference Y / how does this system work" — not "show me all records matching pattern P."
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
