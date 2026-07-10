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
  an informative `User-Agent` that names the project + a contact URL but carries **no
  `python-requests`/library token** (some `.gov` IIS sites crude-filter that substring — see WV),
  429/transient → exponential backoff. Raw PDFs cache to `data/raw/`
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

### Access failure modes & how the fetcher handles them

State/territory portals fail in a handful of recurring ways. `pipeline/sources.fetch_doc`
(the plain-GET path) now classifies each so a run never wastes retries on an unfixable error,
never silently accepts junk, and always logs the *fix* — and every failure is still **best-effort**
(`process_seed` writes a metadata-only record on any miss, so one bad doc never aborts a run).

| Failure mode | Symptom | Fetcher behavior | Operator fix |
|---|---|---|---|
| **Throttling / connection reset** | `ConnectionError` / read timeout / curl `000` after a burst (seen on `puc.idaho.gov`, `apps.puc.state.or.us`, `apiproxy.utc.wa.gov`) | **exponential backoff + jitter** (`_backoff_seconds`, capped 90s) then retry, up to `MAX_RETRIES` | space out requests; re-run (idempotent). Don't hammer. |
| **Rate limit** | `HTTP 429` | same exponential backoff + retry | re-run later |
| **Broken / mismatched TLS** | `SSLError` (hostname mismatch) — AZ `images.edocket.azcc.gov`, MS InSite `psc.state.ms.us` | **fail fast, no retry** (a cert won't fix on retry); error names the fix | use a valid-cert host alias (AZ → `docket.images.azcc.gov`), else browser-capture + `fetch=false` |
| **WAF / login wall** | `HTTP 401/403` (OH PUCO F5, NC Cloudflare, IA `efs.iowa.gov`, NM PRCe360 `Login.aspx`) | **fail fast, no retry**; error says "open in a browser, seed `fetch=false`" | Chrome MCP capture + `fetch=false`, or a non-walled host |
| **Blank placeholder PDF** | `200` + `%PDF` magic but tiny (~5 KB), no real content — AZ `edocket.azcc.gov/docketpdf/` | kept, but **logged `WARNING: possible placeholder/cover page`** (`< _SUSPICIOUS_PDF_BYTES`) | page-1-verify; switch to the real-doc host/path |
| **eLibrary slow on huge decisions** | 90s read timeout on big ALJ orders | `_fetch_elibrary_once` is one-shot, 90s; metadata-only on miss | re-run when eLibrary is quiet (page counts backfill) |
| **UA-filtered IIS** | `404.19` to any UA containing `python-requests` (WV) | n/a — `config.USER_AGENT` carries **no** library token | — |

**Verify-before-seed still applies on top of all this:** a `200` + `%PDF` only means *a* PDF came back,
not the *right* one — read page 1 (locally with `fitz`; `WebFetch` saves the binary even when it can't
render it) before labelling `company` / `issued_date` / `doc_type`.

### Cross-portal techniques (learned in the 2026-06-02 multi-state expansion — GA/LA/MS/AR/MO/MN/WI/CO)

These generalize across the per-state recipes below. They're the difference between an hour and ten minutes per state.

- **Try clients in tiers; the failure tells you the access mode.** (1) pipeline `requests` UA (`config.USER_AGENT`); (2) `WebFetch` (browser-ish UA); (3) real browser (Chrome MCP). If the pipeline UA **403s** (AL `psc.alabama.gov`, IA `efs.iowa.gov`) the host is WAF/hotlink-walled → it needs **browser-capture + `fetch=false`** (OH/NC pattern). If WebFetch *also* 403s, only the browser works. A broken **TLS chain** (MS InSite `psc.state.ms.us`) blocks scripts *and* WebFetch *and* the browser — effectively unreachable from here.
- **`WebFetch` can't render a PDF, but it SAVES it.** For binary/scanned/odd-font PDFs WebFetch returns "can't extract" — but it writes the file to the transcript `tool-results/` dir. Extract page 1 locally with PyMuPDF (`fitz`) / pdfplumber to read the verbatim caption. This was the workhorse verify step (GA/LA/MS/MN). Fetch a batch, then one local `fitz` pass identifies them all.
- **VERIFY the case/company off page 1 (or the docket sheet) — search engines lie.** Caught this session: ER-2024-0261 = *Empire/Liberty*, **not** Ameren (search insisted Ameren; the Ameren case is ER-2024-0319); a résumé and a misc. exhibit mislabeled as IRP filings (GA); Arch Coal dated 2025 when it's 2015. The authoritative source is the **docket sheet** (MO `Case/Display`, CO `EFI.Show_Docket`, AR `docket_search_results`) or page 1 of the PDF — never the search snippet.
- **Font-mangled docket numbers ⇒ leave `docket` null.** Several portals (LA ViewFile, AR olsv2) have broken text-layer fonts that garble the docket digits (`U- \/ex/\/ma`) even though the caption reads fine. `docket` is optional — omit it and describe the proceeding precisely in `source_note` rather than guessing a number.
- **Harvest opaque doc IDs via Google, enumerate via the docket sheet.** Two ways to find a portal's stable PDF URLs: (a) `WebSearch site:<host>` — Google indexes the PDFs' first-page text, so titles are reliable (GA FACTS, CO); (b) the docket-sheet page lists filings (sometimes 2-level: docket → filing → document, as in CO). The download URL is then a stable `.gov` GET.
- **URL-encode opaque tokens in the seed `pdf_url`.** Base64-ish `fileId`s need `+`→`%2B`, `/`→`%2F`, `=`→`%3D` (LA ViewFile); the pipeline `requests` GET passes them through and the server decodes.
- **Cadence that worked:** one jurisdiction per checkpoint — find→verify→seed `data/seeds/<st>.json`→`pipeline.sources`→`pipeline.build`→`pytest`→commit (seed+baked together)→push. Add a `test_is_official_gov` assertion for each new host and a per-state recipe section below. Everything **inline + bounded** — no agents / deep-research / Workflow fan-outs (see [CLAUDE.md § AI / API cost optimization](../CLAUDE.md)).

---

## FERC (the core corpus)

- **`/audits` listing** (`https://www.ferc.gov/audits`) — Cloudflare-challenged; 403s to scripts.
  The listing is **browser-captured** into `data/listing.json`. The live page lists **2019+** only.
- **FY2014–2018 backfill** — recovered from a saved Internet Archive **Wayback** snapshot of `/audits`;
  each older report's eLibrary accession is resolved via the eLibrary **Docket Search** API
  (`pipeline/backfill.py`, **ferc.gov-origin only**; records carry `archived_via`).
- **eLibrary PDFs** — `pipeline/fetch.py` runs the **F5 WAF cookie dance**: GET the `filelist`
  endpoint to seed the session cookie, then POST `DownloadPDF`. Accession-keyed (`YYYYMMDD-####`).
- **NEW FERC audits since the last `/audits` snapshot (scriptable, no browser needed — verified 2026-06-19).**
  The live `/audits` page is Cloudflare-walled, but the eLibrary AdvancedSearch API enumerates audit
  issuances directly. Warm the F5 cookie (`fetch.make_session()` + `fetch._warm(s, <any-recent-acc>)`),
  then `POST /eLibraryWebAPI/api/Search/AdvancedSearch` with
  `{"searchText":"<DOCKET-PREFIX>","searchFullText":false,"categories":["Issuance"]}`. **Enumerate the
  audit docket series** `FA{YY}` (financial) and `PA{YY}` (non-financial), YY ≈ last ~6 FYs. A
  **completed** report's hit has `documentType:"Audit Summary"` and a description matching
  `issuing [Aa]udit [Rr]eport` (the `"…Commission is commencing/informing…"` hits are just audit
  *start* notices — no report yet). Keep hits with `issuedDate` newer than the latest in `listing.json`,
  dedupe by `acesssionNumber`, then append ListingEntry rows (id `YYYY-MM-DD_<co-slug>_<docket-lower>`,
  `pdf_download_url=…/api/File/DownloadPDF?accesssionNumber={acc}`) and run
  `fetch → classify → extract → structure → build`. **Gotcha that cost a revert (2026-06-19):** bare
  `pipeline.extract` + `pipeline.structure` re-process the WHOLE corpus — they re-extracted/re-parsed
  ~20 already-committed records and silently regressed some (PGW 11/32 → 1/70). After running them,
  `git checkout HEAD -- data/processed/` to drop all tracked modifications (the new untracked report
  dirs survive), then rebuild. (Note params `fromDate`/`toDate` are ignored; `sortBy:"date"` works but
  the `page` param doesn't — prefix-enumeration is the reliable path.) **Schema note:** the hits are in
  `data.searchHits[]`; the completed-report signal is a `description` matching `issuing [Aa]udit [Rr]eport`
  (the `documentType` is usually `General Correspondence`, NOT "Audit Summary" — don't filter on that);
  `issuedDate` is `MM/DD/YYYY`. **Re-checked 2026-06-22 (no new records):** newest issued audit report
  remains **FA24-3 (2026-05-07)** — every FY25/FY26 `FA*/PA*` hit is a *"commencing an audit"* start
  notice, not an issued report (FA26-1…5, PA26-5 etc. are audits in-progress with no report yet). FERC
  simply hasn't issued an audit report since 2026-05-07; the gap is real, not a scrape miss.
- **eLibrary discovery (prudence reviews)** — `POST /eLibraryWebAPI/api/Search/AdvancedSearch` returns
  JSON (scriptable, unlike the `www.ferc.gov` HTML). **Working recipe (2026-06-02):** the docket goes
  in **`searchText`** (NOT a dedicated docket field — `docketNumber`/`dockets` are silently ignored),
  with `{"searchFullText":false,"categories":["Issuance"]}`. Each hit gives `acesssionNumber` (sic —
  their typo), `issuedDate`, `description`, `docketNumbers`. Returns **10 hits/page** (`totalHits` shows
  the full count). **Caveat:** results are relevance-ranked full-text, so a clean single-issue docket
  (e.g. MAPP `ER13-607` → `20130228-3064`) resolves precisely, but a messy consolidated-complaint docket
  (the ROE cases `EL11-66`/`EL14-12` with dozens of bundled complaints) pulls in siblings — confirm the
  exact order by `description`+`issuedDate` (and page-1) before seeding. PDFs still need the F5 cookie
  dance (above). This cracks the long-standing "automate prudence discovery" blocker.
- Parsing: FERC audit executive summaries → findings → recommendations (`pipeline/structure.py`,
  snapshot-gated). The prudence orders are metadata-only.

## State PUC / PSC / SCC sources

Each commission's docket system is different. Patterns below are all confirmed by live capture.

### Access tiers (the at-a-glance map — learned across the 2026 expansion)

Every commission falls into one of five access tiers. **Tiers 1–2 are scriptable** (plain `requests` GET, the
default path) and account for all 39 seeded jurisdictions; **tiers 3–5 need a browser** and are the remaining backlog.

| Tier | How docs are served | States | Method |
|------|---------------------|--------|--------|
| **1 · Static `.gov` PDF** | predictable URL path on a `.gov`/`*.state.xx.us`/`.org`-allowlisted host | PA MI VA TX IL SC GA LA AR MO MN WI CO ND SD ID OR NV MT FL KS UT CT RI NY(summaries) NE TN + DC | seed `pdf_url` directly; **verify page 1** (filenames lie — caught a DSM order named "…Settlement", an energy-*data* tariff, IRPs, a résumé) |
| **2 · Scriptable doc-API / valid-cert alias** | a GET endpoint returning the PDF (eLibrary F5 dance; WA `GetDocument`; AZ `docket.images.azcc.gov`; NY DMM `ViewDoc?DocRefId`) | FERC, WA, AZ, NY(orders) | accession/guid/docID harvested from search or a docket page; **AZ gotcha:** use the valid-cert host (`docket.images.azcc.gov`), not the broken-cert `images.edocket.azcc.gov` nor the blank-placeholder `edocket.azcc.gov/docketpdf/` |
| **3 · HTML-only** | decisions published as HTML, no PDF (`.PDF` 404s) | **CA** (CPUC) | seed `fetch=false` with the `.htm` URL (captured by reference, page_count 0); `WebFetch` reads the HTML to verify |
| **4 · WAF / TLS-broken** | scripts get 403 / Access-Denied / SSL-mismatch | OH NC IA NH(Akamai) AL · MS(TLS) | browser-capture (Chrome MCP) + `fetch=false` |
| **5 · DMS/CMS/SPA/login-wall** | doc list is client-side or behind a viewer/login | OK MA WY HI VT ME · NM(login) | reverse-engineer the API or browser-capture the download URL |

**The fetcher (`sources.fetch_doc`) now classifies tier-4 failures** (fail-fast on SSL/403, exponential backoff on
throttling, warn on placeholder PDFs) — see *Access failure modes* above.

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

### GA — Georgia PSC (FACTS) · SPA list, but stable `.gov` download URLs
- **Download (stable, scriptable GET, no cookie):**
  `services.psc.ga.gov/api/v1/External/Public/Get/Document/DownloadFile/{documentId}/{fileId}` (`.gov`;
  pipeline UA fetches directly). Per-doc landing: `psc.ga.gov/search/facts-document/?documentId={id}`;
  docket landing: `psc.ga.gov/search/facts-docket/?docketId={id}`.
- **Enumerating a docket's docs is the hard part — the docket page is a JS SPA** (WebFetch sees docket
  metadata but the filings table is "No records found"); the document-list JSON API endpoint isn't the
  obvious `/Get/Docket/{id}` (404). Two working paths: (a) **browser (Chrome MCP)** to read the rendered
  list; (b) **`WebSearch` harvests indexed `DownloadFile/{id}/{fileId}` URLs** by docket/company keyword
  (Google indexes the PDFs' first-page text, so titles are reliable).
- **Verify trick:** GA PDFs vary — many are **text-based** (WebSearch shows real captions) but some are
  **scanned/image** (no text layer). `WebFetch` can't render either, **but it saves the PDF locally** to
  the tool-results dir — extract page 1 with `fitz`/`pdfplumber` to get the verbatim caption before
  seeding. (Caught a CV and a misc. exhibit mislabeled by search this way.)
- **Shipped:** Georgia Power 2025 IRP (Docket 56002) — 3 PSC **Public Interest Advocacy Staff (PIAS)**
  testimony panels + 1 intervenor (Georgia Conservation Voters); `data/seeds/ga_psc.json`. Follow-ups:
  GA Power's own direct case + the **July 15, 2025 Commission order** approving the IRP (needs the SPA/browser).

### LA — Louisiana PSC (LPSC portal) · stable `.gov` ViewFile, but hostile metadata
- **Download (stable GET):** `lpscpubvalence.lpsc.louisiana.gov/portal/PSC/ViewFile?fileId={token}`
  (`.gov`; pipeline UA fetches directly). The `fileId` is opaque base64 — **URL-encode `+`→`%2B`, `/`→`%2F`,
  `=`→`%3D`** in the seed `pdf_url` (the pipeline `requests` GET passes it through; server decodes).
  Docket landing: `…/portal/PSC/DocketDetails?docketId={internalId}` (server-rendered header — gives the
  `U-#####` number + title; but the **document-list endpoint 500s/SPAs**, and the internal `docketId` ≠ the
  `U-` number).
- **Two metadata traps (verify locally!):** (a) many Entergy filings use a **broken font encoding** that
  mangles the **docket number** in the text layer (e.g. `U- \/ex/\/ma`) even though captions read fine —
  leave `docket` null rather than guess; (b) `WebSearch` scatters `ViewFile` tokens across *many* Entergy
  dockets, so it won't cleanly scope one proceeding. Enumerate a single docket via the browser/SPA.
- **Shipped:** Entergy Louisiana — U-36959 FRP rate-case **Global Settlement** + the **Lake Charles Power
  Station construction-management prudence review** (Jones + Dickens testimony, Dec 2021; tied to approval
  Order U-34283); `data/seeds/la_lpsc.json`. On-theme & prudence-relevant; Grand Gulf/SERI refund + the
  Meta-data-center infrastructure approval are obvious next LA targets.

### MS — Mississippi PSC · two hosts, one cert-broken
- **Static `.gov` (works):** `www.psc.ms.gov/sites/default/files/{...}.pdf` (Drupal) serves agendas, consent
  dockets, Commissioner notes, and the **Mississippi Public Utilities Staff (MPUS) annual reports** — the
  MPUS is the independent staff that runs year-round fuel-adjustment audits (Entergy MS ECR, Mississippi
  Power FCR); its annual report is the cleanest on-theme MS doc fetchable by script.
- **Per-utility docket docs (BLOCKED):** the real docket filings/orders live in InSite at
  `www.psc.state.ms.us/InSiteConnect/InSiteView.aspx?...&docid={N}` (a legacy `.state.ms.us` host — passes
  the gov-guard) **but it serves a broken TLS chain** ("unable to verify the first certificate") → scripts
  and the pipeline fetch fail. Treat like OH/NC: **browser-capture the docid URL + seed `fetch=false`**.
- **Shipped:** MPUS annual reports FY2024 + FY2025; `data/seeds/ms_psc.json`. **High-value InSite targets**
  (browser-capture next): the **Kemper IGCC prudence settlement** (Feb 2018 — Mississippi Power shareholders
  absorbed ~$6B) and the **$300M Entergy Mississippi Grand Gulf settlement** (2022, largest in MPSC history).

### AR — Arkansas PSC (olsv2) · scriptable, stable `.gov` PDF paths
- **Download (stable GET, no cookie):** `apps.apsc.arkansas.gov/pdf/{NN}/{DOCKET}_{DOCNUM}_{PART}.pdf`
  where `{NN}` = the docket's leading 2 chars (e.g. `16` for `16-036-FR`). The `viewdoc/pdfview.asp?document=…`
  link **302-redirects** to that `/pdf/` path; the pipeline UA fetches it (text PDFs, some font mojibake but
  readable). `apps.apsc.arkansas.gov` ends in `.gov` (`*.arkansas.gov`) → passes the guard. Per-doc landing:
  `…/olsv2/Docket_Search_Documents.asp?Docket={DOCKET}&DocNumVal={DOCNUM}`.
- **DO NOT use `apscservices.info`** — the legacy doc store is **`.info` (non-gov)** and is rejected by the
  guard. Use the current `apps.apsc.arkansas.gov` host only.
- **Enumerating docs:** `…/olsv2/docket_search_results.asp?CaseNumber={DOCKET}` is server-rendered but the
  description cells don't expose cleanly to scraping — pull the `DocNumVal` numbers + dates via the browser,
  then **identify each by fetching its PDF page 1** (the doc number alone is opaque). Continuing dockets like
  `16-036-FR` (the EAL FRP) span years; the recent annual filing is the high doc-number tail.
- **Shipped:** Entergy Arkansas 2025 Rider FRP (Docket 16-036-FR) — EAL application (doc 1090) + Staff
  evaluation-report testimony (1107) + **Order No. 74** (1122, approved Dec 12 2025); `data/seeds/ar_apsc.json`.

### AL — Alabama PSC · WordPress, scanned minutes (deferred)
- `psc.alabama.gov/wp-content/uploads/{YYYY}/{MM}/{UPPERCASE-MONTH}-{D}-{YYYY}-Commission-Minutes.pdf` —
  but the minutes are **scanned (no text layer)**, search-indexed paths are **stale** (must scrape the live
  `?s=Commission+Minutes` list), and no clean per-utility orders are indexed (Alabama Power is the only IOU;
  its Rate RSE/ECR/CNP actions live inside the scanned monthly minutes). **Deferred** — low value-per-effort;
  would need OCR + live-index scraping, or the APSC formal-docket system. The Dec 2 2025 rate-freeze / Lindsay
  Hill (data-center-driven) minutes are the on-theme target if revisited.

### MO — Missouri PSC (EFIS) · scriptable, docket-sheet enumerable
- **Download (stable GET):** `efis.psc.mo.gov/Document/Display/{docId}` (`.gov`; text PDFs; pipeline UA
  fetches directly). **Docket sheet (authoritative):** `efis.psc.mo.gov/Case/Display/{caseInternalId}` gives
  the verbatim case caption (which utility) + the full filing list — **use it to confirm the company**, since
  search engines conflate MO case numbers (caught ER-2024-0261 = *Empire/Liberty*, not Ameren as search claimed;
  the Ameren 2024 rate case is *ER-2024-0319*). Map a case number → internal id via the EFIS case search.
- **Shipped:** (1) Empire District Electric (Liberty) 2024 rate case (ER-2024-0261) — 3 MoPSC **Staff direct testimony**
  panels (Eubanks T&D, Lange cost-of-service/rate-design, Giacone PISA/wind/property-tax), `data/seeds/mo_psc.json`;
  (2) **Ameren Missouri Staff prudence reviews** (`data/seeds/mo_ameren_prudence.json`) — the **Tenth FAC Prudence
  Review** (EO-2024-0053, doc 772394) + the **Taum Sauk construction audit & prudence review** (ER-2011-0028, doc 99523).
- **More on-theme gold to mine:** earlier Ameren FAC prudence reviews (`EO-2013-0407` … `EO-2019-0257`, and EO-2024-0053's
  Commission order) + the Ameren large-load / **data-center** tariff docket (`ET-…`, doc 848430).

### MN — Minnesota PUC · use OAH PDFs (eDockets is WAF-walled)
- **eDockets is blocked:** `edockets.state.mn.us` / `efiling.web.commerce.state.mn.us` throws a "Security check"
  (WAF) → scripts blocked. **Instead use the MN Office of Administrative Hearings:** `mn.gov/oah/assets/{…}.pdf`
  serves the ALJ **Findings of Fact / Recommendation** reports for PUC contested cases as direct, text `.gov`
  PDFs (pipeline UA fetches fine; `mn.gov` ends in `.gov`). Filenames are descriptive (`…xcel-rate-increase-puc-report…`).
  Verify the **MPUC docket** off page 1 (`G002/GR-23-413` = gas rate case; `E-002/AA-22-179` = electric fuel forecast;
  `…/GR-24-320` = the 2024 electric rate case).
- **Shipped:** Northern States Power (Xcel) — ALJ report in the gas rate case (G002/GR-23-413) + ALJ Findings on
  the 2023 Annual **Fuel Forecast** (E-002/AA-22-179); `data/seeds/mn_puc.json`. Expand via more `mn.gov/oah` ALJ
  reports (the GR-24-320 electric rate case is the obvious next).

### WI — Public Service Commission of Wisconsin (ERF) · scriptable docid
- **Download (stable GET):** `apps.psc.wi.gov/ERF/ERFview/viewdoc.aspx?docid={N}` (`.gov`; text PDFs; pipeline UA
  fetches directly). Docs are named `Direct-{PARTY}-{Witness}-{n}` / `Ex.-{PARTY}-…` (PARTY = utility code or an
  intervenor like `SC` = Sierra Club). The docket (`{util#}-UR-{nn}`, e.g. `4220-UR-127` NSPW, `3270-UR-125/126` MGE,
  `5-UR-111` We Energies) is on page 1 of most — but **not all** (intervenor testimony sometimes omits it).
- **Shipped (utility-diverse sampler, like VA):** Wisconsin Electric (We Energies) **Very Large Customer & Bespoke
  Resources Tariffs** — Sierra Club's Fisher testimony (574424; the data-center large-load issue) + NSPW 4220-UR-127
  (539705) + MGE 3270-UR-125 (466619) rate-case testimony; `data/seeds/wi_psc.json`. The We Energies very-large-customer
  tariff is the on-theme **data-center** docket to expand (the Commission's final decision + WEPCO's own filing).

### IA — Iowa Utilities Commission (EFS) · WAF-blocked (deferred)
- `efs.iowa.gov` GET_FILE downloads (`…/cs/idcplg?IdcService=GET_FILE&dDocName={N}&…`) are real `.gov` PDFs but the
  host **403s every non-browser client** (pipeline UA *and* WebFetch) — a hard WAF/hotlink block. The filing-search
  and filing-summary pages are SPAs. **Deferred**: needs browser-capture + `fetch=false` (OH/NC pattern). On-theme
  target: MidAmerican Energy rate case **RPU-2023-0001** (gas) and its successors.

### CO — Colorado PUC (E-Filings) · scriptable docs, 2-level enumeration
- **Download (stable GET):** `www.dora.state.co.us/pls/efi/efi.show_document?p_dms_document_id={ID}&p_session_id=`
  (`.state.co.us` legacy-gov ✓; text PDFs; pipeline UA fetches fine). The `efi_p2_v2_demo.show_document` variant works too.
- **Enumeration is 2-level (the catch):** the docket page `EFI.Show_Docket?p_session_id=&p_docket_id={PROC}` lists
  **filings** as `EFI.Show_Filing?p_fil=G_{n}` links (only a few documents inline) — each filing page then exposes the
  `show_document?p_dms_document_id=` PDFs. So a clean rate-case set (PSCo direct testimony → Staff/OCC answer testimony →
  Commission decision) needs the docket→filing→document walk; `WebFetch` 400s the `Show_Docket` page (use the pipeline UA).
  Proceeding numbers: `{YY}AL-{nnnn}E/G` = rate cases (AL = advice letter), `{YY}A-{nnnn}E` = applications.
- **Shipped (PSCo sampler — deeper testimony sets need the 2-level walk):** PSCo electric rate case advice letter
  (22AL-0530E) + an electric Commission decision (24AL-0275E, C25-0122-I) + a gas rate-case hearing transcript
  (22AL-0046G); `data/seeds/co_puc.json`.

### ND — North Dakota PSC · `webdocs` static path (shipped 2026-06-07)

- **PDFs at a fully predictable static path:** `https://www.psc.nd.gov/webdocs/case/{CASE}/{NNN-010}.pdf`
  (`{CASE}` = `YY-NNNN`, e.g. `23-0342`; `{NNN}` = the per-case **sequential document number**, e.g. `157`).
  Plain GET, **pipeline UA, no WAF** — verified live (HTTP 200, born-digital `%PDF`, 1.4 MB). `is_official_gov` ✓ (`.gov`).
- **Enumerate** the doc numbers from the case page (the `psc.nd.gov` site lists each case's filings). Three IOUs:
  **Montana-Dakota Utilities**, **Northern States Power / Xcel**, **Otter Tail Power**.
- **Shipped** (`data/seeds/nd_psc.json`, all 3 IOUs): NSP/Xcel rate-case direct testimony (`PU-24-376`), Otter Tail
  **Dual Fuel Riders** (`PU-23-342`), Montana-Dakota **RRCA** (`PU-25-279`) + **Transmission Cost Adjustment**
  (`PU-25-225`). The `source_page_url` is the generic `psc.nd.gov/public/cases/` landing (per-case pages aren't
  cleanly deep-linkable); the `pdf_url` is doc-specific. Metadata-only.

### SD — South Dakota PUC · `commission/dockets` static path (shipped 2026-06-07)

- **Per-year docket index** `puc.sd.gov/Dockets/Electric/{YEAR}/default.aspx` → docket page `…/{DOCKET}.aspx`
  (docket = `EL{YY}-{NNN}`) → document **PDFs at** `puc.sd.gov/commission/dockets/electric/{YEAR}/{DOCKET}/…pdf`
  (filenames are descriptive, e.g. `attachment1.pdf`, `LTR060425.pdf` — harvest them from the docket page).
  Plain GET, **pipeline UA, no WAF** — verified live (HTTP 200, `%PDF`). `is_official_gov` ✓ (`.gov`).
- IOUs: **NSP/Xcel**, **MidAmerican**, **Otter Tail**, **Black Hills**, **NorthWestern**, **Montana-Dakota**. On-theme:
  fuel-clause riders, transmission-cost-recovery (TCR) reconciliations, energy-adjustment riders. **Shipped**
  (`data/seeds/sd_puc.json`): Otter Tail Phase-In Rider petition (`EL25-026`), MidAmerican TCR reconciliation
  (`EL25-004`), Montana-Dakota TCR annual update (`EL25-006`). **Note:** the per-year index lists dockets as
  `EL{YY}-{NNN}.aspx`; many are routine (welcome brochures, economic-development reports) — read the docket title
  + page 1 to keep only cost-recovery/rate matters. Metadata-only.
- **MISO gap note:** ND + SD close two of the four missing MISO-footprint states; **IA** (`efs.iowa.gov`) is WAF-blocked
  (browser-capture + `fetch=false`, OH/NC pattern) and **MT** (`psc.mt.gov`) is cracked — see the Western section below.

## Southwest & Pacific Northwest states (6 shipped 2026-06-07; NM blocked)

The Western Interconnection PUCs. **Five crack cleanly and are seeded** (plain GET, pipeline UA, no WAF, `.gov`,
verified live — HTTP 200 + born-digital `%PDF`): `data/seeds/{wa_utc,or_puc,id_puc,mt_psc,nv_pucn}.json`, each with a
`test_is_official_gov` assertion. **Two are blocked** (AZ broken TLS, NM registration wall). Signature on-theme
proceeding everywhere out here is the annual **power-cost adjustment** (each state's fuel-equivalent: PCA / PCAM / PCCAM / DEAA).

- **WA — Washington UTC** ✅ `utc.wa.gov`. Clean document API: `https://apiproxy.utc.wa.gov/cases/GetDocument?docID={ID}&year={YEAR}&docketNumber={DOCKET}` (verified 200, 0.9 MB PDF). Human docket pages list docs/orders: `utc.wa.gov/casedocket/{YEAR}/{DOCKET}/docsets` and `…/orders` (harvest the `docID`s there). IOUs: **Puget Sound Energy**, **Avista**, **PacifiCorp**. On-theme: GRCs, power-cost / multiyear rate plans, refunds.
- **OR — Oregon PUC** ✅ `apps.puc.state.or.us` / `edocs.puc.state.or.us` (legacy `.state.or.us`). **Two stable paths:** Commission orders at `apps.puc.state.or.us/orders/{YEAR}ords/{ORDER}.pdf` (e.g. `2008ords/08-261.pdf`, fully predictable by order number) and docketed filings at `edocs.puc.state.or.us/efdocs/{TYPE}/{slug}.pdf` (both verified 200). IOUs: **PGE**, **PacifiCorp (Pacific Power)**, **Idaho Power**, **Avista**. On-theme: PCAM/TAM power-cost mechanisms, GRCs.
- **ID — Idaho PUC** ✅ `puc.idaho.gov`. Beautifully predictable **fileroom** path: `puc.idaho.gov/Fileroom/PublicFiles/ELEC/{UTIL}/{CASE}/{OrdNotc|Company|Staff}/{YYYYMMDD}{file}.pdf` — **final orders live in `/OrdNotc/`** (e.g. `…/ELEC/IPC/IPCE2211/OrdNotc/20220531Final_Order_No_35421.pdf`, verified 200). `{UTIL}` = `IPC` (Idaho Power) / `AVU` (Avista) / `PAC` (Rocky Mountain Power). On-theme: annual **PCA** (power cost adjustment).
- **NV — PUCN** ✅ `pucweb1.state.nv.us` (legacy `.state.nv.us`). Direct PDF pattern `pucweb1.state.nv.us/pdf/CS{NNNNN}.pdf` (e.g. `CS27269.pdf`, verified 200) — the `CS` doc id is harvested from the docket page `pucweb1.state.nv.us/puc2/DktDetail.aspx` (search type "PUC - Public Search - Dockets"). Post-Oct-2023 docs are on the newer `puc-onbase.nv.gov` (OnBase). IOU: **NV Energy** (Nevada Power / Sierra Pacific). On-theme: annual **DEAA** (Deferred Energy Accounting Adjustment) — an explicit fuel/purchased-power *prudence* review (NRS 704.187).
- **MT — Montana PSC** ✅ `psc.mt.gov`. Static order/doc PDFs at predictable paths: `psc.mt.gov/News/Special/{slug}_DOC-{id}.pdf` (e.g. `FinalOrder7860y_DOC-26058.pdf`, verified 200, 0.8 MB) and `psc.mt.gov/_docs/Energy/pdf/…pdf`. The full docket document-search (`DOC-{id}` ids) is browser-driven; the static News/Special order PDFs are the quick win. IOU: **NorthWestern Energy** (also Montana-Dakota). On-theme: **PCCAM** (Power Costs & Credits Adjustment Mechanism), GRCs.
- **AZ — Arizona Corporation Commission · CRACKED (use the valid-cert host alias).** The eDocket image host has **three aliases for the same files**; pick the one with a valid cert: **`docket.images.azcc.gov/{DOCID}.pdf`** ✅ (valid cert, `ssl_verify=0`, 200, real born-digital docs — e.g. TEP Decision No. 79065 = `0000209684.pdf`, 189 pp) and **`edocket.azcc.gov/docketpdf/{DOCID}.pdf`** ✅ (valid cert too, **but** that `/docketpdf/` path returns a **blank 1-page placeholder** anonymously — avoid it). The original **`images.edocket.azcc.gov/docketpdf/…`** has a **broken cert** (hostname mismatch) — don't use. So: seed `docket.images.azcc.gov/{DOCID}.pdf` (path WITHOUT `/docketpdf/`). The `{DOCID}` is harvested from the docket-search item-detail pages or via `WebSearch site:images.edocket.azcc.gov/docketpdf` (Google indexes them; swap the host). The **main-site** `www.azcc.gov/divisions/utilities/electric/…pdf` also serves born-digital orders (e.g. `APS-FinalOrder.pdf`). **Shipped** (`az_acc.json`): APS rate-case order (E-01345A-03-0437) + TEP Decision 79065 (E-01933A-22-0107). IOUs: **APS**, **Tucson Electric Power**, **UNS**. On-theme: **PSA** (Power Supply Adjustor) prudence, rate cases. Metadata-only.
- **NM — Public Regulation Commission · BLOCKED (login wall; old host dead).** NMPRC migrated to **PRCe360** (live 2026-01-26). The **old `edocket.nmprc.state.nm.us` is now dead** (connection refused), and the new **`edocket.prc.nm.gov` 302-redirects to `Login.aspx?ReturnUrl=%2f`** — confirmed registration/login wall, no anonymous document access. `prc.nm.gov` ✓ gov but only hosts site pages + `wp-content` instruction PDFs, not case documents. To seed: create a Public Guest Account and drive the new portal in a browser (then `fetch=false`), or wait for a public document URL pattern to surface. IOUs: **PNM**, **El Paso Electric**, **SPS (Xcel)**. On-theme: **FPPCAC** (fuel & purchased-power cost adjustment) — a prudence review.
- **CA — CPUC · HTML-only decisions, seeded `fetch=false` (shipped 2026-06-07).** California's signature on-theme doc is the **ERRA (Energy Resource Recovery Account) reasonableness review** — the annual fuel & purchased-power *prudence* determination for PG&E / SCE / SDG&E (e.g. D.06-01-007 rejected a $16.36M disallowance against SCE). **Access caveat:** CPUC publishes decisions as **HTML**, not PDF — `docs.cpuc.ca.gov/published/Final_decision/{id}.htm` (the `.PDF` variant 404s), so the PDF pipeline can't extract them. Seed them **`fetch=false`** with the `.htm` URL as `pdf_url` (captured by reference, page_count 0) — `docs.cpuc.ca.gov` is `.ca.gov` ✓. `WebFetch` reads the HTML to verify decision#/date/holding. `data/seeds/ca_cpuc.json`. *Deepen:* recent (2020+) ERRA decisions live as real PDFs under the opaque `docs.cpuc.ca.gov/PublishedDocs/Published/G000/M.../K.../{id}.PDF` paths — harvest those for fetchable records.
- **NY — Department of Public Service · two clean paths (shipped 2026-06-07).** **Easiest:** the DPS publishes statutorily-required (Public Service Law §66(12)(l)) **rate-case summaries** as static PDFs at `dps.ny.gov/system/files/documents/{YYYY}/{MM}/{slug}.pdf` (plain GET, pipeline UA, `.ny.gov` ✓) — on-theme and reliable. **Also:** the DMM serves the actual Commission **orders** as fetchable PDFs at `documents.dps.ny.gov/public/Common/ViewDoc.aspx?DocRefId=%7B{GUID}%7D` (the `{}` braces URL-encode to `%7B…%7D`; verified a real 17-pp PSC order) — but the `DocRefId` must be harvested from the matter's document list, and many guids are testimony/press-releases (**verify the caption**, not the title). Shipped 3 §66(12)(l) summaries (National Grid 24-E-0322, Con Ed 25-E-0072, NYSEG 25-E-0375) + the **National Grid rate-case Joint Proposal** (149 pp, harvested from the DMM via guid `90E66D96`); `data/seeds/ny_dps.json`. **DMM caption-verify:** the guids Google indexes for a case are mostly off-theme (securities-issuance orders, transmission-siting Article VII orders, grid-of-the-future, testimony, press releases) — read page 1 before seeding; the substantive rate documents (Joint Proposal, Order Adopting It) are buried among them. IOUs: Con Ed, National Grid (Niagara Mohawk), NYSEG, RG&E, O&R, Central Hudson.
  - **DMM doc list is SCRIPTABLE — no browser needed (cracked 2026-06-22, supersedes the old "browser-harvest the matter master" note).** Ignore `MatterManagement/CaseMaster.aspx` (client-rendered DataTables — `WebFetch`/`requests` see an empty grid) **and** its legacy AJAX route `/public/CaseMaster/DocumentExternal/{MatterSeq}` (302s to `generalerror.aspx`). The **modern search server-renders the full result list**: `GET documents.dps.ny.gov/search/Home/DocumentSearch2/?searchCriteria={case-or-keyword}` returns HTML with one row per document — each exposing the title **and** the fetchable PDF links `…/search/Home/DownloadDoc/Find?id=%7B{GUID}%7D&ext=pdf` **and** `…/public/Common/ViewDoc.aspx?DocRefId=%7B{GUID}%7D` (both verified to return `application/pdf`; seed the canonical `ViewDoc.aspx` form to match existing records). Regex the rows for `DownloadDoc/Find\?id=(%7B[0-9A-Fa-f-]+%7D)&amp;ext=pdf&amp;docTitle=([^"]+)`. **Caveats:** results are full-text relevance-ranked, capped at 50/page (the `page` param is unreliable — narrow `searchCriteria` instead), and pull in *sibling* cases (a `23-M-0103` query returns some `22-E-0317` rows) — filter to the target case/title and **still verify page 1**. The LIPA/PSEG-LI audit (a LIPA-Reform-Act matter, no `##-X-####` case number) is reachable via its landing page `dps.ny.gov/audit-lipa-and-pseg-long-island` → the report's `ViewDoc` link.
  - **Shipped 2026-06-22 (`data/seeds/ny_dps_audits.json`):** the two NorthStar Consulting **comprehensive management & operations audits** — NYSEG/RG&E (Case 23-M-0103: 439-pp final report w/ 128 recommendations + the initiating order, order releasing the report, and 716-pp utility implementation plans) and LIPA/PSEG-LI (Matter 21-00618: 569-pp final report w/ 49 recommendations). All `fetch=true`/`parse=false`. *Deepen:* the NorthStar M&O report format is consistent across NY (and other states NorthStar audits) — a candidate for a gated findings parser (§5); the final "Order Adopting Terms of Joint Proposal" guids per rate case; fuel.
- **KS — Kansas Corporation Commission · `estar` ViewFile PDFs (shipped 2026-06-07).** Direct fetchable PDFs at `estar.kcc.ks.gov/estar/ViewFile.aspx/{filename}.pdf?Id={guid}` (plain GET, pipeline UA, `.ks.gov` ✓; the `{guid}` is the stable key — filenames carry spaces/parens/apostrophes and are passed through fine). Shipped: the **25-EKCE-294-RTS** base-rate Order approving the unanimous settlement (88 pp) + the **Winter Storm Uri** cost investigation stipulation (`21-EKME-329-GIE` / `21-GIMX-303-MIS`, Feb-2021 extraordinary fuel-cost prudence). `data/seeds/ks_kcc.json`. **Caption-verify is essential here:** filenames mislead — `Order_on_Evergy's_App._and_Settlement_Agreements.pdf` is a *DSM/KEEIA* order (off-theme), and several "Order…" hits are the parties' *applications/motions*, not Commission orders. On-theme: Evergy **RECA** (Retail Energy Cost Adjustment = fuel) + **ACA** (annual true-up). *Deepen:* a RECA/ACA fuel-true-up order.
- **OK — Oklahoma Corporation Commission · imaging URLs need harvesting (deferred).** OCC case files are PDFs at `imaging.occ.ok.gov/AP/CaseFiles/occ{NNNNNNNN}.pdf` (`.ok.gov` ✓), but the doc-id form indexed by search **404s** (stale ids / the imaging app rewrites them) — the live ids must be harvested from the OCC case-search (PUD/cause lookup) before seeding. On-theme: OG&E / PSO **Fuel Cost Adjustment** + the **2021 Winter Storm Uri** securitization/prudence causes.
- **MA — DPU · fileroom is a SPA (API needed).** `eeaonline.eea.state.ma.us/DPU/Fileroom/dockets/bynumber/{docket}` (`.state.ma.us` ✓) renders the document list **client-side** — a plain GET returns only the shell, no PDF links. Reverse-engineer the fileroom's download API (or browser-capture) before seeding. On-theme dockets: `{YY}-OGAF-…` / `{YY}-PGAF-…` (gas adjustment factors = fuel-equivalent), base-rate cases.
- **UT — PSC · `pscdocs` static repository (shipped 2026-06-07).** Cleanest western portal: every filing is a static PDF at `pscdocs.utah.gov/electric/{YY}docs/{docketnodash}/{docid}{TitleAbbrev}{date}.pdf` (plain GET, pipeline UA, `.utah.gov` ✓; commas in the filename pass through fine). Docket folder = the docket number with dashes removed (`24-035-04` → `2403504`). Per-year order index at `psc.utah.gov/electric/orders-notices/electric-{YEAR}/`. Shipped: Rocky Mountain Power (PacifiCorp) base-rate Report & Order (`24-035-04`, $382.1M) + the **EBA (Energy Balancing Account) audit** for CY2023 (`24-035-01`, Daymark's independent audit of RMP's net-power/fuel-cost prudence — the Feb-2025 order disallowed ~$19.4M). `data/seeds/ut_psc.json`. On-theme: **ECAM/EBA** (energy-cost/balancing = fuel prudence), rate cases.
- **CT — PURA · `portal.ct.gov/-/media` static PDFs (shipped 2026-06-07).** PURA decisions are static PDFs at `portal.ct.gov/-/media/pura/{...}/{slug}.pdf` and `portal.ct.gov/-/media/PURA/{slug}.pdf` (plain GET, `.ct.gov` ✓). Shipped two PURA Final Decisions: the **Tropical Storm Isaias** EDC preparation/response investigation (`20-08-03`, 139 pp, civil penalties on Eversource/UI — a management-performance prudence matter) + a distribution rate-design decision (`17-12-03RE011`). `data/seeds/ct_pura.json`. EDCs: CL&P d/b/a Eversource, United Illuminating. *Deepen:* Eversource base-rate (e.g. `22-08-01`) + RAM (Rate Adjustment Mechanism = cost recovery) final decisions — slugs harvested from the PURA docket pages / press releases.
- **NH — PUC · Akamai WAF (deferred).** `puc.nh.gov/VirtualFileRoom/ShowDocument.aspx?DocumentId={guid}` (`.nh.gov` ✓) is **Akamai-fronted** and returns "Access Denied" (`errors.edgesuite.net`) to scripts/WebFetch — browser-capture + `fetch=false` (OH/NC/IA pattern). On-theme: Eversource Energy Service (default-service power supply = fuel) `DE 24-046`, distribution rate case `DE 24-070`. **ME — PUC (browser-only):** the CMS at `mpuc-cms.maine.gov/CQM.Public.WebUI/Common/ViewDoc.aspx?DocRefId=%7B{guid}%7D&DocExt=pdf` (`.maine.gov` ✓) **returns an HTML "Message" page to a plain GET** — the viewer needs a session/JS (browser-capture). Case master: `…/CaseMaster.aspx?CaseNumber={YYYY-NNNNN}`. On-theme: CMP rate case `2025-00218`, Versant 2023 rate case, the CMP/Versant service-quality investigation `2022-00279`.
- **RI — PUC · `ripuc.ri.gov` static PDFs (shipped 2026-06-07).** Filings/orders at `ripuc.ri.gov/sites/g/files/xkgbur841/files/{YYYY-MM}/{docket}%20{desc}.pdf` (plain GET, `.ri.gov` ✓; spaces `%20`-encoded). Per-docket landing `ripuc.ri.gov/Docket-{docket}`; orders index `ripuc.ri.gov/events-and-actions/decisions-and-orders/{natural-gas|electric}`. Shipped RI Energy (Narragansett Electric) **2024 Gas Cost Recovery** (`24-29-NG`, the GCR clause = gas fuel-cost recovery) + PUC Order 25247 (`24-38-GE`). `data/seeds/ri_puc.json`. On-theme: **GCR** (gas cost recovery), base-rate cases (Report & Order No. 23823, docket 4770). *Deepen:* a GCR Report & Order; the 25-45-GE base-rate case once decided.
- **WY — PSC · DMS portal, no `.gov` static PDFs (browser-only).** `psc.wyo.gov`'s orders link out to the **`dms.wyo.gov/external/publicusers.aspx`** Docket Management System (a search portal); no static `.gov` PDF path is exposed, and the only indexed RMP filing PDFs are on `rockymountainpower.net` (non-gov, rejected). On-theme: Rocky Mountain Power **ECAM** (Schedule 95 = fuel), Docket `20000-671-ER-24`. Harvest the DMS download URL in a browser before seeding.
- **HI — PUC · DMS unreachable + static D&Os moved (browser-only).** Hawaiian Electric's **ECRC** (Energy Cost Recovery Clause = fuel/IPP cost) is the signature on-theme proceeding (D&O 40044, June 2023; the 2019–2023 ECRC review pegged oil-volatility costs at ≥$250M). But the DMS viewer `dms.puc.hawaii.gov/dms/DocumentViewer?pid={PID}` **refuses scripted connections (000)**, and the old static `puc.hawaii.gov/wp-content/uploads/{Y}/{M}/DO-No.-{N}.pdf` files now **return the site's HTML 404** (some recent wp-content PDFs — annual reports, summaries — still serve). Browser-capture the DMS PID. `.hawaii.gov` ✓.
- **VT — PUC (browser-only):** orders are in **ePUC** (`epuc.vermont.gov`) or on the utility site (`greenmountainpower.com`, non-gov); `puc.vermont.gov` static PDFs are only plans/procedures. Harvest from ePUC.
- **AL — PSC (browser-only):** only `alabamapower.com` (non-gov) copies are indexed; `psc.alabama.gov` is WAF-walled (403 to scripts, scanned minutes). Alabama Power **Rate ECR** (Energy Cost Recovery) + **RSE** (Rate Stabilization & Equalization) are the on-theme mechanisms.
- **NE — PSC · `nebraska.gov/psc/orders` static PDFs (shipped 2026-06-07).** NE electric is all-public-power, but the PSC **rate-regulates the natural-gas IOUs** (Black Hills, NorthWestern). Orders are static PDFs at `www.nebraska.gov/psc/orders/natgas/NG-{docket}.{seq}.pdf` (plain GET, `nebraska.gov` ✓). Shipped: Black Hills **Cost-of-Service Gas Hedge Agreement** with its affiliate — **DENIED** (`NG-0086`, affiliate gas-cost prudence) + SourceGas **gas-supply contract buyout cost recovery** (`NG-0088`). `data/seeds/ne_psc.json`. On-theme: gas-cost/hedge/affiliate prudence, **Gas Supply Cost Review** (`NG-119`), Choice Gas reviews.
- **TN — TPUC · `tpucdockets.tn.gov` static archive (shipped 2026-06-07).** Filings/orders are static PDFs at `tpucdockets.tn.gov/archive/filings/{YEAR}/{docnum}{seq}.pdf` (`{docnum}` = docket digits, e.g. `21-00107` → `2100107`; `{seq}` = a letter suffix per filing) — plain GET, `.tn.gov` ✓. Shipped: Kingsport Power (AEP) general rate case (`21-00107`) + the Utilities Division's **Atmos WNA (Weather Normalization Adjustment) audit** (`25-00044`). `data/seeds/tn_tpuc.json`. IOUs are mostly **gas** (Atmos, Piedmont) + small electric (Kingsport/AEP) — most of TN is TVA/munis/coops (not PUC-rate-regulated).

> **Boundary note (2026-06-07, corrected):** static-`.gov`-PDF states are seeded out to **39 jurisdictions** — including the gas-only-IOU states (NE, TN) that a first pass dismisses. The genuinely walled remainder — **OK, MA, NH, WY, HI, VT, ME, AL, NM, NC, IA** — each sits behind a **DMS/CMS viewer, a SPA, a WAF, or a login wall**, so *those* need a **browser-capture pass** (Chrome MCP), not more `requests` GETs. Only **AK** (tiny coop/muni IOUs) and US **territories** (PR/USVI/Guam — separate regulators) remain genuinely out of scope. Per-state walls + recipes above and in [BACKLOG.md](../BACKLOG.md).

## PJM-footprint states (rate cases + fuel-cost adjustments)

The PJM expansion. **Best-practice learned across all five: a state PUC often publishes its
*orders* at a predictable static `.gov` path even when its docket *search* is a JS app or behind a
WAF — prefer that static order host for `pdf_url`.** And always verify order-vs-**press-release**
(MD's Pepco "decision" turned out to be a press release — dropped).

### NJ — New Jersey BPU
- **Docket system:** `publicaccess.bpu.state.nj.us` — ASP.NET WebForms behind an **Imperva/Incapsula
  WAF** (needs a `visid_incap`/`incap_ses` cookie dance, same shape as eLibrary's F5).
- **But board orders are WAF-free static PDFs** on `www.nj.gov`:
  `www.nj.gov/bpu/pdf/boardorders/{year}/{agenda-date}/…pdf` and `…/pdf/energy/bgs/…pdf` — plain GET,
  pipeline UA, 200. Seed these. (A raw `&` in a filename, e.g. `JCP&L`, fetches fine unencoded.)
- On-theme: base-rate case orders (PSE&G `ER23120924`, JCP&L `ER23030144`), BGS procurement
  (`ER25040190`). Metadata-only.

### MD — Maryland PSC
- **Order PDFs (scriptable):** `psc.maryland.gov/wp-content/uploads/<slug>.pdf` — **Cloudflare-fronted
  but currently serves the pipeline UA directly (200, no challenge)**; treat as Cloudflare (could
  harden — capture-date everything). The `www.psc.state.md.us/wp-content/...` host 301-redirects here.
- **Docket system:** the DMS case-search (`webpscxb.psc.state.md.us/DMS/…`, case numbers are 4-digit
  no-year e.g. `9692`) renders the per-case doc table **client-side** → browser-capture to enumerate.
- On-theme: rate / multi-year-plan orders (BGE `9692`, Potomac Edison `9695`, Pepco `9702`). **The
  old ColdFusion `webapp.psc.state.md.us` host is dead.** Metadata-only.

### DE — Delaware PSC
- **DelaFile** `delafile.delaware.gov` — IIS/ASP.NET, **no WAF**. Search is a VIEWSTATE form-POST;
  per-docket sheet works by number: `…/CaseManagement/DocketSheet.aspx?MatterNo={docket}&Type=Docket&ViewDocketPage=ViewDocketPage`;
  PDFs at `…/ViewFileNetDocument.aspx?Id={guid}` (GUIDs scraped from the docket page).
- **Also** `depsc.delaware.gov/wp-content/uploads/sites/54/{year}/{mm}/…pdf` serves agenda/order PDFs
  at static paths (what we seeded for Delmarva `22-0897`). Metadata-only.

### KY — Kentucky PSC · deterministic order paths, no WAF
- **Order/Commission PDFs (deterministic, plain GET, no cookie):**
  `psc.ky.gov/pscscf/{YEAR}%20Cases/{CASE}/{YYYYMMDD}_PSC_ORDER.pdf` (also `_ORDER01.pdf`, `_DATA_REQUEST.pdf`).
- **Party filings:** `psc.ky.gov/pscecf/{CASE}/{filer-email}/{timestamp}/{file}.pdf` (non-guessable
  segments — harvest from the case folder `psc.ky.gov/Case/ViewCaseFilings/{CASE}`, whose filing table
  is client-side).
- On-theme: FAC reviews (Kentucky Power `2024-00136`), base-rate cases (LG&E `2025-00114`, Duke KY
  `2024-00354`). Metadata-only.

### IN — Indiana IURC · deterministic order paths, no WAF
- **Commission Orders (deterministic, plain GET):** `www.in.gov/iurc/files/ord_{CAUSE}{SUBDOCKET}_{MMDDYY}.pdf`
  (e.g. `ord_38707FAC147_040826.pdf`; some have a hyphen `ord_38703-FAC132_…`). Also on `secure.in.gov`.
- **Filed docs (testimony/exhibits):** Power-Apps portal `iurc.portal.in.gov` SharePoint entity URLs
  `…/_entity/sharepointdocumentlocation/{recordGuid}/bb9c…?file={name}.pdf` (recordGuid harvested from
  the server-rendered search; the second GUID is constant).
- On-theme: fuel-cost-adjustment (FAC) orders — Duke Indiana `38707`, NIPSCO `38706`, AES Indiana
  `38703` (each quarter is a `FAC NNN` sub-docket). Metadata-only.

### WV — West Virginia PSC · ColdFusion, UA-filtered
- **WebDocket** `psc.state.wv.us/scripts/WebDocket/` (ColdFusion/IIS). Search `viewCaseForWebList.cfm`
  → internal `CaseID` → `tblCaseActivitiesList.cfm?CaseID={id}` lists filings with `CaseActivityID`s →
  PDF at `…/ViewDocument.cfm?CaseActivityID={id}&NotType=WebDocket`.
- **Gotcha (drove a general fix):** the IIS request-filter **404.19-denies any UA containing the
  `python-requests` token** (serves the same PDF fine to a browser UA). We **dropped that token from
  `config.USER_AGENT`** (now just `FERC-Audit-Tool/0.1 (+repo URL; public-interest research)`) — still
  honest, no longer filtered. No regression on the other 12 sources.
- On-theme: APCo/Wheeling Power ENEC (fuel-cost) orders — `23-0377-E-ENEC` (Jan 2024 order **disallowed
  $231.8M** as imprudent coal-stockpiling), `25-0413-E-ENEC`. Metadata-only.

### DC — DC PSC · `.org` host (allowlisted), no WAF
- **e-Docket** `edocket.dcpsc.org` — Angular SPA search, but PDFs are at stable plain-GET URLs:
  `edocket.dcpsc.org/apis/api/Filing/download?attachId={id}&guidFileName={guid}.pdf` (no WAF; pipeline
  UA fetches directly). Per-case human landings at `dcpsc.org/Newsroom/HotTopics/Rate-Case-Applications/FC{n}.aspx`.
- **Provenance note:** the DC PSC is an official US-government commission but publishes only on **`.org`,
  not `.gov`** — admitted via the gov-guard's narrow exact-domain allowlist (`_OFFICIAL_GOV_ORG_DOMAINS`;
  ISSUES.md 2026-06-02). The `attachId`s are harvested from the SPA / `.aspx` landings.
- On-theme: Pepco Multiyear Rate Plan (`FC 1176`) Order & Opinion + reconsideration. **Gotcha:** the
  `dcpsc.org/CMSPages/GetFile.aspx?guid=…` "order" we first tried was a **press release** — verify page 1.
  Metadata-only.

### FL — Florida PSC · static order PDFs, two hosts (one .gov)

- **Two mirror hosts serve the same files:** `www.floridapsc.com` (**`.com` — rejected by the gov-guard**)
  and **`www.psc.state.fl.us`** (legacy `.state.fl.us` ✓ — use this one). Both expose identical static
  paths; always seed the `.state.fl.us` URL.
- **Order PDFs (stable plain GET, pipeline UA, no WAF):**
  `www.psc.state.fl.us/library/Orders/{YEAR}/{DOCNUM}-{YEAR}.pdf` (the `{DOCNUM}` is the clerk's
  sequential **document number**, *not* the `PSC-YYYY-NNNN-FOF-EI` order number). Filings live at
  `…/library/filings/{YEAR}/{DOCNUM}-{YEAR}/{DOCNUM}-{YEAR}.pdf`.
- **Human landing:** `www.psc.state.fl.us/document-detail?orderNum={ORDER-NUMBER}` (an Angular SPA —
  fine as a `source_page_url`, but it renders client-side so you can't scrape the PDF link from it).
- **Finding the doc number (the catch):** the order#→doc# map isn't on the SPA. Harvest the
  `library/Orders/{YEAR}/{DOCNUM}.pdf` URL via `WebSearch` restricted to `psc.state.fl.us` (Google
  indexes the order text), then **verify page 1 locally** — `WebFetch` saves the binary even when it
  can't render it; one `fitz` pass reads the caption + confirms it's a **FINAL ORDER** (skip the
  `-PCO-EI` procedural / `-PHO-EI` prehearing / notice docs that share the docket).
- **On-theme (Florida's signature prudence dockets are the annual cost-recovery *clauses*):** Fuel &
  purchased-power cost recovery (Docket `{YY}0001-EI`, e.g. `PSC-12-0664-FOF-EI`), Nuclear cost
  recovery (`{YY}0009-EI`, prudence/true-up of nuclear project costs, e.g. `PSC-14-0617-FOF-EI`), and
  Storm-protection-plan cost recovery (`{YY}0010-EI`, e.g. `PSC-2023-0364-FOF-EI` / `PSC-2024-0459-FOF-EI`).
  `data/seeds/fl_psc.json`. Metadata-only.

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

## Fuel-adjustment-clause / prudence-review harvest — 2026-07-06 finder-agent pass

A finder agent (BACKLOG P2 #5) searched 8 states with little/no fuel-clause coverage. Landed 2
verified candidates (**FL** `20250001-EI` above; **NM** dropped — see below), and confirmed/durable
dead-ends for the other 6 — recorded here so a future session doesn't re-spend an agent on the same
seams:

- **NM — found a real, on-theme document but no `.gov`-hosted copy exists.** PNM's periodic FPPCAC
  factor-reset notices (Case `22-00270-UT`, the same base docket as the already-seeded 2023 rate-case
  recommended decision — NM apparently administers the clause via notices filed under the original
  rate-case docket rather than a new case number each quarter) are self-published at `pnm.com` — the
  *utility's own* site, not `prc.nm.gov`. `WebSearch site:prc.nm.gov` for the exact case number
  surfaces only the existing rate-case documents, not the factor-reset notices. Rejected by
  `_assert_official_gov` correctly — do not add `pnm.com` to `_OFFICIAL_GOV_ORG_DOMAINS` (that
  allowlist is for a commission's *own* non-`.gov` domain, e.g. `nm-prc.org`, never a regulated
  utility's site). Would need NM PRC's own case-file system (not indexed here) to close.
- **Mississippi** — correct docket numbers exist (Entergy MS ECR-4, Docket 2023-UN-145; Mississippi
  Power FCR-2) but `psc.ms.gov`'s Utility Docket listing only shows rate-schedule tariff sheets for
  these, not a fetchable order/notice PDF. Next attempt: navigate `psc.ms.gov`'s e-filing/docket-detail
  page for 2023-UN-145 directly, not the monthly docket listing.
- **Oklahoma** — real OG&E/PSO annual Fuel Adjustment Clause dockets exist before the OCC, but every
  `imaging.occ.ok.gov` URL surfaced by search (e.g. `occ30399759.pdf`) 404s on fetch — the OCC imaging
  system's links go stale once out of the live case-search UI. Needs `case.occ.ok.gov`'s live search
  (browser-only), not search-engine-cached links.
- **Colorado** — Xcel bundles fuel cost recovery into its general rate cases via the Electric Commodity
  Adjustment rider; no standalone fuel-prudence docket found. Off-theme by design, not a gap.
- **Montana** — PCCAM-specific docket `2021.04.047` confirmed to exist (via search snippets) but
  `psc.mt.gov`'s document search is a Tableau-embedded portal with no direct document links — would
  require guessing a URL (against the rules). The only fetchable PDF was NorthWestern's general rate
  case, not the PCCAM docket.
- **Utah** — only fetchable RMP ECAM-adjacent document found was a 2009 procedural scheduling order
  (Docket 09-035-15) — not a substantive prudence/approval order.
- **Nevada** — `puc-onbase.nv.gov` is a search-portal-only interface (no direct document links);
  `pucweb1.state.nv.us` links found were image-only/corrupted streams, unverifiable within budget.

## Management/operations audit expansion — 2026-07-10 (state_audit +21 across 5 states)

A finder-agent batch (6 states) targeting genuine utility *audit reports* for the `state_audit`
collection. Landed **21 verified metadata-only records** (FL 6, IL 4, CA 4, DC 3, WA 4) — 3 new
states (FL, DC, WA), CA 2→6, IL 1→5. All page-1-verified by download; `pipeline.verify_sources` PROVEN.
New reusable source recipes:

- **FL — Florida PSC Office of Auditing and Performance Analysis** · static `.gov` PDFs. The staff
  management/operations audit program ("Review of … BY AUTHORITY OF The Florida Public Service
  Commission, Office of Auditing and Performance Analysis") publishes every report under one flat dir:
  `https://www.psc.state.fl.us/pscfiles/website-files/PDF/Publications/Reports/General/Electricgas/{Name}.pdf`
  (identical mirror on `www.floridapsc.com`, but **use `psc.state.fl.us`** — the `.com` fails the
  gov-guard). Index page: `https://www.psc.state.fl.us/reports`. No docket on these staff reports.
- **DC — DC PSC eDocket API** (`edocket.dcpsc.org`, allowlisted `.org`). The SPA has two undocumented
  GET endpoints that need no browser: `apis/api/Filing/GetFilings?caseNumber=FC1154&recordsToShow=800&isAdmin=false&orderByColumn=receivedDate&sortBy=asc&caseTypeId=0`
  → rows with `filingId`/`filingType` (filter `filingType=="Report - Audit"`); then
  `apis/api/Filing/GetAttachmentsByFilingId?filingId={id}` → `{attachmentId, guidFilename, pageCount}`.
  Stable download URL: `apis/api/Filing/download?attachId={attachmentId}&guidFileName={guidFilename}`
  (guidFilename already ends `.pdf`). **Always take the `isConfidential:false` / "Public" attachment**
  (each audit has a confidential twin). DC PSC statutorily orders periodic management audits of Pepco
  (FC 1176) & Washington Gas (FC 1154 PROJECTpipes 2, FC 1115 PROJECTpipes).
- **WA — UTC Pipeline Safety inspection reports** · static `.gov` PDFs, a *different* host path from
  the existing WA `apiproxy.utc.wa.gov/cases/GetDocument` case-API. UTC inspectors audit each gas/LNG
  operator against a published protocol set (`WA.GD.2024.02`, `LNG.2024.01`, `GD.2025.01`), producing
  scope + findings + satisfactory/unsatisfactory ratings. URL:
  `https://www.utc.wa.gov/sites/default/files/{YYYY-MM}/{report#}%20Inspection%20Report.pdf`; the
  report# and upload-month folder are harvested from the per-operator index page
  (`.../pipeline-operators-inspected-pipeline-safety-program/{operator}-inspection-reports`), whose
  **year sections are JS accordions** (collapsed on load → need a browser to reveal the links). No
  docket (program inspections). NOTE: classic WA UTC *docketed* consultant management audits (PA/NY
  genre) do **not** exist — WA uses prudence reviews / GRCs / penalty investigations (already seeded).
- **CA — CPUC Utility Audits Branch** · the energy audit-reports index lists **381 reports** across 6
  categories; `.../reports/energy/{YYYY}/energy_{YYYY-MM-DD}_{util}_{ba|atr}.pdf` on `cpuc.ca.gov`.
  Added Balancing-Accounts + a new-to-corpus **Affiliate Transaction Rules** audit type. Deep room to
  scale (PacifiCorp, Bear Valley, Liberty Utilities BA; more ATR).
- **IL — ICC** · Liberty Consulting Group audits on `icc.illinois.gov` (static `/downloads/public/…`
  and `api/web-management/documents/downloads/public/…`; URL-encode spaces). Genuine management /
  baseline-grid-assessment (§16-105.10 CEJA, dockets 21-0736/21-0737) / storm-restoration audits.

**VA — dead seam (intentional exclusion).** The VA SCC does **not** publish standalone management/
operations audit *reports*; its "audit" work product is **Commission Staff prefiled testimony**
(Division of Utility Accounting & Finance earnings-test exhibits) inside biennial/triennial reviews —
adjudicative filings that belong in `state_rate_case`, not `state_audit`. Held out to preserve the
audit collection's meaning. Useful byproduct: the SCC DocketSearch SPA has a scriptable Breeze OData
API — `scc.virginia.gov/DocketSearchAPI/breeze/CASES_ESTABDATE/GetCasesEstDate?$filter=Case_Number eq 'PUR-2024-00024'&$select=MATTER_NO,…`
then `…/breeze/CaseDetails/GetDocuments?$filter=MATTER_NO eq {n}&$select=Document_Name,DocID,FileName`,
whose `FileName` plugs into `www.scc.virginia.gov/docketsearch/DOCS/{FileName}` (percent-encode `#`).

### More-states dead seams — 2026-07-10 batch 2 (MN, WI)

Two states swept for standalone utility *audit reports* for `state_audit`; both are
**structural** dead seams (the state's regulatory model doesn't produce discrete audit reports),
not effort limits — recorded so a future session doesn't re-spend a finder agent:

- **Minnesota** — MN publishes no independent management/operations/service-quality *audit* report
  of its utilities as a static `.gov` PDF. OAH-hosted PDFs (`mn.gov/oah/...`) are **ALJ rate-case
  reports** (adjudicative, excluded, already in `mn_puc.json`); the MN PUC Reliability & Service
  Standards page hosts **utility-self-filed** SRSQ reports (compliance filings, not audits); the MN
  Office of the Legislative Auditor audits state *agencies*, never the utilities; and MN eDockets
  (where a consultant/management audit would live) is WAF-walled ("Security check") to scripts.
- **Wisconsin** — WI PSC handles prudence/construction oversight *inside* CE-/UR-/FR- dockets via
  Staff/intervenor testimony, utility compliance filings, and Commission Final Decisions — not
  discrete consultant "management/construction audit" reports. The ERF search + docket-detail pages
  (`apps.psc.wi.gov/ERF/ERFsearch`, `.../APPS/dockets/.../detail.aspx`) are **Cloudflare-403** to
  scripts; only `viewdoc.aspx?docid={N}` downloads (pipeline UA), but that needs an already-known
  docid and search surfaces docids only for testimony/CPCN/intervenor letters. The Oak Creek CT
  cost-overrun generic investigation (docket 6630-CE-317) was only *opened* May 2025 — no report
  exists yet. Breaking this seam needs browser-capture (Chrome MCP) once a report lands.
