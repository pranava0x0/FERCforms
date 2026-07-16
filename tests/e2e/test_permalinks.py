"""Spec A1 acceptance, verbatim:

  "reload restores exact view; opening a shared link scrolls to + expands the
   report; copy-citation includes the permalink; browser back/forward walks
   filter states."

The codec's own round-trip is unit-tested in tests/test_urlstate.py; this file
tests the BINDING — that the app actually reads and writes it.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def clipboard_page(site_browser, site_url):
    """A page allowed to read the clipboard, for the Copy-* CTAs."""
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
    assert not errors, f"uncaught page errors: {errors}"


def _deep_id(site_page, index=86):
    """A report well past the 20-card first page — the case that breaks naive
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


def test_a_fresh_load_does_not_push_a_history_entry(site_browser, site_url):
    """REGRESSION (2026-07-16, code review). `applyUrlState` reset the URL-write
    suppression flag to `false` in its `finally` instead of restoring the previous
    value — but it runs INSIDE `withUrlSuppressed`, so the `applyFilters()` right
    after it saw writes re-armed and pushed. On a fresh load `location.hash` is ""
    while `encode()` yields "#/ferc_audit", so they differed and pushState fired:
    history.length went 1 -> 3 for one navigation, and Back left the user on the
    same page instead of leaving the site.

    Canonicalising the URL at load is correct — doing it with pushState is not.
    """
    page = site_browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto("about:blank")
    before = page.evaluate("history.length")
    page.goto(site_url, wait_until="networkidle")
    page.wait_for_timeout(600)
    after = page.evaluate("history.length")
    assert page.evaluate("location.hash") == "#/ferc_audit"   # still canonicalised
    assert after - before == 1, (
        f"a fresh load added {after - before} history entries; the navigation itself "
        "is the only one it may add (the load-time canonicalise must replaceState)"
    )
    page.close()


def test_the_open_report_survives_a_rerender(site_page):
    """REGRESSION (2026-07-16, Codex review). renderStream rebuilds every card on
    any filter/sort change, so the open card was silently replaced by a closed one
    while `state.open` and the URL still said it was open — the permalink stopped
    describing the page it pointed at.

    Filters to the report's own company so it stays on the first rendered page:
    that isolates the rebuild bug from paging (a report re-sorted to position ~120
    legitimately isn't in the DOM yet — see the test below for that half).
    """
    site_page.locator("#stream .card summary").first.click()
    site_page.wait_for_timeout(500)
    rid = site_page.evaluate("state.open")
    company = site_page.evaluate("id => state.reports.find(r => r.id === id).company", rid)
    assert rid and company

    site_page.evaluate("c => { state.filters.company = new Set([c]); applyFilters(); }", company)
    site_page.wait_for_timeout(700)

    assert site_page.evaluate("id => !!document.getElementById('r-'+id)?.open", rid) is True, (
        "the rebuilt card came back closed while the URL still said it was open"
    )
    assert f"open={rid}" in site_page.evaluate("location.hash")


def test_an_open_report_paged_away_reopens_when_its_card_is_rebuilt(site_page):
    """The other half of the rebuild fix: when a re-sort moves the open report past
    the first page it is legitimately not in the DOM, but it must come back OPEN
    once the pager reaches it — not silently closed."""
    site_page.locator("#stream .card summary").first.click()   # newest
    site_page.wait_for_timeout(500)
    rid = site_page.evaluate("state.open")
    site_page.select_option("#sort", "oldest")                 # -> moves to the end
    site_page.wait_for_timeout(600)
    assert f"open={rid}" in site_page.evaluate("location.hash")  # still in the result set

    for _ in range(20):
        site_page.mouse.wheel(0, 40000)
        site_page.wait_for_timeout(220)
        if site_page.evaluate("id => !!document.getElementById('r-'+id)", rid):
            break
    site_page.wait_for_timeout(400)
    assert site_page.evaluate("id => !!document.getElementById('r-'+id)?.open", rid) is True


def test_an_open_report_filtered_out_stops_claiming_to_be_open(site_page):
    """The other half: if the new filters exclude it, the URL must let it go
    rather than advertise a report the page no longer shows."""
    site_page.locator("#stream .card summary").first.click()
    site_page.wait_for_timeout(500)
    assert "open=" in site_page.evaluate("location.hash")
    site_page.fill(".hero .search-input", "zzzznomatch")
    site_page.wait_for_timeout(900)
    assert "open=" not in site_page.evaluate("location.hash")


def test_more_on_company_is_one_history_entry(site_page, page_factory):
    """REGRESSION (2026-07-16, Codex review). The click changed collection and
    called resetFilters() — whose applyFilters() pushed an UNFILTERED destination
    tab — before pushing the intended company-filtered state. Two entries for one
    click, so Back landed on an unrelated unfiltered tab instead of the report the
    user came from."""
    rep = site_page.evaluate(
        """(() => { const c={}; state.reports.forEach(r=>c[r.company]=(c[r.company]||0)+1);
             const [n]=Object.entries(c).sort((a,b)=>b[1]-a[1])[0];
             const r=state.reports.find(x=>x.company===n); return {id:r.id, col:r.collection}; })()"""
    )
    p = page_factory(hash_=f"#/{rep['col']}?open={rep['id']}")
    p.wait_for_selector(".more-link", timeout=5000)
    before = p.evaluate("history.length")
    p.locator(".more-link").first.click()
    p.wait_for_timeout(800)
    assert p.evaluate("history.length") - before == 1, "one navigation must be one history entry"
    assert "company=" in p.evaluate("location.hash")
    p.go_back()
    p.wait_for_timeout(700)
    assert f"open={rep['id']}" in p.evaluate("location.hash"), "Back must return to the originating report"


def test_a_stale_open_id_does_not_hang_or_throw(page_factory):
    """Old links outlive the corpus; an unknown id must be a no-op, not a spin."""
    p = page_factory(hash_="#/ferc_audit?open=not-a-real-report-id")
    p.wait_for_timeout(600)
    assert p.locator("#stream .card").count() == 20  # normal first page
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
