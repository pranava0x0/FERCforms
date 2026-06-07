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
- **OK — Oklahoma Corporation Commission · imaging URLs need harvesting (deferred).** OCC case files are PDFs at `imaging.occ.ok.gov/AP/CaseFiles/occ{NNNNNNNN}.pdf` (`.ok.gov` ✓), but the doc-id form indexed by search **404s** (stale ids / the imaging app rewrites them) — the live ids must be harvested from the OCC case-search (PUD/cause lookup) before seeding. On-theme: OG&E / PSO **Fuel Cost Adjustment** + the **2021 Winter Storm Uri** securitization/prudence causes. **NY — DPS DMM** (`documents.dps.ny.gov`, `.ny.gov` ✓) and **NE — `psc.nebraska.gov`** are unprobed next targets; NY serves PDFs via `ViewDoc.aspx?DocRefId={guid}` (harvest the guid from the matter's document list).

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
