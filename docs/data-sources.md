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
