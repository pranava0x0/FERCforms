"""Search behaviour (A11) — including the regression that shipped and was caught.

The race below is the reason this file exists: it passed every unit test, and only
a real browser with a slow network showed it.
"""
from __future__ import annotations


def test_search_matches_finding_bodies_from_the_lazy_detail_file(site_page):
    """Search has to await findings_<collection>.json. "lobbying" appears in
    finding text but in no company/docket, so a non-zero count proves the lazy
    file was fetched and searched."""
    site_page.fill(".hero .search-input", "lobbying")
    site_page.wait_for_timeout(800)
    n = int(site_page.locator("#result-count").inner_text().split()[0])
    assert n > 0


def test_search_matches_company_and_docket(site_page):
    site_page.fill(".hero .search-input", "Kern River")
    site_page.wait_for_timeout(800)
    assert site_page.locator("#result-count").inner_text().startswith("1 report")
    site_page.fill(".hero .search-input", "FA24-3")
    site_page.wait_for_timeout(800)
    assert site_page.locator("#result-count").inner_text().startswith("1 report")


def test_search_matches_the_short_docket_a_card_actually_prints(page_factory):
    """REGRESSION (2026-07-16, Codex review). matches() searched `docket_full`
    only — but 199 of 440 records (nearly every state one) carry a `docket` and no
    `docket_full`, and `docket` is exactly what their card prints. So searching a
    docket the user could see returned 0 results while the hero promised "Search a
    utility, docket, or keyword". The FERC-docket test above passed throughout,
    because FERC records DO have docket_full — the false confidence is the point.
    """
    p = page_factory(hash_="#/state_audit")
    # Take a real docket off a real record: no docket_full, so only `docket` can match.
    docket = p.evaluate(
        """(() => (state.reports.find(r => r.collection === 'state_audit'
              && r.docket && !r.docket_full) || {}).docket)()"""
    )
    assert docket, "fixture drift: no state_audit record with a short-only docket"
    p.fill(".hero .search-input", docket)
    p.wait_for_timeout(900)
    n = int(p.locator("#result-count").inner_text().split()[0])
    assert n >= 1, f"searching the printed docket {docket!r} found nothing"


def test_back_cancels_a_queued_search(page_factory):
    """REGRESSION (2026-07-16, Codex review). The popstate handler restored URL
    state without cancelling a pending search, so a query awaiting its detail
    fetch landed after the restore and dragged the user back into the search they
    had just navigated away from — it passes the collection guard whenever Back
    stays on the same tab."""
    p = page_factory()
    p.route("**/findings_*.json", lambda route: (p.wait_for_timeout(1500), route.continue_()))
    p.click('.pattern-card[data-value="Depreciation"]')
    p.wait_for_timeout(500)
    p.fill(".hero .search-input", "gas")
    p.wait_for_timeout(200)          # armed, mid-fetch
    p.go_back()
    p.wait_for_timeout(2500)         # let any stale run land
    assert p.input_value(".hero .search-input") == ""
    assert "q=gas" not in p.evaluate("location.hash")


def test_no_match_shows_the_honest_empty_state(site_page):
    site_page.fill(".hero .search-input", "zzzznomatch")
    site_page.wait_for_timeout(800)
    assert site_page.locator("#result-count").inner_text().startswith("0 report")
    assert site_page.is_visible("#empty-state")
    site_page.click("#empty-reset")
    site_page.wait_for_timeout(400)
    assert site_page.locator("#result-count").inner_text().startswith("123 report")


def test_queued_search_does_not_apply_to_another_tab(page_factory, site_url, site_browser):
    """REGRESSION (2026-07-16, found in code review, reproduced here).

    The debounced handler awaits a detail-file fetch, so a queued search can land
    seconds later — after the user has switched tabs. It used to re-apply itself
    to the NEW tab: State PUC Audits rendered 33 of its 82 reports with a phantom
    "gas" chip while the search box read empty, and because the awaited details
    belonged to the OLD collection the query silently degraded to index-only
    matching. Throttling the detail fetch makes the window deterministic.
    """
    site_page = page_factory()
    site_page.route(
        "**/findings_*.json",
        lambda route: (site_page.wait_for_timeout(1500), route.continue_()),
    )

    site_page.click('[data-collection="state_rate_case"]')
    site_page.wait_for_timeout(300)
    site_page.fill(".hero .search-input", "gas")
    site_page.wait_for_timeout(200)          # past the 150ms debounce, inside the fetch
    site_page.click('[data-collection="state_audit"]')
    site_page.wait_for_timeout(2500)         # let any stale run land

    total = site_page.evaluate("state.reports.filter(r=>r.collection==='state_audit').length")
    assert site_page.evaluate("document.querySelector('.tab[aria-selected=\"true\"]').dataset.collection") == "state_audit"
    assert site_page.input_value(".hero .search-input") == ""
    assert site_page.locator(".active-chip").count() == 0, "a phantom search chip survived the tab switch"
    assert site_page.locator("#result-count").inner_text().startswith(f"{total} report")


def test_reset_cancels_a_queued_search(page_factory):
    """Same class as above, via Reset filters rather than a tab switch."""
    site_page = page_factory()
    site_page.route(
        "**/findings_*.json",
        lambda route: (site_page.wait_for_timeout(1200), route.continue_()),
    )
    site_page.click('[data-collection="state_audit"]')
    site_page.wait_for_timeout(300)
    site_page.fill(".hero .search-input", "gas")
    site_page.wait_for_timeout(200)
    site_page.click("#reset-filters")
    site_page.wait_for_timeout(2000)
    assert site_page.locator(".active-chip").count() == 0
    assert site_page.input_value(".hero .search-input") == ""
