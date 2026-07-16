"""Spec flow F-A + the mobile ergonomics (B3) and touch rules the project calls
non-negotiable (CLAUDE.md / DESIGN.md §7, §9).

F-A acceptance: "first meaningful click available without scrolling on mobile".
"""
from __future__ import annotations

import pytest

WIDTHS = [(375, 812, "mobile"), (768, 1024, "tablet"), (1280, 800, "desktop")]


def _box(site_page, sel):
    return site_page.evaluate(
        """sel => { const e = document.querySelector(sel); if (!e) return null;
             const r = e.getBoundingClientRect();
             return {top: r.top, bottom: r.bottom, h: r.height, w: r.width}; }""",
        sel,
    )


def test_search_and_trust_line_are_above_the_fold_at_375(page_factory):
    """The F-A test: a cold visitor reaches value without scrolling."""
    p = page_factory(width=375, height=812)
    assert _box(p, ".trust-line")["bottom"] < 812
    assert _box(p, ".hero .search-input")["bottom"] < 812


def test_mobile_controls_are_fixed_not_scroll_away(page_factory):
    """F9: from card #10 the Filters toggle used to be unreachable."""
    p = page_factory(width=375, height=812)
    assert p.evaluate("getComputedStyle(document.querySelector('.stream-toolbar')).position") == "fixed"


@pytest.mark.parametrize("sel", ["#filters-toggle", "#to-top", ".sort-select"])
def test_touch_targets_meet_44px_at_375(page_factory, sel):
    p = page_factory(width=375, height=812)
    box = _box(p, sel)
    assert box and box["h"] >= 44, f"{sel} is {box and box['h']}px — under the 44px floor"


@pytest.mark.parametrize("sel", [".sort-select", ".view-btn"])
def test_toolbar_controls_are_touch_targets_on_tablet_too(page_factory, sel):
    """640-1023 is treated as touch by this design (the rail becomes a slide-in),
    so toolbar controls need a full target there, not just on phones.

    REGRESSION for `.view-btn`, which shipped at 36px and was visible at 768px —
    right beside the sort control this same test had always held to 44px.
    """
    p = page_factory(width=768, height=1024)
    box = _box(p, sel)
    assert box and box["h"] >= 44, f"{sel} is {box and box['h']}px at 768 — under the 44px floor"


def test_new_navigation_controls_are_touch_targets(page_factory):
    """`.more-link` (32px) and `.tp-co` (unsized) are navigation, not the compact
    filter chips ISSUES.md grants a sub-44 exception to."""
    p = page_factory(width=375, height=812, hash_="#/ferc_audit?theme=Depreciation")
    p.wait_for_timeout(400)
    assert _box(p, ".tp-co")["h"] >= 44

    repeat = p.evaluate(
        """(() => { const c={}; state.reports.filter(r=>r.collection==='ferc_audit')
             .forEach(r=>c[r.company]=(c[r.company]||0)+1);
             const hit = Object.entries(c).sort((a,b)=>b[1]-a[1])[0][0];
             const r = state.reports.find(x=>x.collection==='ferc_audit' && x.company===hit);
             return r.id; })()"""
    )
    p2 = page_factory(width=375, height=812, hash_=f"#/ferc_audit?open={repeat}")
    p2.wait_for_selector(f"#r-{repeat} .thread", timeout=5000)
    if p2.locator(".more-link").count():
        assert _box(p2, ".more-link")["h"] >= 44


@pytest.mark.parametrize("width,height,name", WIDTHS)
def test_no_horizontal_page_scroll(page_factory, width, height, name):
    p = page_factory(width=width, height=height)
    assert not p.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    ), f"the page scrolls horizontally at {name} ({width}px)"


def test_tablet_filters_slide_in_from_the_left(page_factory):
    """B3: a bottom sheet feels phone-y at 768px and hides the stream it filters."""
    p = page_factory(width=768, height=1024)
    p.click("#filters-toggle")
    p.wait_for_timeout(400)
    box = p.evaluate(
        """(() => { const r = document.getElementById('filters').getBoundingClientRect();
             return {x: Math.round(r.x), y: Math.round(r.y), h: Math.round(r.height)}; })()"""
    )
    assert box["x"] == 0 and box["y"] == 0, f"tablet filter panel is not a left slide-in: {box}"


def test_card_sub_meta_never_wraps_mid_phrase(page_factory):
    """F9: "Issued ⏎ September 29, 2025". Each segment is atomic; wrapping happens
    BETWEEN segments."""
    p = page_factory(width=375, height=812)
    assert p.evaluate(
        "[...document.querySelectorAll('#stream .sub-bit')].every(n => getComputedStyle(n).whiteSpace === 'nowrap')"
    )
