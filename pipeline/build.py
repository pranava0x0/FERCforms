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
from collections import Counter
from datetime import date
from pathlib import Path

from pipeline import config, llmstxt
from pipeline.models import AuditReport
from pipeline.patterns import (
    _themes_for,
    descriptor_themes,
    finding_theme_text,
    is_ratepayer_harm,
    load_reports,
    summarize,
)

logger = logging.getLogger(__name__)

# Canonical collections — one per UI tab. Order is the tab order. The site mirrors
# these keys/labels in docs/js/app.js; a test asserts the key sets stay in sync.
COLLECTIONS: list[dict[str, str]] = [
    {"key": "ferc_audit", "label": "FERC Audits"},
    {"key": "prudence_review", "label": "Prudence Reviews"},
    {"key": "state_audit", "label": "State PUC Audits"},
    {"key": "state_rate_case", "label": "State Rate Cases (Reference)"},
]
COLLECTION_KEYS: list[str] = [c["key"] for c in COLLECTIONS]


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def bake_report_dicts(reports: list[AuditReport]) -> list[dict]:
    """Per-report site dicts: model fields plus derived taxonomy tags.

    Every finding is tagged with its `themes` (keyword rules stay single-source in
    patterns.py) and a `cost_to_customers` flag (the ratepayer-harm axis). Reports
    carry the union `themes` and `cost_to_customers` = any finding flagged, so the
    site can facet without re-implementing the rules.
    """
    out: list[dict] = []
    for r in reports:
        d = json.loads(r.model_dump_json())
        report_themes: set[str] = set()
        for fd, f in zip(d["findings"], r.findings):
            ft = _themes_for(finding_theme_text(f, include_recs=r.collection != "ferc_audit"))
            fd["themes"] = ft
            fd["cost_to_customers"] = is_ratepayer_harm(ft)
            report_themes.update(ft)
        # Reference records (structured=False) are additionally tagged from their
        # displayed descriptors (doc_type + source_note) — see patterns.descriptor_themes.
        report_themes.update(descriptor_themes(r))
        d["themes"] = sorted(report_themes)
        # The ratepayer-harm flag stays finding-derived only — a descriptor tag
        # (e.g. an affiliate-audit doc_type) must never set the harm badge.
        d["cost_to_customers"] = any(fd["cost_to_customers"] for fd in d["findings"])
        out.append(d)
    return out


def build_meta(reports: list[AuditReport], listing: list[dict]) -> dict:
    """Corpus meta for the site footer / llms.txt.

    Industry counts are computed from the structured `reports` themselves (which
    are committed and each carry `industry`) — NOT from the gitignored
    classification.json. That keeps a clean checkout's `pipeline.build` fully
    reproducible instead of silently writing empty counts.
    """
    by_industry = Counter((r.industry or "unknown") for r in reports)
    by_collection = Counter(r.collection for r in reports)
    return {
        "generated_at": date.today().isoformat(),
        "source": config.AUDITS_LISTING_URL,
        "scope": "FERC utility audits — electric, gas & oil",
        "reports_total_listed": len(listing),
        "by_industry_identified": dict(by_industry),
        "reports_structured": len(reports),
        # Per-tab report counts (every canonical collection present, even at 0, so
        # the site can render an honest empty tab rather than a missing one).
        "by_collection": {k: by_collection.get(k, 0) for k in COLLECTION_KEYS},
        "listing_captured_at": listing[0]["captured_at"] if listing else None,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Bake docs/data/*.json for the static site")
    ap.add_argument("--out", type=Path, default=config.SITE_DATA_DIR)
    args = ap.parse_args()

    reports = load_reports(config.PROCESSED_DIR)
    # Scope: all FERC utility audits across the electric, gas, and oil sectors,
    # both financial (FA) and non-financial (PA). See CLAUDE.md.
    reports.sort(key=lambda r: (r.issued_date or date.min, r.id), reverse=True)
    if not reports:
        logger.warning("no reports structured; run classify + structure first")

    args.out.mkdir(parents=True, exist_ok=True)

    # Per-report site dicts with derived taxonomy tags (themes + ratepayer-harm
    # axis), tagged per finding and per report. Rules stay single-source in patterns.py.
    report_dicts = bake_report_dicts(reports)

    summary = summarize(reports)
    _write_json(args.out / "reports.json", report_dicts)
    _write_json(args.out / "patterns.json", json.loads(summary.model_dump_json()))

    # Per-collection aggregates (one PatternsSummary per tab) so each tab shows its
    # OWN top stats/patterns/trends. Every canonical collection is emitted, even
    # empty, so the site always has a summary to render for each tab.
    by_collection = {
        c["key"]: summarize([r for r in reports if r.collection == c["key"]])
        for c in COLLECTIONS
    }
    _write_json(
        args.out / "patterns_by_collection.json",
        {k: json.loads(s.model_dump_json()) for k, s in by_collection.items()},
    )

    listing = json.loads(config.LISTING_PATH.read_text(encoding="utf-8")) if config.LISTING_PATH.exists() else []
    meta = build_meta(reports, listing)
    _write_json(args.out / "meta.json", meta)

    # LLM-friendly entry points (llms.txt + llms-full.txt) at the site root.
    llmstxt.write_llms(config.DOCS_DIR, reports, summary, meta)

    logger.info(
        "baked %d reports -> %s (+ llms.txt, llms-full.txt; by_industry=%s, total_listed=%d)",
        len(reports), args.out, meta["by_industry_identified"], meta["reports_total_listed"],
    )


if __name__ == "__main__":
    main()
