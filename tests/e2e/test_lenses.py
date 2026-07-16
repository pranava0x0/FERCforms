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
