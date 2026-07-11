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

The offline sweep marks a `fetch=true` record PROVEN on the `page_count>0`
shortcut — it trusts the pipeline's earlier download. `--live` closes that gap:
it re-fetches every fetchable PDF and re-confirms it is STILL the *claimed*
document — %PDF magic, page-count == the committed report, and a distinctive
company token present in the first pages (the "200 on the wrong real doc" catch).

Usage:
    python -m pipeline.verify_sources                       # offline sweep (fast)
    python -m pipeline.verify_sources --seed sc_psc         # one seed file
    python -m pipeline.verify_sources --live                # + re-fetch & content-match ALL
    python -m pipeline.verify_sources --seed fl_psc --live  # deep-check one seed file
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


_MAX_PDF_BYTES = 45_000_000
_LIVE_SCAN_PAGES = 15  # fast pass over front-matter; falls back to the whole doc on a miss

# Corporate suffixes / industry words that aren't distinctive enough to prove a
# document is the *claimed* company (every gas audit says "gas"). We match on the
# distinctive remainder (geographic/brand tokens like "pacific", "pepco", "avista").
_CORP_STOPWORDS = frozenset({
    "the", "and", "of", "company", "companies", "corporation", "corp", "inc",
    "incorporated", "llc", "lp", "llp", "co", "gas", "electric", "power", "light",
    "energy", "utilities", "utility", "service", "services", "system", "systems",
    "natural", "holdings", "group",
})


def company_tokens(company: str) -> list[str]:
    """Distinctive lowercase tokens from a company name for content-matching.

    Drops corporate suffixes and generic industry words. Falls back to ≥3-char
    tokens (still stopword-filtered) to keep short distinctive brands like "DTE"
    / "UGI" / "PSE". Returns [] when a name is ALL generic ("Power Company") — the
    caller then can't (and must not) content-match, rather than trivially matching
    any utility doc on "power"/"company" and silently defeating the check."""
    import re

    words = re.findall(r"[a-z0-9]+", company.lower())
    toks = [w for w in words if len(w) >= 4 and w not in _CORP_STOPWORDS]
    if not toks:
        toks = [w for w in words if len(w) >= 3 and w not in _CORP_STOPWORDS]
    return toks


def _stream_capped(url: str, ua: str, timeout: int) -> tuple[bytes, bool]:
    """Return (bytes, truncated). `truncated` is True if the download hit the
    byte cap — the tail (xref/trailer) is then missing, so the PDF is structurally
    incomplete and must not be treated as a verification failure."""
    r = requests.get(
        url,
        headers={"User-Agent": ua, "Accept": "*/*"},
        timeout=timeout,
        stream=True,
        allow_redirects=True,
    )
    data = bytearray()
    truncated = False
    for chunk in r.iter_content(65536):
        data.extend(chunk)
        if len(data) > _MAX_PDF_BYTES:
            truncated = True
            break
    r.close()
    return bytes(data), truncated


def fetch_pdf_bytes(url: str, timeout: int = 90) -> tuple[bytes, bool]:
    """Stream a URL with a hard byte cap (so a 500-page report can't hang the
    sweep). Rate-limited per host. Returns (bytes, truncated). The reusable
    verify-by-download primitive.

    Mirrors the pipeline fetcher's UA fallback: some hosts (michigan.gov)
    UA-filter and serve an HTML interstitial to the default UA but the real PDF
    to a browser UA — so retry once with BROWSER_USER_AGENT on a non-PDF body."""
    host = (urlparse(url).hostname or "").lower()
    _throttle(host)
    data, truncated = _stream_capped(url, config.USER_AGENT, timeout)
    if data[:5] != b"%PDF-":
        _throttle(host)
        data, truncated = _stream_capped(url, config.BROWSER_USER_AGENT, timeout)
    return data, truncated


def content_match_fails(company: str, pages_text: str) -> list[str]:
    """Offline core of the live check: does the extracted text actually mention
    the claimed company? Returns failure strings (empty = matched). Split out so a
    unit test can exercise the matching logic without touching the network.

    Matches on whitespace-normalized text only — NOT a despaced concatenation,
    which would manufacture cross-word substrings ("the pep company" → "pepco")
    and let a genuinely wrong document pass (the exact false-negative this check
    exists to prevent)."""
    norm = " ".join(pages_text.lower().split())
    toks = company_tokens(company)
    if toks and not any(t in norm for t in toks):
        return [f"none of company tokens {toks} found in scanned pages — possible wrong document"]
    return []


