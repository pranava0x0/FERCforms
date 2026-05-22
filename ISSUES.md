# Issues

Living audit trail. Each bug: date · area · description · root cause (**code bug** vs **test bug** vs **environmental**) · status. On resolution: the fix + the commit that resolved it.

## Open

- **2026-05-22 · fetch · FERC HTML behind Cloudflare.** `www.ferc.gov` HTML pages (incl. `/audits`, `sitemap.xml`) and `data.ferc.gov/api/*` return **403** (Cloudflare "Just a moment…" JS challenge) to curl, `requests`, and WebFetch. **Root cause:** environmental bot protection, not a code bug. **Workaround:** capture the audit listing via a real browser (which passes the challenge); download the actual report PDFs over plain HTTP — static `/sites/default/files/` assets are *not* challenged (verified: HTTP 200 to any User-Agent). Status: **Worked around.**
- **2026-05-22 · env · urllib3 LibreSSL warning.** The macOS system Python 3.9 interpreter emits `NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+` because it links LibreSSL 2.8.3. **Root cause:** environmental (system Python's TLS backend). Cosmetic — `requests` works. **Mitigation:** suppress this specific warning in the CLI entry point. Status: **Open (cosmetic).**

## Fixed

_(none yet)_
