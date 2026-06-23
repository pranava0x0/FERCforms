# CLAUDE.md — FERC Document Analysis

> This project's engineering source of truth. The numbered/section principles below are the portfolio's universal discipline — keep them. **Project intent** (immediately below) is specific to this repo and is load-bearing for every change. When a rule here conflicts with portfolio defaults, this file wins locally.
>
> Companion files: [AGENTS.md](AGENTS.md) is the *how* for AI agents; [DESIGN.md](DESIGN.md) is the *look*.

---

## Project intent

A static, GitHub Pages-hosted toolkit to **read FERC documents and surface what matters in them.** The first module is the **FERC Audit Explorer** — electric (Form 1), gas (Form 2) and oil (Form 6) audits: download FERC's published audit reports (every available year, issued 2014→present), extract/OCR them, structure each into reports → findings → recommendations, mine the **common patterns** of noncompliance, and present them as a browsable feed.

The north-star feature (later — see [BACKLOG.md](BACKLOG.md)) is an **"audit-my-document" mode**: given a filing, flag the issues a FERC auditor would likely raise, using the pattern library mined here. So v1's real deliverable is a **clean, well-attributed structured dataset of historical findings** — the model quality later depends on it.

Load-bearing facts for any change here:

- **Source & access.** Reports live at <https://www.ferc.gov/audits> (Cloudflare-challenged: 403 to scripts → the listing is **browser-captured**). The live page lists **2019+** only; **FY2014-2018** are recovered from a saved Internet Archive **Wayback** snapshot of /audits, with each older report's eLibrary accession resolved via the eLibrary **Docket Search** API (`pipeline/backfill.py`, **ferc.gov-origin only**). Report PDFs download from eLibrary (F5 WAF — scripted cookie dance in `pipeline/fetch.py`). See [ISSUES.md](ISSUES.md).
- **Scope: all FERC utility audits — electric (Form 1), gas (Form 2), oil (Form 6).** Both **financial (FA)** and **non-financial (PA)** types (FERC's terms), for **every available year** (issued 2014→present). The whole corpus is downloaded, classified (`pipeline/classify.py`), and structured E2E. `audit_type` (FA/PA) comes from the docket prefix; `industry` from form/statute signals. Every record carries a provenance `source_note` (and `archived_via` for Wayback-sourced reports).
- **Data is the product.** Findings are quoted **verbatim** with a source URL + capture date. No paraphrase, no "compliance score," no LLM-judged editorial calls. See [AGENTS.md](AGENTS.md) and [DESIGN.md §15.6](DESIGN.md).
- **Zero-backend, zero-paid-deps.** Vanilla HTML/CSS/JS site reads baked JSON; Python CLI pipeline produces it. No framework.

---

## North star: ship small things that work end-to-end

Everything below is in service of one rule: **build the smallest version that works, then add only what the next user need demands.** Karpathy's "make it work, then make it good"; levels.io's "ship it ugly, ship it now." A working ugly thing teaches you more in a day than a beautiful plan teaches you in a month.

Three operational consequences:

- **No half-finished work.** Don't merge a feature that's 80% done with a TODO for the rest. Either it ships end-to-end or it's a branch.
- **No speculative abstraction.** Three similar lines beats a premature helper. Build the helper the second time you need it, not the first.
- **No "future-proofing" without a present user.** Every config knob, plugin point, and feature flag is dead weight until someone uses it.

---

## Agent Workflow: Explore → Plan → Code → Verify

Never blindly write code. Always follow this loop:

1. **Explore.** Search the codebase. Find relevant files, understand existing patterns before touching anything.
2. **Plan.** Assess the blast radius (how many files, how long). For significant changes, present 2–3 high-level approaches with pros/cons and ask for human approval before writing code.
3. **Code.** Implement following the rules below.
4. **Verify.** Run tests. Use the feature. Fix all failures before declaring done.

**Read before edit.** Always read a file before editing it, even if it was read earlier in the conversation.

**Ask for options first.** On non-trivial tasks, propose approaches before writing code. The first plausible plan is rarely the best plan.

**Close the loop yourself.** Build projects so the agent can compile, lint, run tests, and verify its own output without a human in the middle. When the agent can close the loop, you can trust the result. (Karpathy: "agentic coding works when the eval is the loop.")

---

## Communication style

- **Concise output.** No filler, no apologies, no moralizing. Skip generic advice.
- **Show your work.** Short reasoning when it changes the answer; silence when it doesn't.
- **Fail loud.** No catch-all exception handlers that silently swallow errors. Raise or log explicitly.
- **State results, not effort.** "Tests pass" beats "I worked hard to get tests to pass." Don't narrate.

---

## Architecture principles

- **No over-engineering.** Only make changes directly requested or clearly necessary. Keep solutions simple.
- **Boring tech wins.** Vanilla JS, SQLite, static HTML, system fonts, plain Python beat the framework-of-the-month. Every dependency is a future bug, a future migration, and a future security advisory. (levels.io: "boring tech is the secret.")
- **Single source of truth.** Constants, configs, and shared types derive from one place. If a value is duplicated, write a test that asserts the copies match.
- **Modular layers.** Separate concerns — data fetching, processing, storage, and presentation are distinct modules.
- **Idempotent operations.** Re-running anything should be safe and produce the same result. `INSERT OR IGNORE`, cache checks, deduplication by unique key.
- **Static when possible.** Prefer baked-in data over runtime backends when the update cycle allows. A `docs/` folder served by GitHub Pages beats a server you have to babysit.
- **Cost-optimized.** Stay on free tiers; use the cheapest resource that meets the requirement.
- **CLI-first.** Build CLI entry points before UI. Agents can invoke CLIs to self-validate output, closing the feedback loop without human intervention.
- **Minimize page weight and request count.** Audit total payload size and request count. Content-focused sites should be lightweight — fewest requests, smallest payload.
- **Tree-shake and code-split.** Don't bundle every controller for every page. Lazy-load what's only needed on demand.
- **Benchmark against best-in-class.** Compare your site against well-optimized references. If the simplest site in your org is orders of magnitude lighter, your build process needs review.
- **Document subsystems.** Maintain a `docs/` folder with notes on non-obvious subsystems, design decisions, and correct CLI invocations. One line of documentation prevents repeated mistakes.

---

## Error resilience

- **Never let one item crash the pipeline.** Wrap per-record processing in try/except. Log and continue.
- **Log aggressively.** Every request, parse, API call, cache hit/miss, and filter decision should be logged.
- **Cache everything fetchable.** Re-runs must be fast and cheap. Multi-layer caching where it pays off.
- **Validate everything.** Invalid responses from external services → log and skip, never crash.
- **Track errors visibly.** Use an `issues.md` file or errors array — failures must surface, not silently disappear.

---

## Security & credential handling

- **Never commit secrets.** API keys, tokens, and passwords never appear in committed code.
- Read credentials from environment variables only. Halt with a clear error if missing.
- Never log or print credential values.
- Always `.gitignore`: `.env`, `.env.local`, `credentials.json`, `secrets/`, `node_modules/`, `__pycache__/`, `dist/`, `*.pyc`.
- Before committing: `git diff --cached | grep -iE "apikey|password|token|secret"`.
- **Respect user privacy choices.** Don't proxy tracking SDKs through your own domain to bypass blockers. That erodes user trust permanently.
- **Check advisories before any package install / upgrade.** Supply-chain attacks land in popular npm/pip packages within hours of a maintainer being phished. Before suggesting or running `npm install` / `pip install`, fetch the latest advisory index at `https://pranava0x0.github.io/vibe-coding-security/llms-ctx.txt` (~12 KB, compact format). If the package or pattern matches a listed advisory, surface the warning before proceeding. Also maintain a `security.md` per project with the date of the last advisory sweep; refresh if older than 7 days.

---

## Testing & validation

- **Write tests alongside code, not as an afterthought.** Every new module or bug fix includes corresponding tests.
- **Regression test every bug fix.** The bug is the test case; without one, the fix rots.
- **Validate output data against expected schemas before writing to disk.** Pydantic with `extra="forbid"` (Python) or zod (TS) is the right shape.
- **Cover edges, not just happy paths:** empty `[] / {} / ""`; null for every optional field; boundary values; combined filters.
- **Run the full test suite before committing** to catch regressions.
- **Never ship test files to production.** CI excludes test files, fixtures, and debug artifacts from production bundles.
- **Tests are the eval suite.** Karpathy on LLMs: "your eval is the loop." Same for software — your test suite is the loop that tells you what works. Invest in it.

---

## Git discipline

- **Commit often** at natural checkpoints — small, focused commits over large monolithic ones.
- **Per natural unit:** per new module / feature, per bug fix (with its regression test), per doc update.
- **Commit in logical chunks — proactively.** When a body of work spans multiple concerns (e.g. a feature, its data regeneration, docs), split it into separate coherent commits in dependency order rather than one monolith. Once a chunk is self-consistent and verified (tests/build green), commit it when it makes sense — agents should do this without waiting for per-commit sign-off, narrating the chunk plan as they go. Keep the seed (`data/listing.json`) and its baked output (`docs/data/*.json`) in the **same** commit (see [AGENTS.md](AGENTS.md)).
- **Descriptive messages explain *what* and *why*.** Not "fix bug" — "fix off-by-one in pagination when filter is empty."
- **Never commit large binaries, downloaded data, or API keys.**
- **Don't amend pushed commits.** Create new commits — amend rewrites history that may already be on a teammate's machine.
- **Don't `--no-verify`.** If a hook fails, fix the underlying issue. Hooks exist because someone got burned.
- **No agent co-authors.** Never add `Co-Authored-By:` lines for AI coding agents (Claude, Codex/OpenAI, Gemini/Google, Copilot, Cursor, etc.) in commit messages. Commits are owned by the human who reviews and ships the work. Enforce per-repo with `git config --local claude.coauthor false`; set globally once with `git config --global claude.coauthor false` to cover all repos. **Tool-agnostic backstop (committed):** `.githooks/commit-msg` strips any AI-agent `Co-authored-by:` trailer regardless of which tool wrote it (and preserves legitimate human co-authors). **Enable once per clone:** `git config core.hooksPath .githooks` (already set in this repo's local config; worktrees share it). Verified 2026-06-07 — strips Claude/Codex/Gemini/Copilot, keeps human; full history is trailer-free.
- **Commit identity (use going forward).** Author commits via the GitHub account **`pranava0x0`** with its **noreply** email **`2497510+pranava0x0@users.noreply.github.com`** — attributes to the account without exposing a personal address in public history. Set **both** once — `git config --global user.name "pranava0x0" && git config --global user.email "2497510+pranava0x0@users.noreply.github.com"` — because if `user.name` is left unset git falls back to the OS full name. Agents don't change git config themselves — the human runs this.

---

## Data handling

- **Append-only data.** Append new records rather than overwriting. Deduplicate via unique keys.
- **Source attribution.** Every data record carries its origin (source URL, connector name, capture date). Users must be able to trace any value back to where it came from.
- **Defensive optional field handling.** Null-check every optional field before rendering or processing.
- **Null values render as explicit placeholders** ("N/A", "Not disclosed", "—") — never blank UI elements.
- **Capture dates over "current" framing.** External sources change; record `captured_at` and surface "as of YYYY-MM-DD" so historical drift is visible.

---

## Issue tracking (`issues.md`)

Maintain a living `issues.md` in the project root as an audit trail.

- Each bug: date, module/area, description, root cause (**code bug** vs. **test bug**), status (Open / Fixed).
- On resolution: what the fix was + the commit that resolved it.
- After every bug fix, check whether a new regression test is needed.

---

## Backlog (`backlog.md`)

Maintain a `backlog.md` for ideas, features, and enhancements.

- Add ideas immediately when they come up — don't lose them.
- Each item: brief description + priority (low / medium / high).
- Review and reprioritize periodically. Demote stale "high" items to "low" rather than letting them rot at the top.

---

## Python standards

*(Apply when the project uses Python.)*

- Type hints on all functions.
- `pathlib.Path` for file paths.
- `logging` module — no bare `print` for runtime output.
- All constants in a single config module.
- Pin dependencies in `requirements.txt`.
- Pydantic for data validation.
- Python 3.9+ unless specified otherwise.

---

## Frontend standards

*(Apply when the project has a web frontend. Full design system lives in [DESIGN.md](DESIGN.md).)*

- Functional components + hooks only. No class components.
- Colors, enums, and constants in a dedicated file — never hardcoded inline.
- Data transforms belong in hooks or utility functions, not in components.
- Loading, error, and empty states on every view.
- Visible focus indicators on every interactive element.
- **Mobile-first responsive design.** Test at 375px (iPhone SE) before declaring done.
- TypeScript strict mode when the project uses TypeScript. No `any`.
- **Touch targets ≥ 44px.** Non-negotiable on touch devices.
- **Deduplicate image assets.** Each image once; use `<picture>` with `srcset` so the browser picks AVIF / WebP / PNG. Never serve uncompressed PNGs for content.
- **Only load libraries used on the page.** No backend-only deps leaking into read-only frontend pages.
- **Descriptive `alt` on every content image.** Never `alt=""`.
- **Responsive CSS, not duplicate DOM trees.** Handle mobile / desktop with media queries — never render the same content twice.
- **The `[hidden]` trap.** Writing `display: inline-flex` / `display: block` on an element that also uses the `hidden` HTML attribute makes the CSS rule win and the attribute become a no-op. Always pair `display: ...` overrides with an explicit `[hidden] { display: none }` rule.

---

## Network ethics & rate limiting

*(Apply when the project fetches from external sources.)*

- Minimum 1.5–2s delay between requests to any single host.
- Informative `User-Agent` header.
- 429 → exponential backoff starting at 10s.
- Cache all fetched content to disk. Re-runs never re-download cached content.
- If a service persistently blocks after retries, log to `issues.md` and gracefully skip. Never crash.
- **Start small.** Validate a scraper against a handful of pages before scaling to full runs.

---

## AI / API cost optimization

*(Apply when the project uses LLM APIs.)*

- Use the cheapest model that meets quality requirements (e.g., Haiku before Opus).
- Keyword pre-filtering to skip irrelevant content before sending to expensive APIs.
- Truncate / excerpt input to reduce token usage.
- Cache API responses by content hash. Never re-classify identical content.
- Log cost impact at each optimization layer. Print a cost summary at the end of each run.
- `--dry-run` and `--fetch-only` modes must work without an API key.
- **Multi-agent harnesses (deep-research, Workflow fan-outs) are 10–100× a single call — size the tool to the ask.** Measured on this repo (2026-06-02): one `deep-research` run fans out to **up to ~95 subagent calls** (1 scope + 5 search + ≤15 fetch + **≤25 claims × 3 votes = 75 verify** + 1 synth) and burned **~7.7M tokens *before* it even finished**. The cost isn't one big call — it's dozens of small agents each *re-loading* the system prompt + tools + the (long) question + a JSON schema, so `cache_creation` + `cache_read` dominate. The **verify phase is ~80% of the agents** (the 3-vote adversarial pass). Rules:
    - **Right-size before reaching for the harness.** A bounded factual lookup → a direct `WebSearch` / a few `WebFetch` calls inline (one-to-low-tens of K tokens). Reserve the full fan-out for genuinely deep, multi-source, *fact-checked* reports where adversarial verification earns its cost.
    - **Don't auto-launch a research/orchestration workflow.** It requires **explicit user opt-in** every time (the `Workflow` tool enforces this; a *skill* that wraps it does not — so confirm cost/scope with the user before invoking). Surface the rough agent count + token order-of-magnitude first.
    - **If you do run it, turn the knobs down.** The fan-out constants live at the top of the generated script (`MAX_FETCH`, `MAX_VERIFY_CLAIMS`, `VOTES_PER_CLAIM`). Lower `MAX_VERIFY_CLAIMS`, and set `VOTES_PER_CLAIM=1` unless correctness is genuinely safety-critical — 3× verification triples the dominant phase for marginal gain on well-sourced `.gov` facts. Narrow the question so the scope agent picks fewer angles.

---

## Working with AI agents (meta-principles)

This file *is* the guidance an AI agent reads on entry. These rules are how to use the agent well.

- **Context is RAM, not memory.** (Karpathy: LLMs are "fuzzy CPUs"; context is the working set.) Fill it with what's needed for the current task — no more, no less. Watch for *context poisoning* (early errors that compound), *context distraction* (irrelevant content that buries what matters), and *context clash* (contradictory instructions).
- **Start fresh on topic switches.** Use `/clear` between unrelated problems. Long mixed-topic contexts degrade quality. Break complex tasks into small steps and commit between them.
- **AI has no taste.** Actively review output for: excessive try/catch, unnecessary abstractions, code bloat instead of refactoring, generic naming, and poor judgment on simplicity vs. structure. These are recurring failure modes that require human correction.
- **Loose heuristic parsers produce *plausible-looking* garbage — guard against it with data, not just code review.** A "grab any line containing `Finding`/`Order`, or text near `$N`" parser feels reasonable and silently ships Table-of-Contents leaders and page furniture as fake findings (2026-06-23: 477 such "findings" had accumulated, ~27% of the corpus). When a parser emits *verbatim* data, add a **corpus-wide regression guard** that asserts the absence of the garbage signatures (dotted/`…` leaders, `(cid:)` glyph artifacts, runaway field length, contentless titles) — `tests/test_sources.py::test_no_garbled_findings_in_committed_corpus`. The discipline: anchor parsers on structured markers, **bound** their region, **validate against a self-stated count** when the document gives one, and **fall back to metadata-only** rather than emit anything that isn't clean. See [AGENTS.md](AGENTS.md) → "What NOT to do" and [ISSUES.md](ISSUES.md).
- **AI is a tool, not a substitute for engineering discipline.** Apply fundamentals to AI-generated code: performance audits, bundle analysis, code review, optimization passes. High LOC means nothing if the code is bloated.
- **Vibe coding is fine for throwaway; engineer the rest.** Karpathy: vibe coding works when you never have to maintain the code. The moment a user depends on it, you owe it engineering discipline.
- **Closed-loop validation.** Build projects so the agent can compile, lint, run tests, and verify its own output without intervention. This is the single biggest force multiplier — when the agent can answer "did it work?" itself, every iteration is fast.
- **Evaluate every agent run.** Each time you spawn a subagent, do a short retrospective when it returns: was an agent the right tool (vs. inline search/Python)? What did it cost (`subagent_tokens` + `tool_uses` → tokens-per-useful-result)? Did it follow its prompt's rules, and did the result survive your own verification? Then fold the lesson into a *file* — a prompt template, a **harness + test** for any recurring manual step, a cost/threshold note in a dated memory, or a dead-seam entry in the backlog — not just the turn's reply. If the same correction would apply to the next run, it doesn't belong only in your head. (Project specifics: [AGENTS.md](AGENTS.md) § "After every agent run — evaluate it".)
- **Keep this file current.** When something unexpected happens — a pattern that failed, a correct CLI invocation, a library quirk — add a concise note. This file grows incrementally as organizational scar tissue. It is not rewritten from scratch.
- **Write big plans to files.** For large tasks, write the spec to a `docs/` markdown file and review it before executing. Persists context across sessions; allows second-opinion review before building.
- **Don't hand-roll background waiters — `run_in_background` already notifies you on completion.** The single biggest time-sink in the 2026-06-08 session was writing manual `while pgrep …; do sleep N; done` waiters around `pipeline.sources` runs. They failed three ways; learn all three:
    1. **`pgrep -f` self-matches the waiter.** `while pgrep -f "pipeline.sources"; do sleep N; done` — the *waiter's own command line contains the string `pipeline.sources`*, so `pgrep -f` finds itself and the loop never exits (every such waiter had to be `pkill`-ed; exit 144). **An earlier version of this very bullet recommended that pattern — it was wrong.** If you must poll for a process, match the *real* invocation precisely: `pgrep -f "python.* -m pipeline.sources"` (excludes the shell wrapper), or capture the PID and poll that. Better: don't poll at all.
    2. **`sleep N; tail …` chains are blocked** by the harness. Don't chain a sleep before reading output.
    3. **The watched process may outlive your assumptions** (large-PDF fetch/extract, F5/Cloudflare backoff can take many minutes), so a too-tight loop spins forever or a too-loose one races.
  **The right pattern:** launch the long job with `run_in_background: true` and simply *wait for the completion notification* — do other independent work meanwhile, or end the turn. To wait on a *condition* (not a process), use the Monitor tool. Always run `pgrep -fl "<project-path>"` before declaring done and `pkill`/`kill` any lingering waiter shells (`pkill -f "while pgrep"`).
- **Never run two instances of the same pipeline stage concurrently.** Two `pipeline.sources --seed X` (or a manual re-run started before the first finished) write the *same* `data/processed/<id>/` dirs and race. Wait for one to finish before starting another on overlapping seeds.
- **Don't gate a commit behind a piped filter in an `&&` chain.** `pytest … | grep -E "passed" && git commit …` silently *skips the commit* when `grep` exits non-zero (no match on the piped line) — happened twice. Run the test, read the result, then commit as a separate step.

---

## Influences

The patterns above are distilled from running many small projects in this folder. Two outside voices shaped them:

- **Andrej Karpathy** — "make it work, then make it good"; the LLM-as-fuzzy-CPU framing; eval-as-the-loop; context engineering over prompt engineering; the closed-loop bar for trustworthy agents; vibe-coding as the right tool for throwaway and the wrong tool for production.
- **Pieter Levels (levels.io)** — ship fast and ugly; boring tech beats shiny tech; solo-friendly defaults (vanilla, SQLite, single-file apps, cheap hosting); profit before scale; don't add a dependency you can't maintain alone; talk to users daily.

When in doubt, both would say the same thing: **ship the smallest version that works, then iterate based on what real users do, not what you imagine they'll do.**
