"""Round-trip guard for the URL-state codec (docs/js/urlstate.js; spec A1).

The codec is the pure half of permalinks, so it is worth a real test — a silent
encode/decode asymmetry means shared citations quietly resolve to the wrong view,
which is the one failure this feature cannot have.

It's JS, and this repo has no JS test runner (and shouldn't grow one — no build
step, no framework). So: drive it through `node`, which urlstate.js supports via
its module.exports branch, and assert from pytest so there stays exactly ONE
command that runs the suite. Skips if node is absent rather than failing the run.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
URLSTATE = REPO / "docs" / "js" / "urlstate.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _node(script: str):
    """Run a JS snippet with urlstate.js required as `U`; return its JSON stdout."""
    prelude = f"const U = require({str(URLSTATE)!r});\n"
    proc = subprocess.run(
        ["node", "-e", prelude + script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"node failed:\n{proc.stderr}"
    return json.loads(proc.stdout or "null")


def test_module_exports_the_codec():
    api = _node("console.log(JSON.stringify(Object.keys(U)))")
    assert set(api) == {"DEFAULTS", "FILTER_GROUPS", "emptyState", "encode", "decode"}


def test_default_state_encodes_to_bare_collection():
    """A pristine view must not carry noise — the link people share is the short one."""
    out = _node("console.log(JSON.stringify(U.encode(U.emptyState())))")
    assert out == "#/ferc_audit"


def test_decode_of_empty_or_garbage_is_the_default_view():
    """This runs on whatever a user pasted; it must never throw."""
    for hash_in in ["", "#", "#/", "nonsense", "#not-a-path", "#/%%%", "#/x?%zz=1"]:
        out = _node(f"console.log(JSON.stringify(U.decode({hash_in!r}).collection))")
        assert out in ("ferc_audit", "x", ""), f"{hash_in!r} decoded to {out!r}"


def test_state_round_trips_through_encode_decode():
    """decode(encode(s)) == s for a fully-populated view (spec A1 acceptance)."""
    out = _node(
        """
        const s = U.emptyState();
        s.collection = 'state_audit';
        s.filters.theme = ['Depreciation', 'AFUDC / cost of capital'];
        s.filters.year = ['2024', '2023'];
        s.filters.industry = ['electric'];
        s.filters.impact = ['cost_to_customers'];
        s.filters.search = 'gas & oil';
        s.sort = 'amount';
        s.view = 'ledger';
        s.open = '2025-07-25_duke-energy-progress_fa23-6';
        const back = U.decode(U.encode(s));
        // arrays come back sorted (canonical), so compare as sets
        const norm = (x) => ({...x, filters: Object.fromEntries(
          Object.entries(x.filters).map(([k, v]) => [k, Array.isArray(v) ? v.slice().sort() : v]))});
        console.log(JSON.stringify({ same: JSON.stringify(norm(back)) === JSON.stringify(norm(s)), back: norm(back) }));
        """
    )
    assert out["same"], f"round-trip lost state: {out['back']}"


def test_finding_rides_as_routed_state_not_a_bare_anchor():
    """A "#f-<report>-<n>" anchor would collide with this app's own routing (the
    fragment IS the route), so the finding target must live inside the query."""
    out = _node(
        """
        const s = U.emptyState();
        s.open = 'rep-1'; s.finding = 3;
        const enc = U.encode(s);
        console.log(JSON.stringify({ enc, back: U.decode(enc).finding }));
        """
    )
    assert out["enc"] == "#/ferc_audit?open=rep-1&finding=3"
    assert out["back"] == 3


def test_finding_is_dropped_without_an_open_report():
    """A finding index is meaningless on its own — it addresses a position INSIDE
    a report, so it must not survive encode or decode without one."""
    out = _node(
        """
        const s = U.emptyState(); s.finding = 3;   // no open
        console.log(JSON.stringify({
          enc: U.encode(s),
          decoded: U.decode('#/ferc_audit?finding=3').finding,
        }));
        """
    )
    assert "finding" not in out["enc"]
    assert out["decoded"] is None


@pytest.mark.parametrize("raw", ["0", "-1", "abc", "1.5", "", "99999999999999999999"])
def test_a_junk_finding_index_never_reaches_the_app(raw):
    """Decoding runs on whatever a user pasted; a non-positive-integer index must
    become None rather than an id the DOM lookup would silently miss."""
    out = _node(
        f"console.log(JSON.stringify(U.decode('#/ferc_audit?open=rep-1&finding={raw}').finding))"
    )
    assert out is None or (isinstance(out, int) and out > 0)


def test_encode_is_canonical():
    """The same view must always produce the same string, whatever order the user
    clicked the facets in — otherwise two people on one view share different links
    and back/forward stacks up duplicate entries."""
    out = _node(
        """
        const a = U.emptyState(); a.filters.theme = ['B', 'A']; a.filters.year = ['2024', '2020'];
        const b = U.emptyState(); b.filters.theme = ['A', 'B']; b.filters.year = ['2020', '2024'];
        console.log(JSON.stringify({ a: U.encode(a), b: U.encode(b) }));
        """
    )
    assert out["a"] == out["b"]
    assert out["a"] == "#/ferc_audit?year=2020&year=2024&theme=A&theme=B"


def test_defaults_are_omitted_from_the_url():
    out = _node(
        """
        const s = U.emptyState(); s.sort = 'newest'; s.view = 'stream';
        const t = U.emptyState(); t.sort = 'amount'; t.view = 'ledger';
        console.log(JSON.stringify({ bare: U.encode(s), set: U.encode(t) }));
        """
    )
    assert out["bare"] == "#/ferc_audit"
    assert "sort=amount" in out["set"] and "view=ledger" in out["set"]


def test_values_needing_escaping_survive():
    """Theme names carry slashes, ampersands, commas and spaces ("AFUDC / cost of
    capital"), and company ids carry dots — a naive comma-joined encoding loses them."""
    out = _node(
        """
        const s = U.emptyState();
        s.filters.theme = ['Below-the-line costs (lobbying, charitable, etc.)', 'AFUDC / cost of capital'];
        s.filters.search = 'a&b=c?d#e';
        const back = U.decode(U.encode(s));
        console.log(JSON.stringify({ theme: back.filters.theme.slice().sort(), q: back.filters.search }));
        """
    )
    assert out["theme"] == [
        "AFUDC / cost of capital",
        "Below-the-line costs (lobbying, charitable, etc.)",
    ]
    assert out["q"] == "a&b=c?d#e"


def test_filter_groups_match_the_app_state():
    """urlstate's FILTER_GROUPS must cover every facet app.js filters on, or a
    shared link silently drops one and the recipient sees a different result set."""
    app_js = (REPO / "docs" / "js" / "app.js").read_text(encoding="utf-8")
    block = app_js.split("filters: {", 1)[1].split("}", 1)[0]
    # state.filters = { search: "", industry: new Set(), ... }
    app_groups = [k for k in __import__("re").findall(r"(\w+):", block) if k != "search"]
    url_groups = _node("console.log(JSON.stringify(U.FILTER_GROUPS))")
    assert sorted(app_groups) == sorted(url_groups), (
        f"app.js filters {sorted(app_groups)} vs urlstate {sorted(url_groups)}"
    )
