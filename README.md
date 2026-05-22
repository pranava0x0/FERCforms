# FERC Document Analysis

Static tooling to **download, extract, structure, and visualize FERC audit reports** — surfacing the findings of noncompliance and corrective recommendations that recur across the corpus.

The first module is a **FERC Form 1 Audit** explorer. The longer-term goal is an *"audit-my-document"* tool that flags likely issues in a filing using patterns mined from historical audits.

## Principles

- **Static-first.** A Python CLI pipeline produces JSON; a vanilla HTML/CSS/JS site (`docs/`) reads it. Hosted on GitHub Pages. No backend, no framework.
- **Source.** FERC publishes final audit reports (FY2015–present) at <https://www.ferc.gov/audits>. Every record carries its source URL and capture date.

## Layout

```
pipeline/      CLI stages: fetch → extract → structure → patterns → build
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
pip install -r requirements.txt        # all deps already present in this env
# (CLI commands documented here as each stage lands)
```

## Project docs

- [CLAUDE.md](CLAUDE.md) — engineering principles + this project's intent
- [AGENTS.md](AGENTS.md) — how AI agents work in this repo (file map, commands)
- [DESIGN.md](DESIGN.md) — visual system (periwinkle + Google+ stream)
- [DATA_STRUCTURE.md](DATA_STRUCTURE.md) — the document/data model across FERC docs
- [BACKLOG.md](BACKLOG.md) · [ISSUES.md](ISSUES.md) · [security.md](security.md)
