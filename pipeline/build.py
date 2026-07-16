"""Bake the static site's data files into docs/data/.

Reads every structured report.json, writes the JSON files the site loads:
  reports_index.json      — card/filter fields for every report (the first-paint payload)
  findings_<collection>.json — the rest of each report (findings + thread fields), fetched lazily
  reports.json            — all structured reports, newest first (stable full-corpus download)
  patterns.json           — cross-report aggregates (from pipeline.patterns)
  meta.json               — corpus counts + provenance for the page footer/header

The index/detail split keeps the first paint small: rendering a collapsed card
needs ~18 metadata fields, while finding bodies are ~80% of the corpus text and
are only needed once a card is expanded. The split is LOSSLESS — `merge_split`
reverses `split_reports` exactly, and a test asserts the round-trip against the
committed corpus, so reports.json stays the single source of truth.

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
    {"key": "state_reference", "label": "State Reference Docs"},
]
COLLECTION_KEYS: list[str] = [c["key"] for c in COLLECTIONS]


# Fields the site needs to render a COLLAPSED card, run every facet/sort, and
# match a search on company/docket/period. Everything else (findings, thread
# metadata, provenance URLs) ships in the per-collection detail file. Keep this
# list in sync with docs/js/app.js: cardNode() + matches() may only read these.
CARD_FIELDS: list[str] = [
    "id",
    "collection",
    "company",
    "docket",
    "docket_full",
    "issued_date",
    "audit_type",
    "doc_type",
    "industry",
    "forms",
    "functions",
    "finding_count",
    "themes",
    "cost_to_customers",
    "structured",
    "source",
    "audit_period",
]

# Rollups the index carries so the stream can show a recommendation pill and a
# report-level $ pill (and sort by them) without fetching finding bodies. Derived
# from findings at bake time, so merge_split drops them to reverse the split.
DERIVED_INDEX_FIELDS: tuple[str, ...] = ("rec_count", "amount_max")


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_json_min(path: Path, payload) -> None:
    """Minified writer for the runtime payloads — these are machine-read only.

    reports.json stays pretty-printed (it's the documented human/machine download);
    the index and detail files are fetched by the page on every visit, where the
    indentation is ~40% of the bytes for no reader benefit.
    """
    path.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")


def split_reports(report_dicts: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """Split baked report dicts into (index, details-by-collection).

    Index entries carry CARD_FIELDS plus the two derived rollups; detail entries
    carry every remaining field, keyed by report id within their collection.
    Pure function — see merge_split for the exact inverse.
    """
    index: list[dict] = []
    details: dict[str, dict] = {}
    for r in report_dicts:
        entry = {k: r.get(k) for k in CARD_FIELDS}
        findings = r.get("findings") or []
        entry["rec_count"] = sum(len(f.get("recommendations") or []) for f in findings)
        amounts = [f["amount_usd"] for f in findings if f.get("amount_usd") is not None]
        # Report-level $ pill = the largest cited figure among its findings. Never a
        # sum: findings can restate the same dollars, and summing them would invent
        # a number no report states (CLAUDE.md — verbatim only, no estimates).
        entry["amount_max"] = max(amounts) if amounts else None
        index.append(entry)
        details.setdefault(r["collection"], {})[r["id"]] = {
            k: v for k, v in r.items() if k not in CARD_FIELDS
        }
    return index, details


def merge_split(index: list[dict], details: dict[str, dict]) -> list[dict]:
    """Exact inverse of split_reports — the build-parity guard's other half."""
    out: list[dict] = []
    for entry in index:
        detail = details.get(entry["collection"], {})[entry["id"]]
        merged = {k: v for k, v in entry.items() if k not in DERIVED_INDEX_FIELDS}
        merged.update(detail)
        out.append(merged)
    return out


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
    # Regulators actually represented in the corpus — the site's hero trust line
    # states this count, so it must be a real count of the committed records
    # rather than a hand-maintained claim that drifts as states are added.
    jurisdictions = sorted({r.jurisdiction for r in reports if r.jurisdiction})
    return {
        "generated_at": date.today().isoformat(),
        "jurisdictions_covered": jurisdictions,
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
    # The stable full-corpus download (documented in the footer + data page). It is
    # no longer the runtime payload — the site loads the index/detail split below.
    _write_json(args.out / "reports.json", report_dicts)

    # First-paint payload + lazily-fetched finding bodies (see module docstring).
    index, details = split_reports(report_dicts)
    _write_json_min(args.out / "reports_index.json", index)
    for key in COLLECTION_KEYS:
        # Emit every canonical collection, even empty, so the site can fetch a
        # detail file for any tab without a 404-shaped special case.
        _write_json_min(args.out / f"findings_{key}.json", details.get(key, {}))

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
