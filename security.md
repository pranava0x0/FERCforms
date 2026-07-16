# Security & Supply-Chain Log

Per [CLAUDE.md](CLAUDE.md) → "Check advisories before any package install / upgrade."

## Advisory sweeps

| Date (UTC) | Source | Result |
| --- | --- | --- |
| 2026-07-16 | https://pranava0x0.github.io/vibe-coding-security/llms-ctx.txt | Reviewed (index generated 2026-07-15). **One new DEV-only dependency added: `playwright==1.58.0`** in the new `requirements-dev.txt`, for `tests/e2e/` (the analyst-UX spec's acceptance criteria, which need a browser that actually paints — see AGENTS.md). Already present in the environment; no install was performed. **No advisory listed for playwright**, nor for any existing dependency (pdfplumber, PyMuPDF, pydantic, requests, pandas, beautifulsoup4, lxml, pytest). The index's dev-tooling entries (Nx Console extension compromise; the Miasma / Mini Shai-Hulud / IronWorm npm+PyPI worm campaigns) name none of this project's packages. Note `playwright` pulls a browser binary via `playwright install` — a real supply-chain surface, which is why it is dev-only and `requirements.txt` (what the pipeline and CI need) is unchanged. |
| 2026-06-02 | https://pranava0x0.github.io/vibe-coding-security/llms-ctx.txt | Reviewed (70 KB index, generated 2026-06-01). **No new packages installed this session** (multi-source expansion, parser, docs, and a corpus provenance audit — all on the existing deps). No listed advisory matches this project's dependency set (pdfplumber, PyMuPDF, pydantic, requests, pandas, beautifulsoup4, lxml, pytest). |
| 2026-05-22 | https://pranava0x0.github.io/vibe-coding-security/llms-ctx.txt | Reviewed (47 KB index). **No new packages installed this session** — every dependency (pdfplumber, PyMuPDF, pydantic, requests, pandas, beautifulsoup4, lxml, pytest) was already present in the environment. No listed advisory matches this project's dependency set. |

**Last updated:** 2026-07-16 — refresh before any `pip install` if older than 7 days.

## Dependency posture

- **Zero new installs for v1.** The pipeline runs on libraries already in the system Python 3.9 environment; versions are pinned in `requirements.txt`.
- **No secrets.** No API keys, tokens, or credentials are used or stored. The pipeline reads only public FERC PDFs.
- **Egress is allowlisted in code.** Downloads are restricted to `www.ferc.gov/sites/default/files/` (see `pipeline/config.py` → `FILES_PREFIX`).

## Notes

- FERC HTML pages are behind a Cloudflare JS challenge. The audit *listing* is captured via a real browser session — **no auth bypass, no tokens, no challenge-solving**. The PDF assets themselves are public and unchallenged.
- If OCR is added later (tesseract + pytesseract — see BACKLOG.md), run a fresh advisory sweep first and record it in the table above.
