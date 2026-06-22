---
name: refresh-ferc-data
description: Refresh or extend the FERC Audit Explorer dataset for THIS project — re-run the pipeline, add a new state/regional source seed, parse a new audit format, or rebuild the baked site data + llms.txt. Use when the user says "refresh the data", "rebuild the dataset", "re-scrape", "add <state> audits", "ingest a new source", "regenerate docs/data", or similar. Encodes the exact CLI invocations, the per-source seed workflow, the parse/fetch flags, and the commit discipline specific to this repo.
---

# Refreshing the FERC Audit Explorer dataset

Pipeline lives in `pipeline/`; it produces baked JSON in `docs/data/` + `docs/llms*.txt` that the
static site reads. Full per-source access mechanics: [docs/data-sources.md](../../../docs/data-sources.md).
Commit discipline (load-bearing): **keep a seed and its baked output (`docs/data/*.json`,
`docs/llms*.txt`) in the SAME commit.** Run `python3 -m pytest` before every commit.

## 1. Rebuild only (data already ingested)

Edit happened to `pipeline/patterns.py` (themes), `pipeline/llmstxt.py`, or a `report.json`?
**A full rebuild is THREE steps, not one** — `build` does not regenerate everything:

```bash
python3 -m pipeline.build        # re-bakes docs/data/*.json + llms.txt + llms-full.txt
python3 -m pipeline.patterns     # writes data/processed/patterns.json (GITIGNORED test artifact)
python3 -m pipeline.csv_export   # regenerates docs/data/findings.csv (separate from build)
python3 -m pytest -q
```

Why all three (each omission bit in the 2026-06-19 session):
- **`pipeline.patterns`** writes `data/processed/patterns.json`, which `build` does NOT, and which
  `tests/test_themes.py` reads. It's **gitignored**, so a *fresh worktree fails 3 theme tests* until
  you run it — run `pipeline.patterns` first thing in a new clone/worktree before trusting `pytest`.
- **`pipeline.csv_export`** regenerates `docs/data/findings.csv` (a committed build output) and is
  **not** part of `build` — skip it after a data change and you commit a stale CSV. (No findings
  changed? The CSV won't change either — that's expected, not a skip.)

## 2. Full FERC pipeline (from scratch / new audit year)

Run in order (each stage is idempotent + cached; safe to re-run):

```bash
python3 -m pipeline.listing     # parse data/listing.json from the browser-captured /audits snapshot (2019+)
python3 -m pipeline.backfill    # add FY2014-2018 via a Wayback snapshot + eLibrary docket search (ferc.gov-only)
python3 -m pipeline.fetch       # download eLibrary PDFs -> data/raw/ (F5 cookie dance, rate-limited, cached)
python3 -m pipeline.classify    # tag each PDF by FERC form -> industry
python3 -m pipeline.extract     # PDF -> per-page text.json
python3 -m pipeline.structure   # text -> verbatim findings + recommendations (snapshot-gated)
python3 -m pipeline.build       # bake docs/data/*.json + llms.txt
```

The `/audits` listing and the Wayback snapshot are **browser-captured** (Cloudflare blocks scripts) —
they're committed inputs, not re-scraped here. eLibrary throttles bursts; if `fetch` 429s, back off
and re-run (idempotent). The prudence seed's 0-page records backfill by re-running `pipeline.sources`
when eLibrary is quiet.

## 3. Add a new state / regional source (metadata-only)

The high-value, repeatable path. **Always verify before seeding** (opaque doc IDs mislabel easily):

1. **Find the doc + its stable `.gov` URL.** Use the per-source recipe in
   [docs/data-sources.md](../../../docs/data-sources.md) (PA/MI plain GET; TX/SC scriptable search;
   VA direct DOCS path; IL server-rendered e-Docket; NY DPS DMM scriptable search; OH/NC browser-capture).
