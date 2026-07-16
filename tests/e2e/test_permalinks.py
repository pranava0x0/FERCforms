"""Spec A1 acceptance, verbatim:

  "reload restores exact view; opening a shared link scrolls to + expands the
   report; copy-citation includes the permalink; site_browser back/forward walks
   filter states."

The codec's own round-trip is unit-tested in tests/test_urlstate.py; this file
tests the BINDING — that the app actually reads and writes it.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def clipboard_page(site_browser, site_url):
    """A site_page allowed to read the clipboard, for the Copy-* CTAs."""
    ctx = site_browser.new_context(
        viewport={"width": 1280, "height": 900},
        permissions=["clipboard-read", "clipboard-write"],
    )
    site_page = ctx.new_page()
    errors: list[str] = []
    site_page.on("pageerror", lambda e: errors.append(str(e)))
    site_page.goto(site_url, wait_until="networkidle")
    site_page.wait_for_timeout(350)
    yield site_page
    ctx.close()
    assert not errors, f"uncaught site_page errors: {errors}"


def _deep_id(site_page, index=86):
    """A report well past the 20-card first site_page — the case that breaks naive
    deep-linking, because the card doesn't exist in the DOM yet."""
    return site_page.evaluate(
        "i => state.reports.filter(r=>r.collection==='ferc_audit')"
        ".sort((a,b)=>(b.issued_date||'').localeCompare(a.issued_date||''))[i].id",
        index,
    )


def test_filters_are_written_to_the_url(site_page):
    site_page.click('.pattern-card[data-value="Depreciation"]')
    site_page.wait_for_timeout(400)
    assert "theme=Depreciation" in site_page.evaluate("location.hash")
    site_page.select_option("#sort", "amount")
    site_page.wait_for_timeout(300)
    assert "sort=amount" in site_page.evaluate("location.hash")


def test_reload_restores_the_exact_view(site_page):
    site_page.click('.pattern-card[data-value="Depreciation"]')
    site_page.wait_for_timeout(400)
    site_page.select_option("#sort", "amount")
    site_page.wait_for_timeout(300)
    before = site_page.locator("#result-count").inner_text()

    site_page.reload(wait_until="networkidle")
    site_page.wait_for_timeout(500)

    assert site_page.locator("#result-count").inner_text() == before
    assert site_page.input_value("#sort") == "amount"
    assert site_page.evaluate(
        "!!document.querySelector('.pattern-card[data-value=\"Depreciation\"][aria-pressed=\"true\"]')"
    ), "the restored view shows a filtered stream above an un-pressed facet"


def test_back_and_forward_walk_filter_states(site_page):
    site_page.click('.pattern-card[data-value="Depreciation"]')
    site_page.wait_for_timeout(400)
    themed = site_page.locator("#result-count").inner_text()

    site_page.go_back()
    site_page.wait_for_timeout(400)
    assert site_page.evaluate("location.hash") in ("", "#/ferc_audit")
    assert site_page.locator("#result-count").inner_text() != themed  # back to unfiltered

    site_page.go_forward()
    site_page.wait_for_timeout(400)
    assert "theme=Depreciation" in site_page.evaluate("location.hash")
    assert site_page.locator("#result-count").inner_text() == themed


def test_deep_link_pages_expands_and_scrolls_to_a_report(page_factory, site_page):
    """An `open=` id can be card #87 of 123 — the pager hasn't rendered it yet."""
    rid = _deep_id(site_page)
    p = page_factory(hash_=f"#/ferc_audit?open={rid}")
    p.wait_for_timeout(700)
    card = p.locator(f"#r-{rid}")
    assert card.count() == 1, "the deep-linked card was never rendered"
    assert p.evaluate(f"document.getElementById('r-{rid}').open") is True
    p.wait_for_selector(f"#r-{rid} .thread", timeout=5000)
    assert p.evaluate("window.scrollY") > 200, "did not scroll to the report"


def test_findings_carry_stable_anchors(page_factory, site_page):
    rid = _deep_id(site_page)
    p = page_factory(hash_=f"#/ferc_audit?open={rid}")
    p.wait_for_selector(f"#r-{rid} .thread", timeout=5000)
    ids = p.evaluate(f"[...document.querySelectorAll('#r-{rid} .finding[id]')].map(n=>n.id)")
    assert ids and all(i.startswith(f"f-{rid}-") for i in ids)


def test_a_stale_open_id_does_not_hang_or_throw(page_factory):
    """Old links outlive the corpus; an unknown id must be a no-op, not a spin."""
    p = page_factory(hash_="#/ferc_audit?open=not-a-real-report-id")
    p.wait_for_timeout(600)
    assert p.locator("#stream .card").count() == 20  # normal first site_page
    assert p.locator("#result-count").inner_text().startswith("123 report")


def test_copy_citation_includes_the_permalink(clipboard_page):
    rid = _deep_id(clipboard_page, index=0)
    clipboard_page.locator("#stream .card summary").first.click()
    clipboard_page.wait_for_selector(".thread-footer", timeout=5000)
    clipboard_page.click(f"#r-{rid} .thread-footer button:has-text('Copy citation')")
    clipboard_page.wait_for_timeout(300)
    cite = clipboard_page.evaluate("navigator.clipboard.readText()")
    assert f"open={rid}" in cite, "a citation without its permalink can't be re-found"
    assert "http" in cite


def test_copy_link_yields_the_permalink(clipboard_page):
    rid = _deep_id(clipboard_page, index=0)
    clipboard_page.locator("#stream .card summary").first.click()
    clipboard_page.wait_for_selector(".thread-footer", timeout=5000)
    clipboard_page.click(f"#r-{rid} .thread-footer button:has-text('Copy link')")
    clipboard_page.wait_for_timeout(300)
    link = clipboard_page.evaluate("navigator.clipboard.readText()")
    assert link.endswith(f"#/ferc_audit?open={rid}")
