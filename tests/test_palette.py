"""Design-token guards over docs/css/styles.css (spec C1; DESIGN.md §3, §9).

Two rules that are easy to state and easy to break silently:

1. Every text/background pair clears WCAG AA (4.5:1) in BOTH themes. The C1
   palette moves several semantic hues at once, so a manual spot-check doesn't
   scale — this is the "extend the manual check into a tiny script" the spec asks
   for. A failure prints the measured ratio, so tuning a token is a one-line loop.
2. No hardcoded hex outside the token blocks. DESIGN.md §3: "never hardcode a hex
   outside :root" — a stray `color: #fff` is invisible in light mode and unreadable
   in dark (that is exactly how `.pill.solid` shipped white-on-periwinkle).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS_PATH = Path(__file__).resolve().parent.parent / "docs" / "css" / "styles.css"
CSS = CSS_PATH.read_text(encoding="utf-8")

AA_NORMAL = 4.5
AA_LARGE = 3.0  # >=18.66px bold or >=24px normal (WCAG 1.4.3)


# ---------- token parsing ----------
def _block(selector: str) -> str:
    """The body of the first `selector { ... }` rule."""
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\n\}", CSS, re.S)
    assert m, f"{selector} block not found in styles.css"
    return m.group(1)


def _tokens(selector: str) -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", _block(selector)))


LIGHT = _tokens(":root")
DARK = {**LIGHT, **_tokens('[data-theme="dark"]')}  # dark overrides a subset


# ---------- WCAG maths ----------
def _rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _luminance(hex_color: str) -> float:
    def chan(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (chan(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    a, b = _luminance(fg), _luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


# ---------- the pairs the UI actually renders ----------
# (foreground token, background token, minimum, what renders it)
PAIRS: list[tuple[str, str, float, str]] = [
    ("--text", "--bg", AA_NORMAL, "body copy on the page"),
    ("--text", "--surface", AA_NORMAL, "card copy"),
    ("--text", "--surface-2", AA_NORMAL, "thread KV grid, inputs"),
    ("--text-muted", "--bg", AA_NORMAL, "band notes, footer"),
    ("--text-muted", "--surface", AA_NORMAL, "card sub-meta, outline stamps"),
    ("--text-muted", "--surface-2", AA_NORMAL, "KV labels, func stamps"),
    ("--accent", "--bg", AA_NORMAL, "links on the page"),
    ("--accent", "--surface", AA_NORMAL, "links/buttons on cards"),
    ("--accent-hover", "--surface", AA_NORMAL, "hovered link"),
    ("--accent-hover", "--accent-weak", AA_NORMAL, "active chip + selected tab label"),
    # The brand mark is an SVG icon, not text → WCAG 1.4.11 non-text contrast (3:1).
    # Text on --accent-weak must use --accent-hover (the pair above); --accent
    # itself lands at 4.40:1 there, which is why the selected tab uses -hover.
    ("--accent", "--accent-weak", AA_LARGE, "brand-mark pylon icon (non-text)"),
    ("--status-finding", "--surface", AA_NORMAL, "finding stamp outline text"),
    ("--status-rec", "--surface", AA_NORMAL, "recommendation number + text"),
    ("--status-resolved", "--surface", AA_NORMAL, "resolved marker"),
    ("--on-status", "--status-finding", AA_NORMAL, "FILLED cost-to-customers stamp"),
    ("--on-status", "--status-resolved", AA_NORMAL, "filled resolved stamp"),
    ("--on-accent", "--accent", AA_NORMAL, "skip link, mobile sheet Done button"),
    ("--bg", "--text", AA_NORMAL, "the solid findings-count stamp (ink plate)"),
    ("--text", "--accent-weak", AA_NORMAL, "header gradient band copy"),
]


@pytest.mark.parametrize("fg,bg,minimum,what", PAIRS, ids=[f"{p[0]}-on-{p[1]}" for p in PAIRS])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_contrast_pairs(theme: str, fg: str, bg: str, minimum: float, what: str):
    tokens = LIGHT if theme == "light" else DARK
    assert fg in tokens, f"{fg} missing from {theme} tokens"
    assert bg in tokens, f"{bg} missing from {theme} tokens"
    ratio = contrast(tokens[fg], tokens[bg])
    assert ratio >= minimum, (
        f"{theme}: {fg} ({tokens[fg]}) on {bg} ({tokens[bg]}) = {ratio:.2f}:1, "
        f"needs {minimum}:1 — renders {what}"
    )


def test_categorical_family_present_in_both_themes():
    """Charts need 5 category tokens that don't borrow the semantic palette."""
    for theme, tokens in (("light", LIGHT), ("dark", DARK)):
        for i in range(1, 6):
            assert f"--cat-{i}" in tokens, f"{theme}: --cat-{i} missing"


def test_categorical_colors_are_distinct():
    """Even-spaced hues — if two categories collide, the chart lies."""
    for theme, tokens in (("light", LIGHT), ("dark", DARK)):
        cats = [tokens[f"--cat-{i}"].lower() for i in range(1, 6)]
        assert len(set(cats)) == 5, f"{theme}: duplicate categorical colors {cats}"


def test_no_hardcoded_hex_outside_token_blocks():
    """DESIGN.md §3: colors live on :root, with a [data-theme] override.

    A literal hex in a component rule can't be themed — it looks fine in the
    theme it was written for and breaks in the other one.
    """
    css = CSS
    for selector in (":root", '[data-theme="dark"]'):
        css = css.replace(_block(selector), "")
    offenders = []
    for i, line in enumerate(css.splitlines(), 1):
        code = line.split("/*")[0]
        if re.search(r"#[0-9a-fA-F]{3,8}\b", code):
            offenders.append(f"  {line.strip()}")
    assert not offenders, (
        "hardcoded hex outside the token blocks (use a var(--token)):\n" + "\n".join(offenders)
    )


def test_semantic_hues_are_distant_from_brand():
    """F15: rec-blue at 212° read as the 240° brand accent at pill/dot size.

    Guard the fix by asserting hue distance, not the specific hex — the point is
    that "staff recommendation" must never look like brand chrome.
    """
    import colorsys

    for theme, tokens in (("light", LIGHT), ("dark", DARK)):
        def hue(tok: str) -> float:
            r, g, b = _rgb(tokens[tok])
            return colorsys.rgb_to_hls(r, g, b)[0] * 360

        brand = hue("--accent")
        for tok in ("--status-finding", "--status-rec", "--status-resolved"):
            d = abs(hue(tok) - brand)
            d = min(d, 360 - d)  # circular
            assert d >= 45, (
                f"{theme}: {tok} hue is {d:.0f}° from the brand accent — too close; "
                "semantic color must not read as brand (DESIGN.md §3.1, spec F15)"
            )
