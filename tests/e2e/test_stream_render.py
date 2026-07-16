"""Spec B1/B2: incremental paging + lazily-fetched finding bodies.

This is the file that cannot be replaced by an MCP-pane check: IntersectionObserver
callbacks never fire in a hidden tab, so the pager reads as "stuck at 20 cards"
there regardless of whether it works. See conftest.
"""
from __future__ import annotations

FERC_TOTAL = 123  # reports on the default tab; also asserted against the UI's own count


def _cards(site_page):
    return site_page.locator("#stream .card").count()


def test_first_paint_renders_one_page_and_no_threads(site_page):
    """20 cards, 0 threads — the whole point of the split payload (F4/F5).

    A regression here (all 123 cards, or threads built up front) is invisible to
    the eye and only shows up as jank on a mid-range device.
    """
    assert _cards(site_page) == 20
    assert site_page.locator("#stream .thread").count() == 0
    assert site_page.locator("#result-count").inner_text().startswith(f"{FERC_TOTAL} report")


def test_result_count_is_exact_despite_paging(site_page):
    """Filtering is whole-corpus; only the DOM append is chunked. The count must
    describe the RESULT SET, not what happens to be rendered."""
    rendered = _cards(site_page)
    counted = int(site_page.locator("#result-count").inner_text().split()[0])
    assert counted == FERC_TOTAL
    assert rendered < counted  # i.e. the count is not just "what's on screen"


def test_scrolling_reaches_every_report(site_page):
    """The load-bearing one: 103 of 123 reports are unreachable if the sentinel
    or the observer lifecycle breaks."""
    prev = -1
    for _ in range(20):
        site_page.mouse.wheel(0, 40000)
        site_page.wait_for_timeout(250)
        n = _cards(site_page)
        if n == prev and n >= FERC_TOTAL:
            break
        prev = n
    assert _cards(site_page) == FERC_TOTAL


def test_sentinel_retires_when_everything_is_rendered(site_page):
    for _ in range(20):
        site_page.mouse.wheel(0, 40000)
        site_page.wait_for_timeout(200)
        if _cards(site_page) >= FERC_TOTAL:
            break
    site_page.wait_for_timeout(300)
    assert site_page.evaluate("document.getElementById('stream-sentinel').hidden") is True


def test_expanding_a_card_lazily_builds_its_thread(site_page):
    """Finding bodies live in findings_<collection>.json, fetched on first open."""
    site_page.locator("#stream .card summary").first.click()
    site_page.wait_for_selector("#stream .card .thread", timeout=5000)
    card = site_page.locator("#stream .card").first
    assert card.locator(".finding, .no-findings").count() > 0
    assert site_page.locator(".thread-pending").count() == 0  # no stuck "Loading…"


def test_first_paint_does_not_fetch_the_full_corpus(site_page):
    """reports.json (1.9 MB) must stay the DOWNLOAD, not the runtime payload (F5).

    Watches a reload rather than the initial load, because the fixture navigates
    before the test can attach a listener.
    """
    requested: list[str] = []
    site_page.on("request", lambda r: requested.append(r.url))
    site_page.reload(wait_until="networkidle")
    site_page.wait_for_timeout(300)
    assert any("reports_index.json" in u for u in requested), "the index was not fetched"
    assert not any(u.endswith("/data/reports.json") for u in requested), (
        "the full corpus was fetched at first paint — the payload split has regressed"
    )