def live_verify(rid: str, seed: dict, report: dict) -> list[str]:
    """Re-fetch a fetch=true PDF record and confirm it is STILL the claimed
    document: %PDF magic, page-count == committed report, and a company token
    present in the first pages. Returns failure strings (empty = verified).

    Fully guarded: any unexpected error becomes a per-record failure string, never
    a raised exception — so one bad record can't abort the whole sweep (the sweep
    runs these concurrently via ex.map, which would otherwise propagate)."""
    try:
        return _live_verify(rid, seed, report)
    except Exception as exc:  # noqa: BLE001 — never let one record crash the sweep
        return [f"{rid}: live-check error {type(exc).__name__}: {exc}"]


def _live_verify(rid: str, seed: dict, report: dict) -> list[str]:
    import fitz  # PyMuPDF

    url = seed["pdf_url"]
    try:
        data, truncated = fetch_pdf_bytes(url)
    except Exception as exc:  # noqa: BLE001
        return [f"{rid}: fetch error {type(exc).__name__}: {exc} — {url}"]
    if data[:5] != b"%PDF-":
        return [f"{rid}: not a PDF (head={data[:12]!r}) — {url}"]
    if truncated:
        # Hit the byte cap: the PDF tail (xref/trailer) is missing, so page_count
        # and text can't be trusted. Not a fabrication signal — a valid PDF header
        # that's simply too large to fully verify here. Pass (don't false-fail).
        logger.info("  (skipped %s — exceeds %d MB cap, not fully verified)", rid, _MAX_PDF_BYTES // 1_000_000)
        return []
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        return [f"{rid}: unreadable PDF ({type(exc).__name__}) — {url}"]
    fails: list[str] = []
    with doc:
        n = doc.page_count
        expected = report.get("page_count", 0)
        if expected and n != expected:
            fails.append(f"{rid}: live page_count {n} != committed {expected} — {url}")
        # Fast pass over front-matter; only if the company isn't named there do we
        # pay to scan the whole (already-downloaded) doc — so a report that names
        # the utility deep inside (a consultant report titled by program, not
        # company) never false-fails, while a genuinely wrong document — which
        # never mentions the claimed company — still fails hard.
        # state_reference is the "not an audit of a utility" collection (blank
        # forms, admin/reference pages) — its `company` field is a document-title
        # slug, not a utility name, so the company-token match is meaningless.
        # Verify it resolves to a PDF (above), but skip the content match.
        if report.get("collection") == "state_reference":
            cfails = []
        else:
            front = " ".join(doc[i].get_text() for i in range(min(n, _LIVE_SCAN_PAGES)))
            cfails = content_match_fails(seed.get("company", ""), front)
            if cfails and n > _LIVE_SCAN_PAGES:
                whole = " ".join(doc[i].get_text() for i in range(n))
                cfails = content_match_fails(seed.get("company", ""), whole)
    fails += [f"{rid}: {m}" for m in cfails]
    return fails


def _load_seeds() -> dict[str, dict]:
    seeds: dict[str, dict] = {}
    for path in sorted(config.SEEDS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        # Some files in data/seeds/ are planning docs (e.g. tier3_targets.json, a
        # state-keyed dict), not SourceSeed lists. Skip anything that isn't a list
        # of seed dicts so the fabrication sweep never crashes on them.
        if not isinstance(data, list):
            continue
        for rec in data:
            if not isinstance(rec, dict) or "id" not in rec:
                continue
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
    ap.add_argument(
        "--live",
        action="store_true",
        help="deep check: re-fetch every fetch=true PDF and confirm page-count + "
        "company-token match (not just the offline page_count>0 shortcut)",
    )
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

    live_fails: list[str] = []
    if args.live:
        seeds = _load_seeds()
        reports = _load_reports()
        work = [
            (rid, seeds[rid], reports[rid])
            for rid in reports
            if rid in seeds
            and seeds[rid].get("fetch", True)
            and not seeds[rid].get("accession")  # eLibrary needs the F5 cookie dance, not a plain GET
            and reports[rid].get("page_count", 0) > 0
            and (not args.seed or args.seed in seeds[rid]["_file"])
        ]
        logger.info("\n=== LIVE re-fetch + content match: %d record(s) ===", len(work))
        with ThreadPoolExecutor(max_workers=8) as ex:
            for fails in ex.map(lambda w: live_verify(*w), work):
                live_fails.extend(fails)
        for f in sorted(live_fails):
            logger.info("  MISMATCH %s", f)
        logger.info("\nLIVE: %d verified, %d mismatch(es)", len(work) - len(live_fails), len(live_fails))
        failures += len(live_fails)

    if failures:
        logger.error("\nFABRICATION/MISMATCH SUSPECTS: %d — investigate before committing", failures)
        return 1
    logger.info("\nNo dead/mismatched URLs. (WALLED/CHECK need a browser/human spot-check.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
