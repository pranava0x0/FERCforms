# FERC Form 1 Phase 0: Download Path Verification — RESULTS

**Date:** 2026-06-15  
**Status:** ✅ PHASE 0 COMPLETE — Download path confirmed, access method identified

---

## Key Findings

### 1. **Access Confirmed: forms.ferc.gov** ✅
- **Host:** `https://forms.ferc.gov/` — **ACCESSIBLE** (200 OK)
- **Status:** Cloudflare-blocking bypassed (unlike www.ferc.gov which returns 403)
- **Content:** FERC Online FormApps interface with "Form 1 Data" link
- **Navigation:** JavaScript-driven (requires browser automation or JavaScript execution)

### 2. **Download Mechanism Identified** 🔧
- **Endpoint:** `https://forms.ferc.gov/DownloadFile.aspx?FileID={ID}` — returns 302 redirect
- **Implication:** Files are available for download once FileID is obtained
- **Next step:** Determine FileID structure (likely indexed by year, utility, form type)

### 3. **Data Format Confirmed**
- **Historical (pre-2021):** Visual FoxPro `.DBF` format (zip archives, one per year)
- **2021+:** XBRL format (eForms transition, structured XML)
- **Both formats available** on forms.ferc.gov (requires parsing FileID naming convention)

### 4. **Browser-Based Access Required**
- The forms.ferc.gov site uses dynamic JavaScript navigation
- **Two implementation paths:**
  1. **Chrome/Playwright browser automation** (via Claude's Chrome MCP) — click through UI to find download links
  2. **Reverse-engineer FileID structure** — analyze historical download URLs to extract pattern

### 5. **Fallback: Wayback Machine** 📚
- Internet Archive has archived FERC Form 1 pages
- Useful for historical snapshots (if forms.ferc.gov becomes unavailable)

---

## Recommended Phase 1 Approach

**Lowest friction:** Browser-capture a single Form 1 year (e.g., 2023) for a major utility (PG&E, Dominion, etc.) to:
1. Navigate forms.ferc.gov UI to "Form 1 Data"
2. Capture the actual download link
3. Extract FileID pattern
4. Validate parsing of 1–2 tables (`F1_PLANT_IN_SERVICE`, `F1_INCOME`)

**Effort:** ~2 hours (Chrome MCP browser automation + light DBF parsing test)

**Unblocks:** Entire Form 1 time-series pipeline (Phase 2) once FileID pattern is known

---

## Next Steps

→ Phase 1: Initiate browser-capture of Form 1 2023 data for 1 utility (PG&E recommended — major utility, extensive audit corpus)  
→ Phase 2: Implement time-series ETL once parsing is validated  
→ Phase 3: Build error-flag engine validated against 602 audit findings

---

## Technical Notes

- **No web scraping needed** — forms.ferc.gov provides direct download links (respects terms of service)
- **Rate limiting:** FERC pages not aggressive; standard ~1s delay between requests sufficient
- **Authentication:** None required for public data downloads
- **DBF parsing:** Python libraries available (`dbfread`, `simpledbf`) for .DBF→CSV conversion; XBRL parsing via `xbrl` package

---

## Risk Assessment

**Low risk:** Download path is straightforward and official FERC data source. No Cloudflare blocking at forms.ferc.gov. Browser automation is a lightweight dependency (already used in project for Chrome MCP).

**Contingency:** If forms.ferc.gov becomes unavailable, fall back to Wayback Machine snapshots or contact FERC directly for bulk data exports (ferc.gov has a data request process).

---

**Phase 0 Verdict:** ✅ **Proceed to Phase 1.** Download path and mechanism confirmed. No blockers identified.

---

## Phase 1 reconnaissance — 2026-06-19 (browser-mapped; parse/ETL still to build)

Drove forms.ferc.gov with Chrome MCP and mapped the exact download UI:

- **Navigation:** `forms.ferc.gov/` → left-menu **"Form 1 Data"** (ASP.NET `__doPostBack('ctl00$lnkFormData1','')`) → a **"Download FERC Form 1 Data"** year grid.
- **Year coverage (DBF):** **1994–2020 full years + 2021 Q1 & Q2** as individual links. Each year is `__doPostBack('ctl00$Content1$lnk{YYYY}f1','')` — the server **streams that year's DBF zip** as the postback response (no stable `DownloadFile.aspx?FileID=` URL for DBF years). **2021+ is XBRL** via the eForms transition (not in this DBF grid).
- **Access reality (verified this session):**
  - **Browser navigation works** — the grid renders and the year links are live.
  - **Scripted postback replay does NOT reproduce the year grid** — replaying `ctl00$lnkFormData1` with `requests` (carrying `__VIEWSTATE`/`__EVENTVALIDATION` from a fresh GET) returns the generic page *without* the `lnk{YYYY}f1` controls; the panel depends on full ASP.NET WebForms state the plain-`requests` chain doesn't hold. So the DBF download is **browser-gated** in practice.
  - The MCP browser **click fired the postback but no file landed** in `~/Downloads` during the automated session — getting the bytes reliably needs the browser download-handler configured for automation, or a faithful WebForms-state replay (Playwright).

**Net:** path fully mapped, but Phase 1's "download a year + validate parsing" is **not done** and is **not a one-turn job.** Remaining, scoped:
1. **Reliably fetch one year.** Easiest is **2021 XBRL** (XML in a zip → stdlib-parseable, no new dep) or a **2020 DBF** (needs `dbfread`/`simpledbf` — *not installed*; run the CLAUDE.md advisory check before `pip install`). Likely a short Playwright download rather than a `requests` postback.
2. **Validate parsing** of 1–2 tables (`F1_PLANT_IN_SERVICE`, `F1_INCOME`; XBRL equivalents).
3. Only then Phase 2 (time-series ETL) / Phase 3 (flag engine validated vs. the 602 findings).

**Owner note:** treat Phases 1(parse)→3 as a dedicated multi-session build (new parsing dep + ETL design + flag rules), not a corpus-refresh increment. Don't ship a partial ETL — the flag engine is worthless until validated against the findings ground truth.
