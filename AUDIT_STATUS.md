# AUDIT-FOCUSED CORPUS STATUS

> **Counts as of 2026-06-08.** Source of truth is `docs/data/meta.json` (regenerated
> by `python -m pipeline.build`). This file is a human-readable summary — if it
> disagrees with `meta.json`, `meta.json` wins.

## ⚠️ READ THIS BEFORE ADDING ANY RECORD — no fabricated documents, ever

The corpus's entire value is that **every record is a real document at a real,
verified government URL** (see CLAUDE.md "Data is the product"). On 2026-06-07 a
prior session, trying to "fill the gaps" listed in an older version of this file,
**fabricated ~70 fake records** — invented docket numbers, guessed PDF URLs, and
`fetch=false` so the fetcher would never test them. They shipped to the live site.
All 70 were removed on 2026-06-08 (see ISSUES.md). **Do not repeat this.**

Rules for adding a record (enforced by tests + `pipeline.verify_sources`):

1. **Never invent a docket, accession, document number, or URL.** If you can't find
   the real one, the record does not get added. A gap is honest; a fake is poison.
2. **Prefer `fetch=true`.** A machine-fetched PDF (page_count>0) is self-proving.
   `fetch=false` is ONLY for genuinely WAF-walled sources whose URL you captured in
   a real browser (Chrome MCP) — and the URL must resolve to the *correct* document.
3. **A `200` is not proof.** A guessed URL can resolve to the *wrong* real document
   (this happened: a guessed FL order number returned a real PDF of a different
   docket). Verify the page-1 caption matches the claimed company/docket/date.
4. **Run `python -m pipeline.verify_sources` before committing** new seeds — it
   flags DEAD (404) and NON_PDF (resolves-but-not-a-pdf) URLs. CHECK/WALLED entries
   need a human/browser spot-check.
5. The offline test `test_committed_seeds_have_no_fabrication_markers` blocks any
   seed with a `placeholder` URL or a future `captured_at`.

## Current corpus: 290 structured records (as of 2026-06-08)

| Collection (UI tab)            | Count | Notes |
|--------------------------------|-------|-------|
| FERC Audits (`ferc_audit`)     | 120   | Form 1/2/6, every available year; traced to `data/listing.json` |
| Prudence Reviews (`prudence_review`) | 26 | FERC eLibrary orders + CA ERRA + WA/IN/WI/GA/VA/IL fuel & construction prudence (8 jurisdictions) |
| State PUC Audits (`state_audit`)     | 35 | 13 jurisdictions: PA MI CT MO MS TN UT NY NJ CA OH MD + **IL** (9 with parsed findings) |
| State Rate Cases (`state_rate_case`) | 109 | Reference metadata across ~37 jurisdictions (+VA biennial, +MN ALJ) |

**State PUC Audits — 33 across 12 jurisdictions, 8 with parsed findings (~122 recommendations):**
- **PA (8, parsed):** Bureau of Audits M&O audits — PPL, PGW, FirstEnergy, PECO, NFG, Duquesne, UGI, Columbia Gas (Exhibit I-2 → findings).
- **NJ (4):** BPU affiliate + management audits (Overland/Liberty) — PSE&G, JCP&L, ACE, NJNG (326–868 pp).
- **NY (3):** DPS/PSC comprehensive M&O audit orders (NYSEG/RG&E, Central Hudson) + Central Hudson billing investigation.
- **CA (2):** CPUC Utility Audits Branch Balancing-Account performance audits (SCE, SoCalGas).
- **OH (4):** PUCO third-party audits (Daymark Rider DMR, Blue Ridge Browns-Stadium) + FirstEnergy 20-1502 — `fetch=false`, F5-WAF-blocked, verified via Wayback.
- **MD (1):** PSC BGE gas-system safety investigation order. **MI (4):** Liberty distribution audits. **CT/MO/MS/TN/UT (7).**

**Patterns of noncompliance (State PUC Audits tab): 13 themes** mined from the parsed M&O-audit recommendations (workforce/training, internal controls, customer service & billing, inventory/fleet, emergency preparedness, cybersecurity & physical security, IT, reliability/vegetation, affiliate transactions, dividends, gas safety, etc.). See `pipeline/patterns.py` THEME_RULES; the matcher scans recommendation text for state audits (their finding titles are generic functional areas).

Keep growing **only with real, verified audits** (run `python -m pipeline.verify_sources`). See BACKLOG.md for per-state recipes and the genuinely-walled states still needing browser-capture.

## Where the real audit gaps are (verified-source targets, NOT placeholders)

The honest version of the old "TIER 1 gaps" list. Each needs a *real docket*,
found by searching the state portal — never a guessed number:

- **PA Bureau of Audits** — already the gold standard (3 parsed M&O audits with
  findings). PA publishes many more management & operations audits; the cleanest
  expansion is more of these (real `puc.pa.gov/pcdocs/{id}.pdf`).
- **NY DPS** — focused operations / management audits under PSL §66; real orders at
  `documents.dps.ny.gov` (DMM) need guid harvesting + caption verification.
- **MI MPSC** — the 4 Liberty Consulting distribution audits are real but
  Cloudflare-blocks scripted fetch; browser-capture is the unblock (URLs verified
  live, return real PDFs).
- **Genuinely walled states** (need Chrome-MCP browser-capture, per BACKLOG):
  OK, MA, NH, WY, HI, VT, ME, AL, NM, NC, IA.

## Rationale

Audit findings (compliance issues, recommended actions, cost impacts) are the
project's core value; rate cases are kept as lower-priority reference context in
their own tab. Both tabs are wanted — but every record in either must be real.
