# DATA_STRUCTURE.md — the document & data model across FERC docs

How the source documents are shaped, and how this project turns them into structured data. Living document: the **schema** sections are authoritative now; the **"observed in corpus"** sections are filled in/refined as reports are actually processed.

> Status: **v1 scoped to Form 1 / electric.** The full corpus is downloaded and classified by form (`pipeline/classify.py`); the tool covers **electric (Form 1)** audits only — gas (Form 2) and oil (Form 6) are out of scope (see [BACKLOG.md](BACKLOG.md)). 2 most-recent electric reports are structured E2E.

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

Mirrors `pipeline/models.py` (Pydantic, `extra="forbid"`). v1 parses the
**Executive Summary** (the most consistent, quotable section) rather than the
long detailed sections. One audit report normalizes to:

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
```

**Observed (snapshot 2026-02-03):** 71 reports, **all** with docket + date, spanning **2019-04-23 → 2025-09-29** (the page advertises "since FY2015," but only 2019+ are currently linked). Re-running is idempotent (dedupe by `accession_number`).

### 5.1 How a report PDF is fetched

Reports are not static PDFs — each lives in **eLibrary** (an Angular SPA + IIS/F5 backend). The pipeline:

1. **GET** `https://elibrary.ferc.gov/eLibrary/filelist?accession_number={acc}&optimized=false` once to obtain the F5 `TS…` session cookie.
2. **POST** `https://elibrary.ferc.gov/eLibraryWebAPI/api/File/DownloadPDF?accesssionNumber={acc}` (note FERC's literal `accesssionNumber` typo) with the cookie, app-like headers (`Origin`, `Referer`, `X-Requested-With`, `Content-Type: application/json`), and body `{"serverLocation":""}`. The response is the **combined PDF** for the accession.

Without the cookie + headers the F5 WAF returns `Request Rejected`. See [ISSUES.md](ISSUES.md).

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

**Structured (2 electric reports, in scope):** both fully **born-digital** — 0 image-only pages, no OCR needed (PG&E 76 pp, Talen 34 pp). Header phrasing varies ("Summary of **Noncompliance Findings**" vs "Summary of **Findings of Noncompliance**"), so the parser tries several phrasings. Yielded PG&E (FA) = 8 findings / 37 recs, Talen (PA) = 3 findings / 6 recs. _(Full-corpus structuring pending — see [BACKLOG.md](BACKLOG.md).)_
