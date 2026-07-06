"""Line-by-line verification of every amount_usd citation in the committed corpus.

Every finding carrying an amount_usd must have a citation that holds up under
independent re-checking — this is the enforcement counterpart to
pipeline/amounts_enrich.py (see CLAUDE.md "loose heuristic parsers" — a figure
with no re-checkable citation is exactly the class of thing that discipline
guards against). Two tiers:

  OFFLINE (default, no network) — for every finding with amount_usd set:
    1. self-consistency: amount_usd_quote must be a verbatim (whitespace-
       normalized) substring of that SAME finding's own summary or one of its
       recommendations' text — proves the quote wasn't invented relative to
       already-committed, already-verbatim data.
    2. numeric consistency: re-parsing the dollar figure embedded in
       amount_usd_quote must reproduce amount_usd exactly — proves the number
       wasn't hand-edited independently of its quote.

  LIVE (--live, hits the network) — additionally re-fetches/re-extracts the
    source PDF (via the FERC eLibrary listing) and confirms amount_usd_page's
    page text actually contains the quote (or its bare dollar figure) — proves
    the citation holds up against a fresh, independent read of the source, not
    just internal self-consistency.

Usage:
    python -m pipeline.verify_amounts                  # offline, full corpus
    python -m pipeline.verify_amounts --live            # + live page recheck
    python -m pipeline.verify_amounts --ids <id> ...    # restrict to some ids

Exit code is non-zero if any finding fails a check.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from pipeline import amounts, config, extract, fetch

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _finding_own_text(finding: dict) -> str:
    parts = [finding.get("summary") or ""]
    parts += [r.get("text") or "" for r in finding.get("recommendations", [])]
    return " ".join(parts)


def check_offline(report_id: str, finding: dict) -> list[str]:
    """Returns a list of failure reasons (empty = pass)."""
    fails: list[str] = []
    quote = finding.get("amount_usd_quote")
    amount = finding.get("amount_usd")
    page = finding.get("amount_usd_page")
    idx = finding.get("index")

    if quote is None or amount is None or page is None:
        fails.append(f"{report_id} finding {idx}: amount_usd/_quote/_page must all be set together (partial fields)")
        return fails

    own_text_norm = _normalize(_finding_own_text(finding))
    if _normalize(quote) not in own_text_norm:
        fails.append(f"{report_id} finding {idx}: amount_usd_quote is not a substring of the finding's own summary/recommendations")

    m = amounts._DOLLAR_RE.search(quote)
    if not m:
        fails.append(f"{report_id} finding {idx}: amount_usd_quote contains no dollar figure at all")
    else:
        try:
            reparsed = amounts.parse_dollar_amount(m.group(0))
        except ValueError:
            fails.append(f"{report_id} finding {idx}: dollar figure in quote ({m.group(0)!r}) failed to re-parse")
        else:
            if abs(reparsed - amount) > 0.01:
                fails.append(
                    f"{report_id} finding {idx}: amount_usd={amount} does not match re-parsed {reparsed} from quote"
                )
    return fails


def check_live(report_id: str, finding: dict, listing_by_id: dict, session) -> list[str]:
    idx = finding.get("index")
    entry = listing_by_id.get(report_id)
    if entry is None:
        return [f"{report_id} finding {idx}: not a FERC audit (no listing.json entry) — cannot live-recheck"]
    try:
        fetch.download_pdf(session, entry, config.RAW_DIR)
        text = extract.extract_report(entry, config.RAW_DIR, config.PROCESSED_DIR)
    except Exception as exc:  # noqa: BLE001 — a fetch/extract failure is a check failure, not a crash
        return [f"{report_id} finding {idx}: could not fetch/extract source PDF to recheck: {exc}"]

    page_num = finding["amount_usd_page"]
    page = next((p for p in text.pages if p.page == page_num), None)
    if page is None:
        return [f"{report_id} finding {idx}: cited page {page_num} does not exist in the re-extracted PDF ({text.page_count} pages)"]

    page_norm = _normalize(page.text)
    quote_norm = _normalize(finding["amount_usd_quote"])
    if quote_norm in page_norm:
        return []
    m = amounts._DOLLAR_RE.search(finding["amount_usd_quote"])
    if m and _normalize(m.group(0)) in page_norm:
        return []
    return [f"{report_id} finding {idx}: neither the quote nor its dollar figure was found on the cited page {page_num} in a fresh re-extraction"]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Verify every committed amount_usd citation")
    ap.add_argument("--live", action="store_true", help="also re-fetch/re-extract sources and recheck citations")
    ap.add_argument("--ids", nargs="*", default=None, help="restrict to these report ids")
    args = ap.parse_args()

    listing_by_id = {}
    session = None
    if args.live:
        listing_by_id = {e.id: e for e in fetch.load_listing(config.LISTING_PATH)}
        session = fetch.make_session()

    all_fails: list[str] = []
    checked = 0
    for path in sorted(config.PROCESSED_DIR.glob("*/report.json")):
        report_id = path.parent.name
        if args.ids and report_id not in args.ids:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for finding in data.get("findings", []):
            if finding.get("amount_usd") is None:
                continue
            checked += 1
            fails = check_offline(report_id, finding)
            if not fails and args.live:
                fails = check_live(report_id, finding, listing_by_id, session)
            for f in fails:
                logger.error("FAIL  %s", f)
            all_fails.extend(fails)

    logger.info("\nchecked %d cited finding(s); %d failure(s)%s", checked, len(all_fails), "" if args.live else " (offline only — re-run with --live for the source-page recheck)")
    return 1 if all_fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
