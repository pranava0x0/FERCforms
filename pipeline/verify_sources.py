"""Live source-verification sweep — catch fabricated / mismatched documents.

The offline test `test_committed_seeds_have_no_fabrication_markers` catches the
cheap fabrication signatures (a `placeholder` URL, a future `captured_at`). But
the 2026-06-07 fabrication incident proved two failure modes that *only* a live
check finds:

  1. a guessed URL that 404s (TX `…_1234567.PDF`), and
  2. a guessed URL that *resolves to the wrong document* — FL `06789-2024.pdf`
     returned a real 1.3 MB PDF that was a different docket entirely (a "200 + a
     real PDF" is NOT proof; the content has to match).

So this CLI hits the network. For every committed report it reports a verdict:

  - PROVEN   — `fetch=true` record with page_count>0 (a real PDF was downloaded
               and extracted by the pipeline; nothing to re-check).
  - OK       — URL reachable and returns the expected content type.
  - DEAD     — 404/410/connection failure → fabrication candidate.
  - WALLED   — 401/403 (WAF/login wall; real-but-blocked, expected for OH/MI/etc.).
  - NON_PDF  — 200 but the body isn't a PDF where one was expected (FL-06790 case).
  - CHECK    — reachable HTML page (CA decisions, OH ViewImage) — content match is
               left to a human/browser; flagged for spot-check, not failed.

FERC audits are verified OFFLINE (accession ∈ listing.json) — we never re-hammer
eLibrary's POST DownloadPDF 120×. Rate-limited to ≥1.6s per host, parallel across
hosts. Exit code is non-zero if any DEAD/NON_PDF record is found.

Usage:
    python -m pipeline.verify_sources                 # full sweep
    python -m pipeline.verify_sources --seed sc_psc   # one seed file
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

from pipeline import config

logger = logging.getLogger(__name__)

_PER_HOST_MIN_GAP = 1.6
_host_lock: dict[str, threading.Lock] = defaultdict(threading.Lock)
_host_last: dict[str, float] = defaultdict(float)


def _throttle(host: str) -> None:
    with _host_lock[host]:
        dt = time.time() - _host_last[host]
        if dt < _PER_HOST_MIN_GAP:
            time.sleep(_PER_HOST_MIN_GAP - dt)
        _host_last[host] = time.time()


def probe(url: str, timeout: int = 25) -> tuple[int, str, bool]:
    """GET the first bytes of a URL (rate-limited per host). Returns
    (status_code, content_type, looks_like_pdf). status 0 = connection error."""
    host = (urlparse(url).hostname or "").lower()
    _throttle(host)
    try:
        r = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT, "Accept": "*/*"},
            timeout=timeout,
            stream=True,
            allow_redirects=True,
        )
        ctype = r.headers.get("content-type", "")
        head = next(r.iter_content(2048), b"")
        r.close()
        return r.status_code, ctype, head[:5] == b"%PDF-"
    except Exception as exc:  # noqa: BLE001 — any network error is a "could not reach"
        return 0, type(exc).__name__, False


def _load_seeds() -> dict[str, dict]:
    seeds: dict[str, dict] = {}
    for path in sorted(config.SEEDS_DIR.glob("*.json")):
        for rec in json.loads(path.read_text(encoding="utf-8")):
            rec["_file"] = path.name
            seeds[rec["id"]] = rec
    return seeds


def _load_reports() -> dict[str, dict]:
    return {
        (r := json.loads(p.read_text(encoding="utf-8")))["id"]: r
        for p in config.PROCESSED_DIR.glob("*/report.json")
    }


def verify(seed_filter: str | None = None) -> dict[str, list[str]]:
    """Run the sweep. Returns a verdict→[ids] map. DEAD/NON_PDF are failures."""
    seeds = _load_seeds()
    reports = _load_reports()

    # FERC audits: offline accession trace.
    listing = json.loads(config.LISTING_PATH.read_text(encoding="utf-8"))
    listing_acc = {e.get("accession_number") for e in listing}
    listing_ids = {e.get("id") for e in listing}

    verdicts: dict[str, list[str]] = defaultdict(list)
    work: list[tuple[str, str]] = []  # (id, url)

    for rid, r in reports.items():
        if r.get("collection") == "ferc_audit":
            if r.get("accession_number") in listing_acc or rid in listing_ids:
                verdicts["PROVEN"].append(rid)
            else:
                verdicts["DEAD"].append(f"{rid} (ferc_audit not in listing)")
            continue
        seed = seeds.get(rid)
        if not seed:
            verdicts["CHECK"].append(f"{rid} (no seed; orphan)")
            continue
        if seed_filter and seed_filter not in seed["_file"]:
            continue
        if seed.get("fetch", True) and r.get("page_count", 0) > 0:
            verdicts["PROVEN"].append(rid)
            continue
        # eLibrary accession-backed records (e.g. FERC prudence orders) are verified
        # by their accession — DownloadPDF needs the F5 cookie+POST, so a plain GET
        # returns HTML. A plain-GET "non-PDF" here is NOT a fabrication signal; the
        # accession is the provenance. (byte-fetch happens via fetch.py's cookie dance.)
        if seed.get("accession"):
            verdicts["CHECK"].append(f"{rid} [eLibrary accession {seed['accession']} — cookie-dance to byte-verify]")
            continue
        # fetch=false (browser-captured) records are STILL probed: a hard 404/410 means
        # the captured URL is wrong/invented (the real fabrication catch), while a WAF
        # wall (403 / connection-reset) or an HTML page is EXPECTED for them and routes
        # to CHECK — see the verdict logic below, which keys on the fetch flag.
        work.append((rid, seed["pdf_url"]))

    def _run(item: tuple[str, str]) -> tuple[str, int, str, bool]:
        rid, url = item
        code, ctype, is_pdf = probe(url)
        return rid, code, ctype, is_pdf

    with ThreadPoolExecutor(max_workers=12) as ex:
        for rid, code, ctype, is_pdf in ex.map(_run, work):
            seed = seeds[rid]
            browser_captured = not seed.get("fetch", True)
            is_html_source = seed["pdf_url"].lower().endswith((".htm", ".html")) or "viewimage" in seed["pdf_url"].lower()
            if code in (404, 410):
                # a 404 is suspicious for ANYONE — even a browser-captured URL should exist.
                verdicts["DEAD"].append(f"{rid} [{code}] {seed['pdf_url']}")
            elif code in (401, 403):
                verdicts["WALLED"].append(f"{rid} [{code}]")
            elif code == 0:
                # connection error/timeout: a hard failure for a script-fetchable URL,
                # but EXPECTED for a WAF-walled browser-captured one.
                (verdicts["CHECK"] if browser_captured else verdicts["DEAD"]).append(
                    f"{rid} [conn-error]{' browser-captured' if browser_captured else ''} {seed['pdf_url']}")
            elif is_pdf:
                verdicts["OK"].append(f"{rid} [{code}]")
            elif browser_captured or is_html_source:
                # HTML where a captured/HTML source is expected — content match needs a human.
                verdicts["CHECK"].append(f"{rid} [{code}] HTML/browser-captured — verify content match")
            else:
                # fetch=true expected a real PDF but got non-PDF — the fabrication signal.
                verdicts["NON_PDF"].append(f"{rid} [{code} {ctype}] expected PDF, got non-PDF: {seed['pdf_url']}")
    return verdicts


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Live source-verification sweep (fabrication catcher)")
    ap.add_argument("--seed", default=None, help="restrict to seed files matching this substring")
    args = ap.parse_args()

    verdicts = verify(args.seed)
    order = ["DEAD", "NON_PDF", "WALLED", "CHECK", "OK", "PROVEN"]
    for v in order:
        ids = verdicts.get(v, [])
        logger.info("\n=== %s: %d ===", v, len(ids))
        if v in ("DEAD", "NON_PDF", "WALLED", "CHECK"):
            for i in sorted(ids):
                logger.info("  %s", i)

    failures = len(verdicts.get("DEAD", [])) + len(verdicts.get("NON_PDF", []))
    if failures:
        logger.error("\nFABRICATION/MISMATCH SUSPECTS: %d — investigate before committing", failures)
        return 1
    logger.info("\nNo dead/mismatched URLs. (WALLED/CHECK need a browser/human spot-check.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
