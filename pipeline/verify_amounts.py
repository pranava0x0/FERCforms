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

from pipeline import amounts, config, fetch
from pipeline.amounts import _normalize

logger = logging.getLogger(__name__)


def _finding_own_fields(finding: dict) -> list[str]:
    """Every field a quote could legitimately have come from, kept SEPARATE (never
    joined) — joining summary+recommendations with a space would let a quote that
    spans the artificial join boundary (never actually contiguous in either field)
    falsely pass a substring check against neither field individually."""
    return [finding.get("summary") or ""] + [r.get("text") or "" for r in finding.get("recommendations", [])]


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

    quote_norm = _normalize(quote)
    if not any(quote_norm in _normalize(field) for field in _finding_own_fields(finding)):
        fails.append(f"{report_id} finding {idx}: amount_usd_quote is not a substring of the finding's own summary or any single recommendation")

    # Re-derive via the SAME selection logic amounts.find_primary_dollar_mention used
    # to produce amount_usd in the first place (skips a range's low bound, applies
    # the word-boundary-safe multiplier) — a bare DOLLAR_RE.search would pick the
    # WRONG figure whenever the quote is a range ("...$5 to $10 million...") and
    # falsely flag every correctly-cited range finding as inconsistent.
    reparsed_hit = amounts.find_dollar_mention(quote)
    if reparsed_hit is None:
        fails.append(f"{report_id} finding {idx}: amount_usd_quote contains no dollar figure at all")
    elif abs(reparsed_hit.amount_usd - amount) > 0.01:
        fails.append(
            f"{report_id} finding {idx}: amount_usd={amount} does not match re-parsed {reparsed_hit.amount_usd} from quote"
        )
    return fails


def check_live_finding(report_id: str, finding: dict, text) -> list[str]:
    """The per-finding page-text recheck, given an already-fetched/extracted
    ReportText (see fetch_and_extract) — no network/IO per call."""
    idx = finding.get("index")
    page_num = finding["amount_usd_page"]
    page = next((p for p in text.pages if p.page == page_num), None)
    if page is None:
        return [f"{report_id} finding {idx}: cited page {page_num} does not exist in the re-extracted PDF ({text.page_count} pages)"]

    page_norm = _normalize(page.text)
    quote_norm = _normalize(finding["amount_usd_quote"])
    if quote_norm in page_norm:
        return []
    # Fall back to the SAME figure amount_usd was derived from (range-aware — see
    # check_offline), not just any dollar-looking substring in the quote.
    hit = amounts.find_dollar_mention(finding["amount_usd_quote"])
    if hit and _normalize(hit.raw) in page_norm:
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
        cited = [f for f in data.get("findings", []) if f.get("amount_usd") is not None]
        if not cited:
            continue

        offline_results = {id(f): check_offline(report_id, f) for f in cited}

        # Fetch/extract the source PDF ONCE per report (not once per finding) — every
        # cited finding in the same report shares the same source PDF.
        text = None
        report_fail: list[str] = []
        if args.live and any(not fails for fails in offline_results.values()):
            if report_id not in listing_by_id:
                report_fail = [f"{report_id}: not a FERC audit (no listing.json entry) — cannot live-recheck"]
            else:
                try:
                    text = amounts.fetch_and_extract(listing_by_id[report_id], session)
                except Exception as exc:  # noqa: BLE001 — a fetch/extract failure is a check failure, not a crash
                    report_fail = [f"{report_id}: could not fetch/extract source PDF to recheck: {exc}"]

        for finding in cited:
            checked += 1
            fails = offline_results[id(finding)]
            if not fails and args.live:
                fails = report_fail or check_live_finding(report_id, finding, text)
            for f in fails:
                logger.error("FAIL  %s", f)
            all_fails.extend(fails)

    logger.info("\nchecked %d cited finding(s); %d failure(s)%s", checked, len(all_fails), "" if args.live else " (offline only — re-run with --live for the source-page recheck)")
    return 1 if all_fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
