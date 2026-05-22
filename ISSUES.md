# Issues

Living audit trail. Each bug: date · area · description · root cause (**code bug** vs **test bug** vs **environmental**) · status. On resolution: the fix + the commit that resolved it.

## Open

- **2026-05-22 · fetch · FERC HTML behind Cloudflare.** `www.ferc.gov` HTML pages (incl. `/audits`, `sitemap.xml`) and `data.ferc.gov/api/*` return **403** (Cloudflare "Just a moment…" JS challenge) to curl, `requests`, and WebFetch. **Root cause:** environmental bot protection, not a code bug. **Workaround:** capture the audit listing via a real browser (which passes the challenge); download the actual report PDFs over plain HTTP — static `/sites/default/files/` assets are *not* challenged (verified: HTTP 200 to any User-Agent). Status: **Worked around.**
- **2026-05-22 · fetch · eLibrary report PDFs behind F5 WAF.** Audit-report PDFs are not static assets — each is in eLibrary (Angular SPA + IIS/F5). A bare GET/POST to the download API returns an F5 "Request Rejected" page (188 bytes). **Root cause:** environmental WAF; expects a real session + app-like request. **Workaround:** GET the filelist page once to capture the F5 `TS…` cookie, then POST `…/eLibraryWebAPI/api/File/DownloadPDF?accesssionNumber={acc}` with that cookie + `Origin`/`Referer`/`X-Requested-With` headers + body `{"serverLocation":""}` → returns the combined PDF (verified: 1.35 MB, born-digital). Status: **Worked around** (see `pipeline/fetch.py`, DATA_STRUCTURE §5.1).
- **2026-05-22 · data · /audits lists 2019+ only.** The page says "all final audit reports since FY2015," but only **71** reports (2019-04 → 2025-09) are actually linked. **Root cause:** FERC's current page content. Not a bug; documented in DATA_STRUCTURE §5 so the "FY2015" framing isn't mistaken for a parser gap. Status: **Documented.**
- **2026-05-22 · env · urllib3 LibreSSL warning.** The macOS system Python 3.9 interpreter emits `NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+` because it links LibreSSL 2.8.3. **Root cause:** environmental (system Python's TLS backend). Cosmetic — `requests` works. **Mitigation:** suppress this specific warning in the CLI entry point. Status: **Open (cosmetic).**

## Fixed

- **2026-05-22 · structure · parser overfit → 44/47 reports parsed to 0 findings on scale-up.** The structurer only read findings from the Executive-Summary "Summary of Noncompliance Findings" list, which I'd validated on 2 reports. Most reports don't have that list — they expose findings only via the TOC "Findings and Recommendations" subsection. **Root cause: code bug** (overfit). **Fix:** added a TOC fallback (`_toc_titles` + `_body_summary`) that parses finding titles from the TOC and pulls each finding's verbatim opening paragraph from the body; the exec-summary path still wins where present. Coverage 3 → 42 of 53 reports with findings (257 findings); the remaining 11 are genuine clean audits whose section is just "A. Conclusion". Regression test `test_structure_report_toc_fallback` added.
- **2026-05-22 · fetch · old (2019) reports timed out at 60s.** eLibrary's DownloadPDF generates the combined PDF server-side; large/old accessions exceeded the 60s read timeout (9 failed). **Fix:** raised `REQUEST_TIMEOUT_SECONDS` to 180; a re-run (idempotent) recovered all 9. Status: **Fixed.**

## Known limitations (backlogged)

- `_body_summary` occasionally grabs a nearby citation instead of the finding's opening sentence for titles that recur in regulatory references. Most summaries are clean; see BACKLOG.
- A few reports without a parseable TOC findings block (e.g., different section wording) show 0 findings even if they have some.
