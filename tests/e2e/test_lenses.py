"""Spec A5 (theme drill-down) + A4 (company lens).

A5 acceptance: "theme URL reload restores panel + filter; panel stats match
patterns.json." The stats check is the important one — a panel whose numbers
disagree with the baked data is worse than no panel, because it looks
authoritative.
"""
from __future__ import annotations

import json
import urllib.request

import pytest


@pytest.fixture(scope="module")
def ferc_patterns(request):
    # site_url is session-scoped; fetch the same file the page reads.
    url = request.getfixturevalue("site_url")
    raw = urllib.request.urlopen(url + "data/patterns_by_collection.json").read()
    return json.loads(raw)["ferc_audit"]


@pytest.fixture
def dep(ferc_patterns):
    return next(t for t in ferc_patterns["themes"] if t["theme"] == "Depreciation")


@pytest.fixture
def theme_page(page_factory):
    return page_factory(hash_="#/ferc_audit?theme=Depreciation")


def test_theme_url_restores_panel_and_filter(theme_page):
    assert theme_page.is_visible("#theme-panel")
    assert theme_page.locator(".tp-title").inner_text() == "Depreciation"
    assert theme_page.evaluate(
        "!!document.querySelector('.pattern-card[data-value=\"Depreciation\"][aria-pressed=\"true\"]')"
    )


def test_panel_stats_match_patterns_json(theme_page, dep):
    nums = theme_page.locator(".tp-num").all_inner_texts()
    assert int(nums[0]) == dep["report_count"]
    assert int(nums[1]) == dep["finding_count"]


def test_panel_sparkline_reconciles_with_report_count(theme_page, dep):
    """One bar per year, and the bars sum to the headline count printed beside them."""
    labels = theme_page.evaluate(
        "[...document.querySelectorAll('.spark-col')].map(n => n.getAttribute('aria-label'))"
    )
    assert len(labels) == len(dep["by_year"])
    total = sum(int(s.split(": ")[1].split(" ")[0]) for s in labels)
    assert total == dep["report_count"]


def test_stream_is_narrowed_to_the_theme(theme_page, dep):
    assert theme_page.locator("#result-count").inner_text().startswith(f"{dep['report_count']} report")


def test_panel_top_companies_match_the_bake(theme_page, dep):
    assert theme_page.locator(".tp-co").all_inner_texts() == [c["company"] for c in dep["top_companies"]]


def test_panel_hides_when_two_themes_are_active(page_factory):
    """With two themes the stream is an OR across them, so one theme's stats would
    describe a different set than the one on screen."""
    p = page_factory(hash_="#/ferc_audit?theme=Depreciation&theme=Property%20%26%20plant%20records")
    assert p.locator("#theme-panel").is_hidden()


def test_clicking_a_top_company_filters_and_lands_in_the_url(theme_page, dep):
    first = dep["top_companies"][0]["company"]
    theme_page.locator(".tp-co").first.click()
    theme_page.wait_for_timeout(500)
    chips = theme_page.evaluate("[...document.querySelectorAll('.active-chip')].map(n=>n.textContent)")
    assert any(first in c for c in chips)
    assert "company=" in theme_page.evaluate("location.hash")


def test_company_facet_renders_and_searches_within(site_page):
    assert site_page.locator("#company-options .filter-chip").count() > 0
    site_page.fill("#company-search", "duke")
    site_page.wait_for_timeout(300)
    shown = site_page.locator("#company-options .filter-chip").all_inner_texts()
    assert shown and all("duke" in c.lower() for c in shown)


def test_enter_in_the_company_facet_does_not_reload_the_page(page_factory):
    """REGRESSION (2026-07-16, Codex review). The filter rail is a <form> for its
    fieldset/legend semantics; adding "Find a company…" made it the only text input
    in that form, so Enter triggered IMPLICIT form submission and reloaded the
    document — throwing away the entire filtered view. There is no server here;
    nothing in this form should ever submit."""
    p = page_factory(hash_="#/ferc_audit?theme=Depreciation")
    navigations: list[str] = []
    p.on("framenavigated", lambda f: navigations.append(f.url))
    p.fill("#company-search", "duke")
    p.press("#company-search", "Enter")
    p.wait_for_timeout(800)
    assert not navigations, f"Enter navigated away: {navigations}"
    assert p.evaluate("location.hash") == "#/ferc_audit?theme=Depreciation"


def test_an_active_company_chip_stays_pressed_while_typing_in_the_facet(site_page):
    """REGRESSION (2026-07-16, Codex review). renderCompanyFacet rebuilds every
    chip on each keystroke, and chip() hardcoded aria-pressed="false" — so the
    selected company announced itself as unselected while the stream stayed
    filtered and the active-filter bar still named it."""
    company = site_page.evaluate("state.reports.filter(r => r.collection === 'ferc_audit')[0].company")
    site_page.evaluate("c => { state.filters.company = new Set([c]); applyFilters(); syncControlsToState(); }", company)
    site_page.wait_for_timeout(300)
    site_page.fill("#company-search", company.split()[0].lower())
    site_page.wait_for_timeout(400)
    pressed = site_page.evaluate(
        """c => { const el = [...document.querySelectorAll('#company-options .filter-chip')]
                    .find(n => n.dataset.value === c);
                  return el && el.getAttribute('aria-pressed'); }""",
        company,
    )
    assert pressed == "true"


def test_reset_clears_the_company_facet_query(site_page):
    """REGRESSION (2026-07-16, Codex review). Reset cleared the selected company
    but left the facet's own search box, so renderCompanyFacet kept hiding
    everything that didn't match the stale text — a reset tab showed an EMPTY
    Company rail (measured: 0 chips) until the user cleared that box separately."""
    site_page.fill("#company-search", "zzznomatch")
    site_page.wait_for_timeout(300)
    assert site_page.locator("#company-options .filter-chip").count() == 0
    site_page.click("#reset-filters")
    site_page.wait_for_timeout(500)
    assert site_page.input_value("#company-search") == ""
    assert site_page.locator("#company-options .filter-chip").count() > 0


def test_more_on_company_row_deep_links_across_collections(site_page, page_factory):
    """A4's cross-collection counts — computed from the index at runtime, which is
    why cross_links.json was retired."""
    repeat = site_page.evaluate(
        """(() => { const c={}; state.reports.forEach(r=>c[r.company]=(c[r.company]||0)+1);
             const [name] = Object.entries(c).sort((a,b)=>b[1]-a[1])[0];
             const r = state.reports.find(x=>x.company===name);
             return {name, id:r.id, collection:r.collection}; })()"""
    )
    p = page_factory(hash_=f"#/{repeat['collection']}?open={repeat['id']}")
    p.wait_for_selector(f"#r-{repeat['id']} .thread", timeout=5000)
    assert p.locator(f"#r-{repeat['id']} .more-on").count() == 1
    assert p.locator(f"#r-{repeat['id']} .more-link").count() > 0
