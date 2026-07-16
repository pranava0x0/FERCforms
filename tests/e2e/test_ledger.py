"""Spec A3: the Ledger view. Acceptance: "ledger sorts"."""
from __future__ import annotations

import pytest

FERC_TOTAL = 123


@pytest.fixture
def ledger_page(page_factory):
    return page_factory(hash_="#/ferc_audit?view=ledger")


def test_ledger_renders_from_a_url_and_hides_the_stream(ledger_page):
    assert ledger_page.is_visible("#ledger")
    assert ledger_page.locator("#stream").is_hidden()
    assert (
        ledger_page.evaluate("document.querySelector('.view-btn[data-view=\"ledger\"]').getAttribute('aria-pressed')")
        == "true"
    )


def test_ledger_header_has_a_column_per_definition(ledger_page):
    """The header iterates LEDGER_COLUMNS (DESIGN.md §12.4) — if someone adds a
    cell without a header, this catches the drift."""
    headers = ledger_page.locator("#ledger-head th").count()
    cells = ledger_page.locator("#ledger-body tr").first.locator("td").count()
    assert headers == cells


def test_ledger_pages_rather_than_rendering_everything(ledger_page):
    """The sentinel must sit AFTER the table. Anchored above it, it intersects
    immediately and pages the whole result set in one go."""
    assert ledger_page.locator("#ledger-body tr").count() <= 60


def test_scrolling_reaches_every_row(ledger_page):
    prev = -1
    for _ in range(20):
        ledger_page.mouse.wheel(0, 40000)
        ledger_page.wait_for_timeout(250)
        n = ledger_page.locator("#ledger-body tr").count()
        if n == prev and n >= FERC_TOTAL:
            break
        prev = n
    assert ledger_page.locator("#ledger-body tr").count() == FERC_TOTAL


def test_ledger_sorts(ledger_page):
    """The spec's stated acceptance for A3."""
    ledger_page.select_option("#sort", "company")
    ledger_page.wait_for_timeout(400)
    names = ledger_page.locator("#ledger-body .lg-co").all_inner_texts()
    assert names[:20] == sorted(names[:20], key=str.casefold)


def test_row_click_returns_to_the_stream_and_deep_links_the_card(ledger_page):
    """The ledger is for FINDING the row; the verbatim thread lives in the stream."""
    rid = ledger_page.locator("#ledger-body tr").first.get_attribute("data-id")
    ledger_page.locator("#ledger-body tr").first.click()
    ledger_page.wait_for_timeout(700)
    assert ledger_page.is_visible("#stream")
    assert ledger_page.locator("#ledger").is_hidden()
    assert ledger_page.evaluate(f"document.getElementById('r-{rid}').open") is True
    h = ledger_page.evaluate("location.hash")
    assert f"open={rid}" in h and "view=ledger" not in h


def test_ledger_with_an_open_id_does_not_render_the_whole_result_set(page_factory):
    """REGRESSION (2026-07-16, code review). `revealOpenReport` paged until it
    found `#r-<id>`; the ledger renders <tr> rows, so that element never appears
    and the loop ran to exhaustion — 123 of 123 rows, B1 paging defeated with no
    error. Reachable, not theoretical: opening a card then clicking Ledger used to
    leave `open=` in the URL (see the test below), so a reload hit exactly this.
    """
    p = page_factory(hash_="#/ferc_audit?view=ledger")
    rid = p.evaluate("state.reports.filter(r=>r.collection==='ferc_audit')[0].id")
    p2 = page_factory(hash_=f"#/ferc_audit?view=ledger&open={rid}")
    p2.wait_for_timeout(700)
    assert p2.locator("#ledger-body tr").count() <= 60


def test_switching_to_the_ledger_drops_the_open_report(page_factory):
    """The ledger has no expandable row, so it must not carry an `open` id it
    can't represent — that stale URL is what fed the full-render bug above."""
    p = page_factory()
    p.locator("#stream .card summary").first.click()
    p.wait_for_timeout(500)
    assert "open=" in p.evaluate("location.hash")
    p.click('.view-btn[data-view="ledger"]')
    p.wait_for_timeout(500)
    h = p.evaluate("location.hash")
    assert "view=ledger" in h and "open=" not in h, f"stale open= survived into the ledger: {h}"


def test_a_hand_written_ledger_open_url_is_canonicalised(page_factory):
    """Belt and braces: even if someone types the combination, it must not persist."""
    p = page_factory(hash_="#/ferc_audit?view=ledger")
    rid = p.evaluate("state.reports.filter(r=>r.collection==='ferc_audit')[0].id")
    p2 = page_factory(hash_=f"#/ferc_audit?view=ledger&open={rid}")
    p2.wait_for_timeout(600)
    assert "open=" not in p2.evaluate("location.hash")


