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

`data/listing.json` is the browser-captured index of audit reports. One record per report:

```
ListingEntry
  company        str   as shown on ferc.gov/audits
  docket         str?
  issued_date    str?  as shown (normalized downstream)
  source_url     str   PDF URL (the /sites/default/files/... asset)
  captured_at    str   date the listing was captured
```

This is the **single seed** the pipeline runs from. Re-running `fetch` from it is idempotent (dedupe by `source_url`).

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
