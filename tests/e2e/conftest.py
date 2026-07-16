"""Fixtures for the end-to-end suite: a real static server + a real browser.

WHY THIS EXISTS (do not replace it with an MCP browser pane): both MCP browser
surfaces render the page in a HIDDEN tab — `document.visibilityState === "hidden"`
with requestAnimationFrame never firing — and Chrome suspends rAF *and*
IntersectionObserver callbacks for non-rendered documents. Anything gated on the
page actually painting (the B1 pager, lazy detail loading, scroll behaviour) looks
catastrophically broken there even when it is correct. Playwright renders for
real. See AGENTS.md → "Verifying changes".

These tests serve `docs/` exactly as GitHub Pages does — the committed
`docs/data/*.json` are the fixtures, so a stale bake fails here rather than in
production.

Skipping is deliberate and total: no playwright, no browser binary, or no baked
data => the whole directory is skipped, never failed. `pytest` stays one command
for contributors who don't want a browser (`pip install -r requirements-dev.txt`
plus `python3 -m playwright install chromium` opts in).
"""
from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"

# Collection-time guards. Anything missing skips the directory rather than
# erroring, so the default `pytest` run stays green on a bare checkout.
collect_ignore_glob: list[str] = []
try:
    import playwright.sync_api  # noqa: F401
except ImportError:  # pragma: no cover - environment-dependent
    collect_ignore_glob = ["test_*.py"]
if not (DOCS / "data" / "reports_index.json").exists():  # pragma: no cover
    collect_ignore_glob = ["test_*.py"]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler that doesn't spam the test output."""

    def log_message(self, fmt, *args):  # noqa: D102
        pass


@pytest.fixture(scope="session")
def site_url():
    """Serve docs/ on an ephemeral port, the way GitHub Pages serves it."""
    handler = functools.partial(_QuietHandler, directory=str(DOCS))
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler) as httpd:
        httpd.daemon_threads = True
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{httpd.server_address[1]}/"
        httpd.shutdown()


@pytest.fixture(scope="session")
def site_browser():
    """Named `site_browser`, not `browser`, on purpose.

    pytest-playwright (if installed) already publishes `browser`/`page`/`context`
    fixtures. Naming ours the same would silently SHADOW them, so a reader can't
    tell which one a test gets, and deleting ours would hand tests a differently
    configured browser that never visits the site. Distinct names, no ambiguity.
    """
    from playwright.sync_api import Error as PWError
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except PWError as e:  # browser binary not fetched
            pytest.skip(f"chromium unavailable ({e}); run: python3 -m playwright install chromium")
        yield b
        b.close()


@pytest.fixture
def page_factory(site_browser, site_url):
    """Make pages at a chosen viewport; fails the test on any uncaught page error.

    A silent JS exception is exactly the class of bug these tests exist to catch,
    so it is never allowed to pass quietly.
    """
    pages, errors = [], []

    def make(width=1280, height=900, color_scheme="light", hash_=""):
        page = site_browser.new_page(
            viewport={"width": width, "height": height}, color_scheme=color_scheme
        )
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(site_url + hash_, wait_until="networkidle")
        page.wait_for_timeout(350)
        pages.append(page)
        return page

    yield make
    for p in pages:
        p.close()
    assert not errors, f"uncaught page errors: {errors}"


@pytest.fixture
def site_page(page_factory):
    """The common case: a desktop page at the site root."""
    return page_factory()
