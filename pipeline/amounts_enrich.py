"""Enrich committed FERC audit findings with a cited headline dollar figure.

Usage:
    python -m pipeline.amounts_enrich --ids <id1> <id2> ...

For each report id: ensures its PDF is fetched (cached, idempotent — reuses
pipeline.fetch), extracts per-page text (reuses pipeline.extract), then for
every finding ALREADY committed for that report, finds the first dollar
figure already present in its OWN summary/recommendations text (see
pipeline/amounts.py — never new text from an unvetted wider span) and locates
which source-PDF page carries it.

A finding's amount_usd/amount_usd_quote/amount_usd_page are set ONLY as a
unit, and ONLY when a page citation is actually found — "has a citation" is a
hard requirement here, not best-effort. A dollar figure with no locatable page
citation is left uncited (all three fields None) rather than shipped partial;
`pipeline.verify_amounts` re-checks every citation this script writes.

Every other field on the report is left untouched (title/summary/recommend-
ations/finding_count/structured are never touched by this script).
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from pipeline import amounts, config, fetch
from pipeline.models import AuditReport

logger = logging.getLogger(__name__)


def enrich_report(report_id: str, listing_by_id: dict, session) -> dict:
    """Enrich one committed report's findings in place. Returns a summary dict."""
    report_path = config.PROCESSED_DIR / report_id / "report.json"
    data = json.loads(report_path.read_text(encoding="utf-8"))
    report = AuditReport.model_validate(data)

    text = amounts.fetch_and_extract(listing_by_id[report_id], session)

    cited = 0
    uncited_mention = 0
    no_mention = 0
    for finding in report.findings:
        mention = amounts.find_primary_dollar_mention(finding)
        if mention is None:
            no_mention += 1
            continue
        page = amounts.locate_page(mention, text.pages)
        if page is None:
            uncited_mention += 1
            logger.warning(
                "%s finding %d: dollar mention %r found but no page citation — left uncited",
                report_id, finding.index, mention.raw,
            )
            continue
        finding.amount_usd = mention.amount_usd
        finding.amount_usd_quote = mention.quote
        finding.amount_usd_page = page
        cited += 1

    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    logger.info(
        "%s: %d finding(s) cited, %d mention(s) uncited (no page match), %d with no dollar figure",
        report_id, cited, uncited_mention, no_mention,
    )
    return {"id": report_id, "cited": cited, "uncited_mention": uncited_mention, "no_mention": no_mention}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Enrich FERC audit findings with a cited dollar figure")
    ap.add_argument("--ids", nargs="+", required=True, help="report ids to enrich")
    ap.add_argument("--listing", type=Path, default=config.LISTING_PATH)
    args = ap.parse_args()

    listing = fetch.load_listing(args.listing)
    listing_by_id = {e.id: e for e in listing}
    missing = [i for i in args.ids if i not in listing_by_id]
    if missing:
        raise SystemExit(f"not in listing.json (FERC audits only): {missing}")

    session = fetch.make_session()
    results = []
    failures: list[tuple[str, str]] = []
    for i in args.ids:
        try:
            results.append(enrich_report(i, listing_by_id, session))
        except Exception as exc:  # noqa: BLE001 — never let one report's fetch/extract failure abort the batch
            failures.append((i, str(exc)))
            logger.error("FAILED %s: %s", i, exc)

    total_cited = sum(r["cited"] for r in results)
    total_uncited = sum(r["uncited_mention"] for r in results)
    logger.info(
        "done: %d report(s) ok, %d failed, %d finding(s) cited, %d mention(s) uncited",
        len(results), len(failures), total_cited, total_uncited,
    )
    for report_id, error in failures:
        logger.error("  %s: %s", report_id, error)


if __name__ == "__main__":
    main()
