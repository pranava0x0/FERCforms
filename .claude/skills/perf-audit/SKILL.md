---
name: perf-audit
description: Audit the FERC Audit Explorer's front-end performance for THIS project — page weight, request count, gzip transfer size, and preload/double-fetch checks against the static site in docs/. Use when the user says "run perf", "perf test", "check performance", "page weight", "payload size", "is the site too heavy", "audit requests", or similar. There is no automated perf suite — this skill IS the perf check. Encodes the exact measurement commands, the recorded baseline, and the known non-bugs so they aren't re-chased.
---

# Front-end performance audit — FERC Audit Explorer

The site is static vanilla HTML/CSS/JS in `docs/` reading baked `docs/data/*.json`. There is **no
pytest perf suite** — perf is a payload + request audit against the project's CLAUDE.md principles
("minimize page weight and request count", "benchmark against best-in-class", "only load libraries
used on the page"). This skill is the repeatable closed loop for it.

**Golden rule (this session's scar tissue): measure, don't assume. Fix only a *confirmed* regression.**
A static read of `index.html` can make a correct setup look broken (see the preload note below) — always
confirm in the browser before "fixing".

## 1. Request count + transfer (gzip) size

Compressed file sizes estimate transfer cost; actual wire size depends on negotiated compression and caching. Measure both:

```bash
cd "$(git rev-parse --show-toplevel)"
for f in docs/index.html docs/css/styles.css docs/js/app.js \
         docs/data/reports_index.json docs/data/findings_ferc_audit.json docs/data/patterns.json \
         docs/data/patterns_by_collection.json docs/data/meta.json; do
  raw=$(wc -c < "$f"); gz=$(gzip -c "$f" | wc -c)
  printf "%-32s raw=%9d  gzip=%9d\n" "$(basename "$f")" "$raw" "$gz"
done
```

Then inspect first-party and external requests separately. Google Analytics is present as of September 24; do not describe the site as third-party-free:

```bash
grep -nE "<link|<script|fetch\(|preload" docs/index.html
grep -nE "fetch\(" docs/js/app.js
```

## 2. Runtime check — double-fetches & preload reuse (browser)

Serve via the Preview MCP (`preview_start` name `ferc-site`, port 8766) or `python3 -m http.server 8766 -d docs`,
then in the page run Resource Timing — it records every real network fetch:

```js
(() => {
  const r = performance.getEntriesByType('resource');
  const rep = r.filter(x => x.name.includes('reports_index.json'));
  return { totalEntries: r.length, reportsIndexFetchCount: rep.length,
           reportsIndex: rep.map(x => ({initiator:x.initiatorType, transfer:x.transferSize})),
           names: r.map(x => x.name.split('/').pop()) };
})()
```

`reportsIndexFetchCount` **must be 1**. Two entries (`initiatorType` `link` *and* `fetch`) = the preload
is being discarded and re-downloaded — a real regression to fix.

## 3. Current baseline (2026-09-24)

| Metric | Value |
| --- | --- |
| Corpus | 444 records |
| Local Resource Timing before refresh | 11 entries, including Google Analytics and active-tab detail prefetch |
| First-party gzip estimate after refresh | About 91 KB before details; 258 KB with active FERC details |
| Index | About 25 KB gzip; fetched once |
| Full `reports.json` runtime fetches | Zero |
| Details | Per-collection file, idle-prefetched; not solely expansion-triggered |

Separate external analytics transfer from first-party estimates. Verify no duplicate index/detail
requests and no full-corpus download. Compare against a baseline with the same loaded collections.
Source measurements: `docs/stocktake-2026-09-24.json`; UAT summary: `uat.md`.

### Historical baseline (2026-06-02; superseded)

| Metric | Value |
| --- | --- |
| Total requests | **7** (favicon, css, app.js, 4 JSONs) — no third-party/font/framework |
| Wire payload | **≈208 KB gzip** (raw ≈1.34 MB), **167 records** |
| `reports.json` | 1.26 MB → **191 KB** gzip — dominant payload, `<link rel=preload>`'d, fetched **once** |
| `app.js` / `styles.css` | 29 KB→8.8 KB / 21 KB→5.2 KB gzip |

Flag a regression if: a new third-party/font request appears, total gzip jumps materially over baseline
without a data/feature reason, or `reportsIndexFetchCount > 1`.

## 4. Historical preload observation — verify current index behavior

The June `index.html` preloaded `data/reports.json` with `crossorigin="anonymous"`, while `app.js` fetches it
same-origin without CORS. On a static read this looks like a CORS mismatch that should double-fetch.
**It does not** — verified via Resource Timing (one fetch, `initiatorType: "link"`, reused by the
`fetch()`; no "preloaded but not used" warning). Current preload targets `reports_index.json`; re-check Resource Timing rather than assuming the old observation still holds. Leave the
`crossorigin` attribute alone unless Resource Timing actually shows two fetches.

## 5. Close the loop

After any UI/data change, re-run §1–§2 and compare to §3. If you fixed a real regression, re-measure to
prove it, then update the baseline table here and the Performance section of `uat.md` (keep them in sync).
