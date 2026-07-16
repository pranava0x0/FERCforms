"use strict";

/* URL state codec (spec A1) — the pure half of permalinks.

   Shape: #/<collection>?<group>=<value>&<group>=<value>&q=…&sort=…&view=…&open=<id>
   e.g.   #/state_audit?theme=Depreciation&year=2024&open=2025-07-25_duke-energy…

   Hash, not query string: GitHub Pages serves a static file per path, so a real
   query would still 404 on anything but /, and the hash keeps the CDN cache key
   stable. Multi-valued facets repeat their key (URLSearchParams.getAll), which is
   the same convention EDGAR/ECHO use and needs no separator escaping.

   No DOM in this file. It is loaded as a plain script (window.URLState) and, in
   node, as a module — so tests/test_urlstate.py can round-trip it without a
   browser or a build step. Keep it that way: the moment this touches `document`
   it stops being testable.
*/
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.URLState = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  /* The facet groups that live in the URL. Mirrors state.filters in app.js minus
     `search` (carried as `q`, since "search" reads oddly in a URL). */
  const FILTER_GROUPS = ["impact", "industry", "audit_type", "functions", "form", "year", "theme", "company"];

  /* Defaults are OMITTED from the encoded URL — a shared link should carry what
     the sender changed, not the whole state object. */
  const DEFAULTS = { collection: "ferc_audit", sort: "newest", view: "stream" };

  function emptyState() {
    const filters = { search: "" };
    FILTER_GROUPS.forEach((g) => (filters[g] = []));
    return { collection: DEFAULTS.collection, filters, sort: DEFAULTS.sort, view: DEFAULTS.view, open: null };
  }

  /* state -> "#/…". Values are sorted so the same view always encodes to the same
     string: without it, two users on identical views produce different links and
     back/forward pushes duplicate entries. */
  function encode(state) {
    const s = state || {};
    const f = s.filters || {};
    const params = new URLSearchParams();
    FILTER_GROUPS.forEach((g) => {
      const values = Array.from(f[g] || []).map(String).sort();
      values.forEach((v) => params.append(g, v));
    });
    if (f.search) params.set("q", f.search);
    if (s.sort && s.sort !== DEFAULTS.sort) params.set("sort", s.sort);
    if (s.view && s.view !== DEFAULTS.view) params.set("view", s.view);
    if (s.open) params.set("open", s.open);
    const qs = params.toString();
    return "#/" + (s.collection || DEFAULTS.collection) + (qs ? "?" + qs : "");
  }

  /* "#/…" -> state. Total: any garbage decodes to the default view rather than
     throwing, because this runs on whatever a user pasted into the address bar. */
  function decode(hash) {
    const out = emptyState();
    const h = String(hash || "").replace(/^#/, "");
    if (!h.startsWith("/")) return out;
    const rest = h.slice(1);
    const cut = rest.indexOf("?");
    const path = cut === -1 ? rest : rest.slice(0, cut);
    const qs = cut === -1 ? "" : rest.slice(cut + 1);
    if (path) {
      try { out.collection = decodeURIComponent(path); } catch (e) { /* keep default */ }
    }
    const params = new URLSearchParams(qs);
    FILTER_GROUPS.forEach((g) => (out.filters[g] = params.getAll(g)));
    out.filters.search = params.get("q") || "";
    out.sort = params.get("sort") || DEFAULTS.sort;
    out.view = params.get("view") || DEFAULTS.view;
    out.open = params.get("open") || null;
    return out;
  }

  return { FILTER_GROUPS, DEFAULTS, emptyState, encode, decode };
});
