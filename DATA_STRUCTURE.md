# DATA_STRUCTURE.md — the document & data model across FERC docs

How the source documents are shaped, and how this project turns them into structured data. Living document: the **schema** sections are authoritative now; the **"observed in corpus"** sections are filled in/refined as reports are actually processed.

> Status: **all FERC utility audits — electric (Form 1), gas (Form 2), oil (Form 6), FA + PA, every available year.** The whole corpus is downloaded, classified (`pipeline/classify.py`), and structured E2E. The live ferc.gov/audits page covers 2019+; FY2014-2018 are backfilled from a Wayback snapshot (ferc.gov-origin only — see §5.2 and [ISSUES.md](ISSUES.md)).

---

## 1. Documents in scope

| Doc type | What it is | In v1? | Source |
| --- | --- | --- | --- |
| **FERC audit report** | Final report from the Office of Enforcement, Division of Audits & Accounting (DAA). Details findings of noncompliance + staff recommendations for a single audited company. | **Yes** | `ferc.gov/audits` (PDF) |
| Annual Report on Enforcement | Yearly staff report summarizing DAA/DOI activity; useful for recommendation-outcome context. | Reference only | `ferc.gov` (PDF) |
| FERC Form 1 (financial data) | Annual financial/operating report filed by major electric utilities. The thing audits scrutinize. | Future | `ferc.gov` / PUDL |

This project starts with **audit reports** because they are where FERC *names the issues* — exactly the pattern library the later "audit-my-document" tool needs.