def test_below_the_breakpoint_a_ledger_link_still_honours_open(page_factory):
    """`open` is only meaningless where the ledger actually renders. On a phone the
    view falls back to the stream, so a shared ledger link must still land on its
    report rather than silently dropping it."""
    p = page_factory(width=375, height=812, hash_="#/ferc_audit?view=ledger")
    rid = p.evaluate("state.reports.filter(r=>r.collection==='ferc_audit')[0].id")
    p2 = page_factory(width=375, height=812, hash_=f"#/ferc_audit?view=ledger&open={rid}")
    p2.wait_for_timeout(800)
    assert p2.evaluate(f"document.getElementById('r-{rid}')?.open") is True


def test_ledger_fits_without_horizontal_scroll(page_factory):
    """A ledger you scroll sideways to read defeats its own purpose. Both the
    desktop and tablet widths must fit."""
    for width in (1280, 768):
        p = page_factory(width=width, hash_="#/ferc_audit?view=ledger")
        m = p.evaluate(
            """(() => { const t=document.querySelector('.ledger'), w=document.querySelector('.ledger-wrap');
                 return { overflows: t.scrollWidth > w.clientWidth + 1 }; })()"""
        )
        assert not m["overflows"], f"ledger overflows its container at {width}px"


def test_resetting_filters_keeps_the_view_toggle_selected(page_factory):
    """REGRESSION (2026-07-16, Codex review). resetFilters() cleared EVERY
    `[aria-pressed="true"]` in the document, including the view toggle — so after
    a reset the ledger kept rendering while both Stream and Ledger reported
    unpressed, leaving the current mode unselected visually and for a screen
    reader. Reset is about facets; it has no business touching the view."""
    p = page_factory(hash_="#/ferc_audit?view=ledger&theme=Depreciation")
    p.click("#reset-filters")
    p.wait_for_timeout(500)
    assert p.is_visible("#ledger"), "reset should not change the view"
    pressed = p.evaluate(
        "Object.fromEntries([...document.querySelectorAll('.view-btn')].map(b=>[b.dataset.view,b.getAttribute('aria-pressed')]))"
    )
    assert pressed == {"stream": "false", "ledger": "true"}, pressed


def test_resizing_into_the_ledger_drops_the_open_report(page_factory):
    """REGRESSION (2026-07-16, Codex review). Crossing the breakpoint is a THIRD
    way into the ledger, and it lacked the toggle's cleanup: a `view=ledger` link
    opened on a phone renders the stream, where a card can be opened — resizing up
    then showed the ledger while `open` stayed in the URL, unrepresentable there
    and reopening unexpectedly on the way back down."""
    p = page_factory(width=375, height=812, hash_="#/ferc_audit?view=ledger")
    p.locator("#stream .card summary").first.click()
    p.wait_for_timeout(500)
    assert "open=" in p.evaluate("location.hash")   # legitimate: the stream is live here

    p.set_viewport_size({"width": 1280, "height": 900})
    p.wait_for_timeout(700)
    assert p.is_visible("#ledger")
    assert "open=" not in p.evaluate("location.hash"), "an unrepresentable open= survived the resize"


def test_the_skip_link_targets_a_visible_container_in_both_views(page_factory):
    """REGRESSION (2026-07-16, Codex review). The skip link pointed at #stream,
    which is display:none in Ledger view — a keyboard user skipping to results
    landed on a hidden element."""
    for hash_ in ("#/ferc_audit", "#/ferc_audit?view=ledger"):
        p = page_factory(hash_=hash_)
        target = p.get_attribute(".skip-link", "href").lstrip("#")
        assert p.locator(f"#{target}").is_visible(), f"skip target #{target} is hidden at {hash_}"
        # and it must be able to hold focus, or the link scrolls but Tab returns to the header
        assert p.evaluate("t => document.getElementById(t).hasAttribute('tabindex')", target)


def test_ledger_is_dense(ledger_page):
    """Density is the entire justification for this view (F8: ~6 cards/screen)."""
    h = ledger_page.evaluate("document.querySelector('#ledger-body tr').getBoundingClientRect().height")
    assert h <= 40, f"row height {h}px — the ledger has stopped being a ledger"


def test_mobile_falls_back_to_the_stream_with_no_ledger_dom(page_factory):
    """One renderer per viewport class — never two DOM trees (DESIGN.md §6)."""
    p = page_factory(width=375, height=812, hash_="#/ferc_audit?view=ledger")
    assert p.is_visible("#stream")
    assert p.locator("#ledger").is_hidden()
    assert p.locator("#view-toggle").is_hidden()
    assert p.locator("#ledger-body tr").count() == 0
