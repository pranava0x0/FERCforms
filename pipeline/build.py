"""Bake the static site's data files into docs/data/.

Reads every structured report.json, writes the three JSON files the site loads:
  reports.json  — all structured reports, newest first
  patterns.json — cross-report aggregates (from pipeline.patterns)
  meta.json     — corpus counts + provenance for the page footer/header

These are build output (never hand-edited); re-run after structure/patterns.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from pipeline import config, llmstxt
from pipeline.patterns import _themes_for, load_reports, summarize

logger = logging.getLogger(__name__)


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Bake docs/data/*.json for the static site")
    ap.add_argument("--out", type=Path, default=config.SITE_DATA_DIR)
    args = ap.parse_args()

    reports = load_reports(config.PROCESSED_DIR)
    # Scope: this tool is the FERC Form 1 / electric audit explorer. Non-electric
    # (gas Form 2, oil Form 6) audits stay in the backlog (see BACKLOG.md).
    reports = [r for r in reports if r.industry == "electric"]
    reports.sort(key=lambda r: (r.issued_date or date.min, r.id), reverse=True)
    if not reports:
        logger.warning("no electric reports structured; run classify + structure --electric-only")

    args.out.mkdir(parents=True, exist_ok=True)

    # Bake a per-report `themes` array so the site can facet by theme without
    # re-implementing the keyword rules (they stay single-source in patterns.py).
    report_dicts = []
    for r in reports:
        d = json.loads(r.model_dump_json())
        themes: set[str] = set()
        for f in r.findings:
            themes.update(_themes_for(f.title + " " + (f.summary or "")))
        d["themes"] = sorted(themes)
        report_dicts.append(d)

    summary = summarize(reports)
    _write_json(args.out / "reports.json", report_dicts)
    _write_json(args.out / "patterns.json", json.loads(summary.model_dump_json()))

    listing = json.loads(config.LISTING_PATH.read_text(encoding="utf-8")) if config.LISTING_PATH.exists() else []
    classification_path = config.PROCESSED_DIR / "classification.json"
    classification = json.loads(classification_path.read_text(encoding="utf-8")) if classification_path.exists() else {}
    electric_identified = sum(1 for c in classification.values() if c.get("industry") == "electric")
    meta = {
        "generated_at": date.today().isoformat(),
        "source": config.AUDITS_LISTING_URL,
        "scope": "FERC Form 1 (electric) audits",
        "reports_total_listed": len(listing),
        "electric_identified": electric_identified,
        "reports_structured": len(reports),
        "listing_captured_at": listing[0]["captured_at"] if listing else None,
    }
    _write_json(args.out / "meta.json", meta)

    # LLM-friendly entry points (llms.txt + llms-full.txt) at the site root.
    llmstxt.write_llms(config.DOCS_DIR, reports, summary, meta)

    logger.info(
        "baked %d electric reports -> %s (+ llms.txt, llms-full.txt; electric_identified=%d, total_listed=%d)",
        len(reports), args.out, meta["electric_identified"], meta["reports_total_listed"],
    )


if __name__ == "__main__":
    main()