**Two audit types, three industries.** Reports split by docket prefix into **FA = Financial Audit** and **PA = Non-Financial Audit** (FERC's own wording on ferc.gov/audits: "a 'PA' docket denotes a Non-Financial Audit (e.g. compliance or operational audits)"). FA = Chief Accountant accounting/USofA/forms compliance; PA = tariff/market/operational compliance. Audited entities span electric utilities + ISOs/RTOs (Form 1), gas pipelines (Form 2), and oil pipelines (Form 6). **v1 is scoped to electric / Form 1** (both FA and PA); `pipeline/classify.py` triages the corpus by form/statute so the electric subset can be selected. Observed (snapshot, 71 reports): ~39 electric, ~8 oil, ~4 gas.

**Functional focus (electric).** Within electric, audits target different functions — **generation** (market-based rates, generator outage / GADS reporting), **transmission** (formula rates, OATT / Attachment O), and **distribution** (wholesale distribution formula rate). `forms.detect_functions` tags this **multi-valued** (a vertically-integrated utility's audit spans transmission + distribution — e.g. PG&E). Observed across the classified electric set: **transmission ≫ generation ≫ distribution** (transmission formula-rate audits dominate; pure distribution is rare). Surfaced as the site's **Function** facet and `by_function` in patterns.

---

## 2. Anatomy of a FERC audit report (PDF)

Audit reports are born-digital PDFs (FY2015+) with a fairly stable structure. Typical sections, in order:

1. **Cover / letterhead** — title, audited company, docket number(s), issue date.
2. **Introduction** — why the audit, the audited entity, the audit period.
3. **Audit scope, objectives & methodology** — what was reviewed and how.
4. **Results of audit / Findings** — the core. Each **finding** describes an area of **noncompliance** with a regulation, tariff, or accounting requirement, usually with: a heading, the requirement cited, what the company did, and the dollar/impact where quantified.
5. **Recommendations** — staff's corrective actions, often numbered and mapped 1:1 (or n:1) to findings.
6. **Company response** — the audited entity's agreement/disagreement and remediation plan (sometimes an appendix).
7. **Appendices** — methodology detail, schedules, acronyms.

Key identifiers to capture: **company**, **docket number(s)** (e.g., `PA21-4-000`), **issue date**, **audit period**, the regulations cited (CFR parts, USofA accounts, tariff sections).

**The Executive Summary is the parse target.** It carries the report in miniature with consistent subsections — `A. Overview`, `B. <Company>`, `C. Summary of Noncompliance Findings`, (optional) `D. Summary of Other Matter`, then `Recommendations`, then `Compliance and Implementation of Recommendations`. v1 parses `C` (findings) and the Recommendations subsection (grouped under each finding title); the long detailed Section IV is left for later.

**Observed variation:** the **letter prefix shifts** when a report has no "Other Matter" — Recommendations is `E.` with Other Matter (Kern River) but `D.` without it (Medallion). The parser therefore anchors on header *text* + the "Audit staff('s) recommendations" intro, never the letter. See [ISSUES.md](ISSUES.md).

---

## 3. Structured data model

Mirrors `pipeline/models.py` (Pydantic, `extra="forbid"`). Findings are parsed
from the **Executive-Summary "Summary of Noncompliance Findings" list** where a
report has one (title + inline verbatim summary); otherwise from the **Table of
Contents "Findings and Recommendations" subsection** (titles) plus each
finding's opening body paragraph (verbatim summary). Reports whose findings
section is just "A. Conclusion" legitimately have **zero** findings. One audit
report normalizes to:

```
AuditReport
  id                str    stable slug, e.g. "2025-09-29_kern-river-..._fa23-10"
  company           str    display name (from the listing)
  company_raw       str    verbatim anchor text (provenance)
  docket            str?   short form from the listing, e.g. "FA23-10"
  docket_full       str?   full form parsed from the PDF, e.g. "FA23-10-000"
  issued_date       date?
  source_page_url   str    eLibrary filelist URL
  pdf_download_url  str    eLibraryWebAPI DownloadPDF URL
  captured_at       date
  page_count        int
  scanned_pages     [int]  pages flagged image-only
  ocr_used          bool   v1: always False (no OCR yet)
  audit_period      str?   e.g. "January 1, 2020 to December 31, 2023"
  industry          str?   "electric" | "gas" | "oil" (form + statute signals, forms.py)
  audit_type        str?   "financial" (FA) | "non-financial" (PA), from docket prefix
  functions         [str]  functional focus: generation / transmission / distribution
  forms             [str]  e.g. ["1"] for FERC Form No. 1
  finding_count     int    count of noncompliance findings (excl. other matter)
  findings          [Finding]

Finding
  index             int    order within the report (1-based)
  title             str    e.g. "Allowance for Funds Used During Construction"
  summary           str?   VERBATIM noncompliance description (never paraphrased)
  is_other_matter   bool   True for "Other Matter" items vs. noncompliance
  recommendations   [Recommendation]

Recommendation
  number            int    report-wide recommendation number
  text              str    VERBATIM recommendation text
```

Provenance is mandatory on every `AuditReport` (`source_page_url` + `captured_at`) per [CLAUDE.md](CLAUDE.md) → Data handling. Findings/recommendations are quoted verbatim from the Executive Summary; the report-level "company response" section is captured in a later pass (see [BACKLOG.md](BACKLOG.md)).

---

## 4. Finding taxonomy

There is **no separate `category` field in v1** — the finding **`title`** is the natural label and is captured verbatim. A *normalized* taxonomy (mapping many phrasings to shared buckets, e.g. "AFUDC" ⇄ "Allowance for Funds Used During Construction") is a [BACKLOG.md](BACKLOG.md) item to define from the full corpus rather than guess.

**Observed finding titles (2 reports processed so far):**

- *Kern River (gas, FA23-10):* Renewable Natural Gas Quality Specifications · Tariff Administration and Oversight · Informational Postings · Allowance for Funds Used During Construction · Annual Membership Dues · (other matter) Creditworthiness Standards
- *Medallion (oil, FA23-9):* Annual Cost of Service Based Analysis Schedule · Nonoperating and Operating Expenses · Noncarrier Property Revenue, Expenses, and Net Income · Crude Oil Accounting Misclassifications · Other Accounting Misclassifications · Property Unit Listing · Depreciation Rates and Study · FERC Form No. 6 Reporting

Even across two reports, recurring themes are visible (accounting misclassification, tariff/forms reporting, AFUDC/cost recovery) — the raw material for cross-report patterns (§ patterns stage).

_(Full-corpus title frequencies: pending — only 2 of 71 structured in v1.)_

---

## 5. The listing (seed)

`data/listing.json` is the index of audit reports — the **single seed** the pipeline runs from. It is parsed (`pipeline/listing.py`) from a saved snapshot of `ferc.gov/audits` in `data/sources/` (the live page is Cloudflare-blocked; see [ISSUES.md](ISSUES.md)). One record per report, mirroring `ListingEntry` in `pipeline/models.py`:

```
ListingEntry
  id                str   readable stable slug (date_company_docket)
  company           str   display name (anchor text, sans docket)
  company_raw       str   verbatim anchor text (provenance)
  docket            str?  e.g. "PA21-2"
  accession_number  str   unique eLibrary key, e.g. "20250410-3014"
  issued_date       date? derived from the accession (YYYYMMDD prefix)
  source_page_url   str   eLibrary filelist URL (human-facing)
  pdf_download_url  str   eLibraryWebAPI DownloadPDF URL (machine)
  captured_at       date  snapshot capture date
  source_note       str   human-readable provenance ("Listed on ferc.gov/audits …")
  archived_via      str?  Wayback snapshot URL when sourced via Internet Archive (else null)
```

**Observed:** **120 reports** spanning **2014 → 2025** (issued dates). The live page (snapshot 2026-02-03, re-verified unchanged 2026-05-25) links **71** reports, 2019-04-23 → 2025-09-29 — it advertises "since FY2015" but lists only 2019+. The other **49** (FY2014-2018) are backfilled from a Wayback snapshot — see §5.2. Re-running is idempotent (dedupe by `accession_number`; on any old-vs-new overlap the live ferc.gov entry wins).

### 5.1 How a report PDF is fetched

Reports are not static PDFs — each lives in **eLibrary** (an Angular SPA + IIS/F5 backend). The pipeline:

1. **GET** `https://elibrary.ferc.gov/eLibrary/filelist?accession_number={acc}&optimized=false` once to obtain the F5 `TS…` session cookie.
2. **POST** `https://elibrary.ferc.gov/eLibraryWebAPI/api/File/DownloadPDF?accesssionNumber={acc}` (note FERC's literal `accesssionNumber` typo) with the cookie, app-like headers (`Origin`, `Referer`, `X-Requested-With`, `Content-Type: application/json`), and body `{"serverLocation":""}`. The response is the **combined PDF** for the accession.

Without the cookie + headers the F5 WAF returns `Request Rejected`. See [ISSUES.md](ISSUES.md).

### 5.2 Listing provenance & parsing by era (FERC's page format changes over time)

FERC's audit listing has used **different link formats at different points in internet history**, so the listing is parsed *per era*. Always confirm which era a snapshot belongs to before parsing it:

| Issued years | Source of listing | Link format in the HTML | Parser | Accession source |
| --- | --- | --- | --- | --- |
| **2019 → present** | Live `ferc.gov/audits` (browser-captured; Cloudflare-blocked to scripts) | `…/eLibrary/filelist?accession_number=YYYYMMDD-####` | `pipeline/listing.py` | embedded in the anchor href |
| **2014 → 2018** | Internet Archive **Wayback** snapshot of `ferc.gov/audits` @ **2021-12-07** (`data/sources/ferc-audits-wayback-20211207.html`) | `…/idmws/common/opennat.asp?fileID=#######` — anchor text is "DOCKET Company"; **no accession in the link** | `pipeline/backfill.py` | resolved per docket via the eLibrary **Docket Search** API → final-audit-report accession, saved to `data/sources/elibrary_docket_accessions_*.json` |

**Format-change timeline observed in Wayback** (pick the right snapshot for the era you need):
- **≤ 2017 — old `.asp` site** (`ferc.gov/enforcement/audits/…`): `conducted.asp` is a *process* page, **not** a report list. Dead end for report links.
- **2021-12 snapshot**: `opennat?fileID=` links, 57 reports back to **FA14** — the source used for the FY2014-2018 backfill.
- **2022-12 onward**: switched to `filelist?accession_number=` **and dropped pre-2019 reports** (why the live page now starts at 2019).

**Why the archived link can't be downloaded directly:** the `opennat?fileID=` URL now 302-redirects to the eLibrary Angular SPA shell (no PDF bytes were archived), so the fileID is useless for download. Instead the **docket** is resolved to its eLibrary accession (recipe in [ISSUES.md](ISSUES.md)), then the normal §5.1 path fetches the PDF from live eLibrary. **Every source is ferc.gov-origin** — `backfill.py` skips any archived link whose host is not `*.ferc.gov`.

**Old-vs-new overlap (verified):** 8 dockets (FA17-1/2/4/5, FA18-2/3, PA16-2, PA18-2) appear on *both* the 2021 Wayback list and the live page. Each was tested to resolve to the **identical eLibrary accession** on both sources (same filing → byte-identical PDF; company names match line-for-line — see `data/sources/overlap_verification_20260525.json`). The backfill excludes any docket already listed live, so the **ferc.gov (live) entry always wins**.

---

## 6. On-disk layout of processed data

```
data/
  listing.json                 the seed (committed)
  raw/<id>.pdf                 downloaded PDF (gitignored)
  processed/
    classification.json        per-report form/industry/audit_type triage (scoping)
    <id>/text.json             per-page extracted text + per-page char counts
    <id>/report.json           the structured AuditReport (validated)
docs/
  index.html, css/, js/        the static site
  llms.txt                     LLM-friendly index (llmstxt.org): summary + links + overview
  llms-full.txt                full structured corpus (findings + recs, verbatim) in one file
  data/
    reports.json               structured reports the site reads (incl. per-report themes)
    patterns.json              cross-report aggregates
    meta.json                  corpus stats, build time, counts
```

`llms.txt` / `llms-full.txt` are generated by `pipeline/llmstxt.py` (invoked from `build`) so the corpus is consumable by an LLM in one fetch, not just by the human UI. Links in them are relative to the site root until a deploy domain is set (see [BACKLOG.md](BACKLOG.md)).

`docs/data/*.json` is **build output** — never hand-edited; regenerated by `pipeline build` ([AGENTS.md](AGENTS.md)).

---

## 7. Extraction notes

- **Primary:** `pdfplumber` for text + layout. **Fallback:** `PyMuPDF` (`fitz`) for pages pdfplumber mis-handles.
- **Scanned detection:** a page yielding `< MIN_TEXT_CHARS_PER_PAGE` (config) extractable chars is treated as **image-only**, recorded in `scanned_pages`, and the report's `ocr_used` is set when OCR eventually fills it. v1 does **not** OCR (no tesseract installed) — it flags. See [BACKLOG.md](BACKLOG.md).

**Classification (`pipeline/classify.py`):** scans the first ~8 pages of each PDF and scores industry from form number + governing statute (FPA→electric, NGA→gas, ICA→oil) + USofA part + tariff/ISO/RTO signals (`pipeline/forms.py`). Statute signals matter because **non-financial (PA) audits often don't cite a form number**. Observed across the snapshot corpus: ~39 electric, ~8 oil, ~4 gas, ~1 unknown.

**Structured (full corpus, all forms + years):** **120 reports** (86 electric, 17 oil, 14 gas, 3 unknown), issued 2014→2025 — all born-digital (0 image-only, no OCR). **94 have findings (599 findings, 1,505 recommendations).** The remaining 26 are either genuine clean audits ("A. Conclusion", no noncompliance) or older FY2014-2018 reports whose layout the 2019+-tuned parser doesn't yet fully read (~9-10 reports — see [ISSUES.md](ISSUES.md) "Known limitations"; the source PDF is linked on every card). Functions: transmission 67, generation 63, distribution 2. Top themes: Form reporting (68 reports), accounting misclassification (67), depreciation (40), below-the-line costs (40), property & plant records (36).

---

## 8. Beyond FERC audits — collections & the generic source path

The explorer now spans **three collections**, one per UI tab, each with its own baked stats/patterns (`docs/data/patterns_by_collection.json`):

| `collection` | Tab | Source | Structured into findings? |
| --- | --- | --- | --- |
| `ferc_audit` | **FERC Audits** | `ferc.gov/audits` (the 120-report corpus above) | **Yes** — `pipeline/structure.py` |
| `prudence_review` | **Prudence Reviews** | FERC eLibrary rate-case orders (formal challenges, fuel/cost prudence, ALJ decisions) | **No** — metadata-only |
| `state_audit` | **State PUC Audits** | State PUC/PSC/SCC audits (PA, MI, … ) | **No** — metadata-only |

`collection`, `jurisdiction`, `source`, `doc_type`, and `structured` are fields on `AuditReport`, defaulted to the original FERC-audit identity so the 120 committed reports validate unmodified.

**The generic seed (`SourceSeed`, `pipeline/sources.py`).** FERC audits seed from `data/listing.json` + the eLibrary cookie dance. Other regulators publish PDFs at stable URLs, so they seed from a simpler per-source file `data/seeds/<source>.json` — one `SourceSeed` per document: a direct `pdf_url` (or, when `accession` is set, the eLibrary DownloadPDF URL) plus full provenance (`source`, `source_page_url`, `issued_date`, `docket`, `captured_at`, `source_note`). Run `python -m pipeline.sources --seed data/seeds/<file>.json` → fetch (plain GET, or the F5 cookie dance when `accession` is set) → extract → write `data/processed/<id>/report.json`.

**Why metadata-only (`parse=False`, the default).** These documents are captured with their source link and full provenance but **not** machine-extracted into findings. FERC's executive-summary → numbered-noncompliance-findings parser does not fit:
- **FERC prudence orders** are adversarial legal opinions / ALJ initial decisions / settlements — free-form prose, no "Summary of Noncompliance Findings" list (verified across the seeded examples).
- **State PUC audits** carry findings either in **multi-column summary tables** (PA focused-audit "Finding / Conclusion / New Recommendation" grids that linearize messily) or **per-chapter prose** — heterogeneous across formats. Emitting garbled text as "verbatim" findings would break the project's [quote discipline](AGENTS.md).

The site renders metadata-only records with an honest **"Listed for reference"** state (`structured=false`) and a link to the source PDF — distinct from a genuinely finding-free audit ("No findings extracted"). A careful findings parser for the clean PA/MI management-audit subset (per-chapter "Findings, Conclusions, and Recommendations" prose + recommendation tables, gated by a no-regression snapshot like the FERC parser) is a [BACKLOG.md](BACKLOG.md) item.

**Seeded so far.** State (PA: 4 PA PUC Bureau of Audits management/focused audits 2022–2025; MI: 4 Liberty Consulting U-21305 distribution audits of Consumers + DTE, 2024). Prudence (FERC eLibrary formal-challenge orders + an ALJ initial decision, 2015–2025). Access notes per regulator (which are scriptable vs. WAF-blocked) live in [ISSUES.md](ISSUES.md).
