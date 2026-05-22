# DATA_STRUCTURE.md — the document & data model across FERC docs

How the source documents are shaped, and how this project turns them into structured data. Living document: the **schema** sections are authoritative now; the **"observed in corpus"** sections are filled in/refined as reports are actually processed.

> Status: **initial.** Schema reflects the planned Pydantic models in `pipeline/models.py`. Empirical sections marked _(pending extraction)_ are populated after the first reports run through `extract` + `structure`.

---

## 1. Documents in scope

| Doc type | What it is | In v1? | Source |
| --- | --- | --- | --- |
| **FERC audit report** | Final report from the Office of Enforcement, Division of Audits & Accounting (DAA). Details findings of noncompliance + staff recommendations for a single audited company. | **Yes** | `ferc.gov/audits` (PDF) |
| Annual Report on Enforcement | Yearly staff report summarizing DAA/DOI activity; useful for recommendation-outcome context. | Reference only | `ferc.gov` (PDF) |
| FERC Form 1 (financial data) | Annual financial/operating report filed by major electric utilities. The thing audits scrutinize. | Future | `ferc.gov` / PUDL |

This project starts with **audit reports** because they are where FERC *names the issues* — exactly the pattern library the later "audit-my-document" tool needs.

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

_(Observed structural variations across the corpus: pending extraction.)_

---

## 3. Structured data model

Mirrors `pipeline/models.py` (Pydantic, `extra="forbid"`). One audit report normalizes to:

```
AuditReport
  id                str    stable slug, e.g. "2025-southern-company-pa21-4"
  company           str    title-cased display name
  company_raw       str    verbatim source casing (provenance)
  docket_numbers    [str]  e.g. ["PA21-4-000"]
  issued_date       date?  report issue date (null -> "Not stated")
  audit_period      str?   e.g. "2019-01-01 .. 2021-12-31" or free text
  source_url        str    the FERC PDF URL
  captured_at       date   when we downloaded it
  page_count        int
  ocr_used          bool   true if any page needed OCR (image-only)
  scanned_pages     [int]  page numbers flagged as image-only
  summary           str?   report's own scope/conclusion (verbatim excerpt)
  findings          [Finding]

Finding
  id                str    "<report_id>#f<N>"
  index             int    order within the report
  heading           str    the finding's title/heading
  text              str    VERBATIM finding text (never paraphrased)
  category          str?   controlled-vocab tag (see §4; null until taxonomy lands)
  regulations       [str]  cited authorities (CFR, USofA account, tariff §)
  amount_usd        float? quantified impact, if stated
  page_ref          int?   source page in the PDF
  recommendations   [Recommendation]

Recommendation
  id                str    "<finding_id>r<M>"
  text              str    VERBATIM recommendation text
  company_response  str?   audited entity's response, if present
```

Provenance is mandatory on every `AuditReport` (`source_url`, `captured_at`) per [CLAUDE.md](CLAUDE.md) → Data handling.

---

## 4. Finding taxonomy (controlled vocabulary)

`category` is intentionally **null in v1** — assigning it is a [BACKLOG.md](BACKLOG.md) item (needs the corpus to define honest buckets, not guesses). Candidate buckets seeded from FERC's known recurring audit themes, to validate against real data:

- Accounting / USofA misclassification
- Capitalization vs. expense
- Formula-rate inputs & true-ups
- Affiliate / intercompany transactions
- Cost allocation
- Executive compensation & incentive comp recovery
- Below-the-line / non-recoverable costs
- Records retention & internal controls

_(Actual category frequencies: pending extraction + tagging.)_

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
  processed/<id>/
    text.json                  per-page extracted text + per-page char counts
    report.json                the structured AuditReport (validated)
docs/data/
  reports.json                 array of structured reports the site reads
  patterns.json                cross-report aggregates
  meta.json                    corpus stats, build time, counts
```

`docs/data/*.json` is **build output** — never hand-edited; regenerated by `pipeline build` ([AGENTS.md](AGENTS.md)).

---

## 7. Extraction notes

- **Primary:** `pdfplumber` for text + layout. **Fallback:** `PyMuPDF` (`fitz`) for pages pdfplumber mis-handles.
- **Scanned detection:** a page yielding `< MIN_TEXT_CHARS_PER_PAGE` (config) extractable chars is treated as **image-only**, recorded in `scanned_pages`, and the report's `ocr_used` is set when OCR eventually fills it. v1 does **not** OCR (no tesseract installed) — it flags. See [BACKLOG.md](BACKLOG.md).

_(Corpus extraction stats — counts, scanned-page rate, parse failures: pending extraction.)_
