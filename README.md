# FERC Document Analysis

Static tooling to **download, extract, structure, and visualize FERC audit reports** — surfacing the findings of noncompliance and corrective recommendations that recur across the corpus.

The first module is the **FERC Audit Explorer** — electric (Form 1), gas (Form 2) and oil (Form 6) audits. The longer-term goal is an *"audit-my-document"* tool that flags likely issues in a filing using patterns mined from historical audits.

## Principles

- **Static-first.** A Python CLI pipeline produces JSON; a vanilla HTML/CSS/JS site (`docs/`) reads it. Hosted on GitHub Pages. No backend, no framework.
- **Source.** FERC publishes final audit reports (FY2015–present) at <https://www.ferc.gov/audits>. Every record carries its source URL and capture date.

## Layout

```
pipeline/      CLI stages: listing → backfill → fetch → extract → structure → patterns → build
  config.py    single source of truth (paths, URLs, tunables)
data/
  listing.json scraped audit index (the seed; committed)
  raw/         downloaded PDFs (gitignored — re-fetchable from listing.json)
  processed/   per-report extracted text + structured JSON
docs/          GitHub Pages site (HTML/CSS/JS) + baked data/*.json
tests/         pytest suite
```

## Quickstart

```bash
pip install -r requirements.txt          # all deps already present in this env

python -m pipeline.listing                # parse data/listing.json from the live snapshot (71 reports, 2019+)
python -m pipeline.backfill               # add FY2014-2018 from a Wayback snapshot (+49 -> 120; ferc.gov-only)
python -m pipeline.fetch                  # download report PDFs -> data/raw/ (rate-limited, cached)
python -m pipeline.classify               # tag each PDF by FERC form -> industry (electric/gas/oil)
python -m pipeline.extract                # PDF -> per-page text (all reports; --limit N to cap)
python -m pipeline.structure              # text -> findings + recommendations (+ FA/PA audit_type)
python -m pipeline.patterns               # cross-report themes
python -m pipeline.build                  # bake docs/data/*.json + llms.txt (all forms)

python -m http.server -d docs 8000                       # preview at http://localhost:8000
pytest -q                                                # run the test suite
```

**Scope:** all FERC utility audits — electric (Form 1), gas (Form 2) and oil (Form 6),
both financial (FA) and non-financial (PA), for every available year. The live /audits page
lists 2019+; FY2014-2018 are backfilled from a saved Internet Archive Wayback snapshot
(ferc.gov-origin only — see [ISSUES.md](ISSUES.md)). The pipeline is **idempotent**
(re-runs skip cached downloads), and the whole corpus is structured end-to-end.

## Project docs

- [CLAUDE.md](CLAUDE.md) — engineering principles + this project's intent
- [AGENTS.md](AGENTS.md) — how AI agents work in this repo (file map, commands)
- [DESIGN.md](DESIGN.md) — visual system (periwinkle + Google+ stream)
- [DATA_STRUCTURE.md](DATA_STRUCTURE.md) — the document/data model across FERC docs
- [BACKLOG.md](BACKLOG.md) · [ISSUES.md](ISSUES.md) · [security.md](security.md)