2. **Read page 1–2 of each PDF** (skip "Filing Receipt"/"Notice of Filing" covers) to label
   `company` / `issued_date` / `doc_type` accurately. Discard off-theme docs (the corpus is utility
   cost/prudence/audit matters — not generic presentations or rulemaking comments).
   **Verify-by-download (the proven pattern, generalizes GA/2026-06-22 NY):** never seed a search-found
   URL on trust — `requests.get` it (stream + ~45 MB cap so a 500-page report can't hang you), assert
   `content[:5]==b"%PDF-"`, then `fitz.open(stream=…)` → print `page_count` + page-1 text. The page-1
   caption is what you label from and is the proof the `pdf_url` resolves to the *claimed* document
   (a `200` on the wrong real doc is the fabrication trap). Seed `fetch:true` so the pipeline re-proves
   it. **Buffered-output gotcha:** Python stdout block-buffers when piped — run verify/ingest with
   `python3 -u` (or `flush=True`) or you'll see nothing until it finishes and mistake a slow large-PDF
   download for a hang.
3. **Write `data/seeds/<source>.json`** — one `SourceSeed` per doc: `collection:"state_audit"`,
   `jurisdiction`, `source`, `doc_type`, `industry`, `pdf_url`, `source_page_url`, `issued_date`,
   `docket`, `captured_at`, a full provenance `source_note`, `parse:false`. **`.gov` hosts only** —
   `load_seed` raises otherwise.
4. **Ingest + build + verify:**
   ```bash
   python3 -m pipeline.sources --seed data/seeds/<source>.json   # ONE seed file per call
   python3 -m pipeline.build && python3 -m pipeline.patterns && python3 -m pipeline.csv_export
   python3 -m pytest -q
   ```
   Then load `python3 -m http.server -d docs 8000`, open the **State PUC Audits** tab, confirm the
   records render ("Listed for reference" with the right doc-type pill).

   **Two re-ingest gotchas (2026-06-19):**
   - **Don't loop `pipeline.sources` over multiple seed files in one shell command.** The harness may
     background a `for … do pipeline.sources … done` loop and silently drop later iterations (the SD
     seed vanished this way). Run each seed file as its own call, or one combined run, and confirm
     each finished.
   - **Re-running a multi-record seed file re-extracts `text.json` for ALL its records.** A
     no-clobber guard protects existing `report.json`, **but not `text.json`** — and a throttled
     burst re-download can return a *truncated/wrong* PDF, silently corrupting a previously-good
     record (this is how the PGW seed got a 3-page stub over its real 95-page audit). After
     re-ingesting a file you only added to, **spot-check that pre-existing records kept their expected
     `page_count`** (`python3 -c "import json;print(json.load(open('data/processed/<id>/report.json'))['page_count'])"`).
5. **Verify sources before committing:** `python3 -m pipeline.verify_sources` — new records must land
   in **PROVEN** (DEAD/NON_PDF for a real PDF is a wrong/dead URL — fix it, don't commit it). The
   sweep also catches the wrong-document class of bug (a seed `pdf_url` pointing at an unrelated doc).
6. **Commit** the seed + new `data/processed/<id>/report.json` (force-add: `git add -f`, it's
   gitignored) + baked `docs/data` (incl. `findings.csv`) together.

## 4. WAF-blocked source (OH PUCO, NC NCUC, FERC /audits)

Scripts get 403/F5/Cloudflare. Open the doc in a **real browser (Chrome MCP)**, capture the stable
`.gov` PDF URL, and seed it with **`fetch:false`** (writes metadata-only without hitting the blocked
endpoint; page_count 0). **Never solve interactive CAPTCHAs** — only let the browser pass its own
non-interactive JS challenge. Then `pipeline.sources --seed … && pipeline.build`. See OH/NC in
[docs/data-sources.md](../../../docs/data-sources.md).

## 5. Parse a new audit format into findings

Metadata-only is the default. Only parse a format with a clean, enumerable structure, and **gate it
with a no-regression snapshot** (like `pipeline/structure.py` and `pipeline/state_structure.py`):
add a parser, a synthetic-fixture test + a real-report regression in `tests/`, flip `parse:true` on
those seeds, re-ingest, rebuild, verify. If a parse yields nothing or looks garbled, it must fall
back to metadata-only — never ship paraphrased or mangled "verbatim" text.

## Guardrails

- **Verbatim, no LLM editorializing.** Findings/recommendations are quoted exactly; themes are
  transparent keyword tags (`pipeline/patterns.py`), never model judgement.
- **Idempotent + cached.** Re-running anything is safe; raw PDFs (`data/raw/`) and per-page text are
  gitignored and re-fetchable.
- **Sweep for orphaned wrapper shells** after long-running background fetches (`pgrep -fl <project>`).
- Log access status in [ISSUES.md](../../../ISSUES.md); park new ideas in [BACKLOG.md](../../../BACKLOG.md).
