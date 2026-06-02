# Data sources & scraping guide

How every document in the corpus is acquired, per regulator. This is the single reference for
re-running or extending the dataset; the live access-status log lives in [ISSUES.md](../ISSUES.md)
and the per-source backlog in [BACKLOG.md](../BACKLOG.md). To actually run a refresh, see the
**refresh-ferc-data** skill (`.claude/skills/refresh-ferc-data/`).

---

## General principles (apply to every source)

These are non-negotiable and enforced in code where possible:

- **Official government sources only.** Every PDF and landing URL must be an official `.gov` host
  (or the legacy `*.state.xx.us` pattern). Enforced by `pipeline/sources.is_official_gov` /
  `_assert_official_gov` — `load_seed` raises on any non-gov URL. Never mirror, aggregator, or
  third-party copy (DocumentCloud, scribd, SEC EDGAR, news sites).
- **Verify before you seed.** Doc IDs are opaque on most dockets. **Fetch the PDF and read page 1–2
  (skip "Filing Receipt" / "Notice of Filing" cover sheets) before labelling** company / date /
  doc_type. This repeatedly caught mislabels — a TX ERCOT presentation, an SC DSM update, a PGW
  implementation-plan-vs-audit — that the docket summary alone would have gotten wrong.
- **Metadata-only by default; parse only what's clean.** Legal orders, testimony, and settlements
  are captured *with their source* (`structured=False`, "Listed for reference") — never paraphrased
  or LLM-judged. Only documents with a clean, enumerable structure are parsed into verbatim findings
  (today: FERC audit executive summaries, and PA M&O audits' Exhibit I-2). Flip `parse=true`
  per-seed once a format's parser is proven and snapshot-gated.
- **Rate-limit & cache.** ≥1.5–2 s between requests to one host (`config.REQUEST_DELAY_SECONDS`),
  informative `User-Agent`, 429/transient → exponential backoff. Raw PDFs cache to `data/raw/`
  (gitignored); re-runs skip cached files. A service that persistently blocks → back off, log, skip
  — never hammer.
- **Provenance on every record.** `source_note` (human-readable), `source_page_url`, `pdf_url`,
  `captured_at`; `archived_via` when sourced from a Wayback snapshot.

### The three seed flags (`SourceSeed`)

| flag | default | meaning |
|------|---------|---------|
| `parse` | `false` | `true` ⇒ run the findings parser (PA M&O Exhibit I-2 today); falls back to metadata-only on any miss. |
| `fetch` | `true`  | `false` ⇒ **don't** machine-fetch — the URL was captured out-of-band (a WAF-blocked source opened in a browser); write metadata-only straight from the seed (page_count 0). |
| `accession` | `null` | set ⇒ fetch via the FERC eLibrary F5 cookie dance instead of a plain GET. |

---

## FERC (the core corpus)

- **`/audits` listing** (`https://www.ferc.gov/audits`) — Cloudflare-challenged; 403s to scripts.
  The listing is **browser-captured** into `data/listing.json`. The live page lists **2019+** only.
- **FY2014–2018 backfill** — recovered from a saved Internet Archive **Wayback** snapshot of `/audits`;
  each older report's eLibrary accession is resolved via the eLibrary **Docket Search** API
  (`pipeline/backfill.py`, **ferc.gov-origin only**; records carry `archived_via`).
- **eLibrary PDFs** — `pipeline/fetch.py` runs the **F5 WAF cookie dance**: GET the `filelist`
  endpoint to seed the session cookie, then POST `DownloadPDF`. Accession-keyed (`YYYYMMDD-####`).
- **eLibrary discovery (prudence reviews)** — the JSON API **is** scriptable (unlike the `www.ferc.gov`
  HTML): `POST /eLibraryWebAPI/api/Search/AdvancedSearch` with `searchFullText:true`,
  `categories:["Issuance"]` returns JSON. Used to hand-curate the prudence seed; PDFs still need the
  cookie dance. (Automating prudence discovery is a backlog item — a single month of "imprudent"
  returns ~2,900 mostly-incidental hits.)
- Parsing: FERC audit executive summaries → findings → recommendations (`pipeline/structure.py`,
  snapshot-gated). The prudence orders are metadata-only.

## State PUC / PSC / SCC sources

Each commission's docket system is different. Patterns below are all confirmed by live capture.

### PA — Pennsylvania PUC (Bureau of Audits) · `parse=true` for M&O
- **PDFs:** plain GET `https://www.puc.pa.gov/pcdocs/{id}.pdf` (the pipeline `requests` UA works).
- **Parsed:** Management & Operations audits carry an **Exhibit I-2 "Summary of Recommendations"** —
  chapter headers (functional areas) + numbered verbatim recommendations, "None" for clean chapters.
  Parsed by `pipeline/state_structure.py` (Finding per chapter, Recommendation per row).
  **Use PyMuPDF text** (`extract.pymupdf_pages`) — pdfplumber interleaves the rec label/columns into
  the wrapped text; fitz linearizes the table cleanly.
- **Metadata-only:** focused audits (messy multi-column tables) and the Management Efficiency
  Investigation (different structure) stay `parse=false` until their parsers exist (backlog).

### MI — Michigan MPSC (Liberty Consulting distribution audits)
- **PDFs:** `michigan.gov/.../3rdparty/...` consultant reports + the reports index. Plain GET via
  `requests`; `WebFetch` 403s on `michigan.gov` (tool-UA quirk, not a site block — use `curl`/the
  pipeline). Metadata-only.

### VA — Virginia SCC · `dis`-style DocketSearch
- **PDFs (direct):** `https://www.scc.virginia.gov/docketsearch/DOCS/{code}!.PDF`. **Use the `www.`
  host** — the bare `scc.virginia.gov` 307-redirects to it (seed `www.` so the pipeline fetch doesn't
  bounce). `{code}` is opaque (e.g. `89g601`).
- **Search:** the DocketSearch *search* is a **hash-routed SPA — not curl-resolvable**. Resolve codes
  by browsing in a browser (a companion fuel-factor order was left un-added for this reason).
- Metadata-only (biennial reviews, RAC riders, net metering, CPCN orders).

### TX — Texas PUCT (Interchange) · scriptable search
- **Search (scriptable):** `GET interchange.puc.texas.gov/search/filings/?ControlNumber={N}` (follow
  the 302, keep cookies) → an HTML table of items; each row's
  `/search/documents/?controlNumber={N}&itemNumber={M}` page exposes the real PDF link.
- **PDFs:** `interchange.puc.texas.gov/Documents/{control}_{item}_{docid}.PDF` (pipeline UA fetches
  fine; `WebFetch` 403s — tool quirk). `.texas.gov` ends in `.gov` → passes the guard.
- **Gotchas:** every filing's **page 1 is a "Filing Receipt" cover** — read page 2+. Item-1
  "Application" filings are often **multi-part** (a dozen PDFs); some scanned → OCR. Metadata-only.

### IL — Illinois ICC e-Docket · server-rendered (easiest for metadata)
- **Docket → docs:** `…/docket/P{YYYY}-{NNNN}/documents` lists filings; each `…/documents/{docId}`
  detail page exposes **authoritative `Date Filed` + `Type`** (no page-1 read needed) and per-file
  links `…/documents/{docId}/files/{fileId}.pdf`.
- **Gotchas:** a filing can bundle many files — the *first* may be a "Notice of Filing" cover (the
  testimony was the 2nd file). The `www.` host serves PDFs to browser UAs but **307s the pipeline UA
  to the non-www host**, which briefly throttled a request burst with 404s then cleared — **back off
  and re-run ingest**, don't hammer. Metadata-only (parsing the orders is a backlog idea).

### SC — South Carolina PSC (DMS) · GET search
- **Search (scriptable):** `GET dms.psc.sc.gov/Web/Dockets/Search?Summary=fuel%20cost&NumberType=E`
  (or `?OrganizationName=…`) → `/Web/Dockets/Detail/{id}` lists filings with dates +
  `/Attachments/Matter/{guid}` PDFs (pipeline UA fetches directly, no cookies).
- **Gotchas:** the formal final order lives in a separate, unfiltered `/Web/Orders` index (couldn't
  isolate a single docket's order quickly — settlements + joint proposed orders stand as the on-theme
  disposition). The annual fuel docket exists for all 3 electric utilities (DESC `2-E`, Duke Carolinas
  `3-E`, Duke Progress `1-E`). Metadata-only.

## WAF-blocked sources — browser-capture + `fetch=false`

Scripts are rejected, so the doc URL is located in a **real browser (Chrome MCP)** and the stable
`.gov` URL seeded with `fetch=false` (metadata-only, no scripted fetch — page_count 0). **Never solve
interactive CAPTCHAs** — only non-interactive JS challenges that the browser passes on its own.

### OH — Ohio PUCO DIS (F5 ASM) · done
- Scripts get a 245-byte "Request Rejected / support ID" page. URL chain in the browser:
  `CaseRecord.aspx?CaseNo={case}` → `DocumentRecord.aspx?DocID={guid}` → `ViewImage.aspx?CMID={cmid}`
  (the PDF). `dis.puc.state.oh.us` matches the `*.state.xx.us` guard. Seeded `fetch=false`.
- OH has the **richest consultant management/financial audits** — DIS Full-Text / "By Industry and
  Purpose" search can surface them (each a browser-capture record; a future parser target if the F5
  fetch is ever cracked).

### NC — North Carolina NCUC `starw1.ncuc.gov` (Cloudflare) · remaining
- The Cloudflare "Just a moment" JS challenge **auto-resolves in the Chrome-MCP browser** (no
  interactive CAPTCHA). The docket search (`/NCUC/page/Dockets/portal.aspx`) posts back without inline
  results — driving that search to a docket → order → PDF URL is the remaining step. On-theme target:
  fuel-cost riders (Duke Energy Progress `E-2`, Duke Energy Carolinas `E-7`). Seed `fetch=false`.
