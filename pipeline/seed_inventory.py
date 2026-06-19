"""Dump the current corpus inventory for finder-agent deduplication.

Web-research **finder agents** (see AGENTS.md § "Dispatching a research-finder
agent") repeatedly surface documents we ALREADY hold — the 2026-06-19 CA PG&E
ERRA and MO Ameren FAC near-duplicates slipped through because the agent was
handed a *hand-written, partial* "already have" list. This module prints the
**full, current** inventory (every seeded doc + the FERC audits) as compact,
paste-ready lines so a finder agent can dedupe against the real corpus instead.

Usage:
    python3 -m pipeline.seed_inventory                  # all jurisdictions
    python3 -m pipeline.seed_inventory --jurisdiction SC TX   # filter
    python3 -m pipeline.seed_inventory --dockets-only   # just "JURIS docket" pairs

The output is informational (read-only); it touches no data.
"""
from __future__ import annotations

import argparse
import json
import logging

from pipeline import config

logger = logging.getLogger(__name__)


def load_inventory() -> list[dict]:
    """Return one row per known document: {id, jurisdiction, company, docket,
    doc_type, pdf_url}. Sources: every list-shaped seed file in data/seeds/ plus
    the structured FERC audits in data/processed/ that have no seed (the listing
    docs). De-duplicated by id."""
    rows: dict[str, dict] = {}

    for path in sorted(config.SEEDS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):  # skip planning dicts (e.g. tier3_targets.json)
            continue
        for rec in data:
            if not isinstance(rec, dict) or "id" not in rec:
                continue
            rows[rec["id"]] = {
                "id": rec["id"],
                "jurisdiction": rec.get("jurisdiction") or "?",
                "company": rec.get("company") or "?",
                "docket": rec.get("docket") or "",
                "doc_type": rec.get("doc_type") or "",
                "pdf_url": rec.get("pdf_url") or "",
            }

    # FERC audits live in processed/ without a seed file — include them so a
    # finder agent dedupes against the FERC corpus too.
    for rep in config.PROCESSED_DIR.glob("*/report.json"):
        try:
            d = json.loads(rep.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rid = d.get("id")
        if not rid or rid in rows:
            continue
        rows[rid] = {
            "id": rid,
            "jurisdiction": d.get("jurisdiction") or "?",
            "company": d.get("company") or "?",
            "docket": d.get("docket") or "",
            "doc_type": d.get("doc_type") or "",
            "pdf_url": d.get("pdf_url") or d.get("source_url") or "",
        }

    return sorted(rows.values(), key=lambda r: (r["jurisdiction"], r["docket"], r["id"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jurisdiction", nargs="*", help="filter to these jurisdiction codes (e.g. SC TX)")
    ap.add_argument("--dockets-only", action="store_true", help="print just 'JURIS  docket' pairs")
    args = ap.parse_args()

    rows = load_inventory()
    if args.jurisdiction:
        want = {j.upper() for j in args.jurisdiction}
        rows = [r for r in rows if r["jurisdiction"].upper() in want]

    print(f"# Corpus inventory — {len(rows)} documents (dedupe finder-agent candidates against this)\n")
    for r in rows:
        if args.dockets_only:
            print(f"{r['jurisdiction']:4} {r['docket']}")
        else:
            print(f"{r['jurisdiction']:4} | {r['docket'] or '(no docket)':22} | {r['company'][:48]:48} | {r['id']}")


if __name__ == "__main__":
    main()
