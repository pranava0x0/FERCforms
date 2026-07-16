"use strict";

/* FERC Audit Explorer — vanilla JS. Loads docs/data/*.json and renders a
   Google+ style stream of report cards, each expanding into a thread of
   findings -> recommendations. No framework, no build step. */

/* The five collections, one per tab. Keys mirror pipeline/build.py COLLECTIONS
   (a Python test asserts the key sets stay in sync). `lead` is the per-tab intro
   sentence; `empty` shows when a collection has no documents yet. */
const COLLECTIONS = [
  {
    key: "ferc_audit",
    label: "FERC Audits",
    lead: "Findings from <strong><span class=\"intro-count\">—</span> FERC utility audits</strong> — electric, gas &amp; oil. Tap a <strong>pattern</strong> below to see an issue across companies, or open any card to read the findings, quoted verbatim.",
    empty: "No FERC audit reports in this build yet.",
  },
  {
    key: "prudence_review",
    label: "Prudence Reviews",
    lead: "<strong><span class=\"intro-count\">—</span> FERC prudence determinations</strong> from rate-case orders, formal challenges &amp; fuel-cost disputes. These are free-form legal orders — listed with their source, not parsed into findings.",
    empty: "No FERC prudence determinations in this build yet — coming soon.",
  },
  {
    key: "state_audit",
    label: "State PUC Audits",
    lead: "<strong><span class=\"intro-count\">—</span> state utility-commission audits &amp; prudence reviews</strong> (PUC / PSC / SCC). Management and focused audits are parsed into findings; orders &amp; testimony are listed with their source.",
    empty: "No state PUC audits in this build yet — coming soon.",
  },
  {
    key: "state_rate_case",
    label: "State Rate Cases (Reference)",
    lead: "<strong><span class=\"intro-count\">—</span> state regulatory rate-case documents</strong> — base-rate orders, fuel-cost decisions, settlements, and testimony. These are cost-recovery proceedings showing commission-approved/denied costs; listed with their source for regulatory reference.",
    empty: "No state rate-case documents in this build yet.",
  },
  {
    key: "state_reference",
    label: "State Reference Docs",
    lead: "<strong><span class=\"intro-count\">—</span> state PUC reference &amp; administrative documents</strong> — a commission's own internal/self-audits, recurring compliance or informational filings, and administrative reference pages. These are not audits of a regulated utility; listed with their source for reference.",
    empty: "No state reference documents in this build yet.",
  },
];

/* The fields the first-paint payload (data/reports_index.json) carries for every
   report — enough to render a collapsed card and run every facet/sort. Findings
   and thread metadata live in data/findings_<collection>.json, fetched lazily on
   first expand. Mirrors pipeline/build.py CARD_FIELDS (a Python test asserts the
   two lists stay in sync); reading anything outside this list off a report object
   before its detail has loaded yields undefined. */
const CARD_FIELDS = [
  "id",
  "collection",
  "company",
  "docket",
  "docket_full",
  "issued_date",
  "audit_type",
  "doc_type",
  "industry",
  "forms",
  "functions",
  "finding_count",
  "themes",
  "cost_to_customers",
  "structured",
  "source",
  "audit_period",
];

const state = {
  collection: "ferc_audit",
  reports: [],             // index entries (no findings — see CARD_FIELDS)
  details: {},             // { collection: { report_id: {findings, ...thread fields} } }
  detailFetches: {},       // { collection: Promise } — in-flight/settled, dedupes fetches
  patterns: null,          // global summary (all collections)
  patternsByCollection: {}, // { key: PatternsSummary }
  meta: null,
  sort: "newest",
  filters: { search: "", industry: new Set(), form: new Set(), audit_type: new Set(), functions: new Set(), year: new Set(), theme: new Set(), impact: new Set() },
};

/* ---------- lazy detail loading ---------- */
/* Finding bodies are ~80% of the corpus text but are only needed to render an
   expanded thread (or to search finding text). Fetch each collection's detail
   file at most once; callers await the same promise. */
function ensureDetails(collection) {
  if (state.detailFetches[collection]) return state.detailFetches[collection];
  const p = fetch(`data/findings_${collection}.json`)
    .then((r) => {
      if (!r.ok) throw new Error(`findings_${collection}.json: HTTP ${r.status}`);
      return r.json();
    })
    .then((d) => {
      state.details[collection] = d;
      return d;
    })
    .catch((e) => {
      // Let the next caller retry rather than caching the failure forever.
      delete state.detailFetches[collection];
      throw e;
    });
  state.detailFetches[collection] = p;
  return p;
}

const detailOf = (r) => (state.details[r.collection] || {})[r.id] || null;
const findingsOf = (r) => (detailOf(r) || {}).findings || [];

/* Warm the active tab's detail file once the page is interactive, so expanding a
   card is instant in the common case. Low priority — never races the first paint. */
function prefetchDetails(collection) {
  const go = () => ensureDetails(collection).catch(() => {});
  if ("requestIdleCallback" in window) requestIdleCallback(go, { timeout: 3000 });
  else setTimeout(go, 400);
}

/* A11 — long enough to skip intermediate keystrokes, short enough to feel live. */
const SEARCH_DEBOUNCE_MS = 150;

/* A pending search is module state, not wireChrome-local, because every path that
   CLEARS the search (reset filters, clear-all, the chip ✕, a tab switch) has to be
   able to cancel one. A queued search doesn't just wait out the debounce — it also
   awaits a detail-file fetch, so the window it can fire in is the whole download,
   long enough to land after the user has moved on. */
let _searchTimer = null;
let _searchSeq = 0;
function cancelPendingSearch() {
  clearTimeout(_searchTimer);
  _searchSeq++; // also invalidates a run already past its timer, mid-fetch
}

/* Set the search box(es) directly — used by the reset paths, which must not go
   through the input handler. A query rather than a hard-coded id so the hero box
   isn't the only thing this can ever drive. */
function setSearchInputs(value) {
  document.querySelectorAll(".search-input").forEach((i) => (i.value = value));
}

/* Patterns + reports for the active tab. */
const activePatterns = () => state.patternsByCollection[state.collection] || { report_count: 0, finding_count: 0, recommendation_count: 0, themes: [], by_year: {}, by_industry: {}, by_function: {} };
const collectionReports = () => state.reports.filter((r) => r.collection === state.collection);

/* The ratepayer-harm axis: finding types that, by their nature, over-recover from
   or wrongly charge customers. Curated single-source in pipeline/patterns.py. */
const COST_TIP =
  "Finding type that over-recovers from or wrongly charges customers — below-the-line costs, membership dues, affiliate transactions, depreciation, AFUDC, or cost-of-service errors.";

/* ---------- tiny DOM helper ---------- */
function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "html") node.innerHTML = v; // only used with trusted static strings
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c == null) continue;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

const fmtDate = (iso, short) => {
  if (!iso) return "Not stated";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { year: "numeric", month: short ? "short" : "long", day: "numeric" });
};
/* B3 — card sub-meta always uses the short date ("Sep 8, 2025") so it stays one
   line at 375px. The spec scoped this to <560px, but a viewport-dependent date
   has to be read at render time, which freezes the format at whatever width first
   painted unless the whole stream re-renders on every breakpoint cross (which
   would also collapse any open card). One format everywhere is simpler, has no
   stale-state failure mode, and reads more like the ledger the identity is aiming
   at. The full date still appears where formality matters: the thread's KV grid
   and the citation string. */
const yearOf = (iso) => (iso ? iso.slice(0, 4) : null);
/* Compact USD for the finding-level $ pill (amount_usd is the first dollar figure
   in a finding's own committed text — see pipeline/amounts.py). */
const fmtAmount = (n) => {
  if (n == null || !isFinite(n)) return null;
  const a = Math.abs(n), sign = n < 0 ? "-" : "";
  // Thresholds are 0.5% below each unit so values that round up across a
  // boundary (999,999 -> "$1M", not "$1000K") land in the higher unit.
  if (a >= 9.95e8) return sign + "$" + (a / 1e9).toFixed(a >= 1e10 ? 0 : 1).replace(/\.0$/, "") + "B";
  if (a >= 9.95e5) return sign + "$" + (a / 1e6).toFixed(a >= 1e7 ? 0 : 1).replace(/\.0$/, "") + "M";
  if (a >= 1e3) return sign + "$" + Math.round(a / 1e3) + "K";
  return sign + "$" + Math.round(a).toLocaleString("en-US");
};
const initials = (name) => (name || "?").replace(/[^A-Za-z ]/g, "").trim().charAt(0).toUpperCase() || "?";

/* ---------- data load ---------- */
const getJSON = (path) =>
  fetch(path).then((r) => {
    if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
    return r.json();
  });

async function load() {
  const [meta, patterns, byCollection, index] = await Promise.all([
    getJSON("data/meta.json"),
    getJSON("data/patterns.json"),
    getJSON("data/patterns_by_collection.json"),
    getJSON("data/reports_index.json"),
  ]);
  state.meta = meta;
  state.patterns = patterns;
  state.patternsByCollection = byCollection;
  state.reports = index;
}

/* ---------- KPIs ---------- */
function renderKPIs() {
  const p = activePatterns();
  document.getElementById("kpi-reports").textContent = p.report_count;
  document.getElementById("kpi-findings").textContent = p.finding_count;
  document.getElementById("kpi-recs").textContent = p.recommendation_count;
  document.getElementById("kpi-themes").textContent = p.themes.length;
  // The per-tab intro sentence carries one or more .intro-count spans.
  document.querySelectorAll(".intro-count").forEach((n) => (n.textContent = p.report_count));
}

/* ---------- tabs ---------- */
function renderTabs() {
  const host = document.getElementById("tabs");
  if (!host) return;
  const counts = (state.meta && state.meta.by_collection) || {};
  host.replaceChildren(
    ...COLLECTIONS.map((c) => {
      const tab = el("button", {
        type: "button",
        class: "tab",
        role: "tab",
        id: `tab-${c.key}`,
        "aria-selected": c.key === state.collection ? "true" : "false",
        "data-collection": c.key,
      }, [
        el("span", { text: c.label }),
        el("span", { class: "tab-count", text: String(counts[c.key] != null ? counts[c.key] : 0) }),
      ]);
      tab.addEventListener("click", () => switchCollection(c.key));
      return tab;
    })
  );
}

function switchCollection(key) {
  if (key === state.collection) return;
  state.collection = key;
  resetFilters(); // facets differ per collection; start each tab clean
  document.querySelectorAll(".tab").forEach((t) =>
    t.setAttribute("aria-selected", t.dataset.collection === key ? "true" : "false")
  );
  const def = COLLECTIONS.find((c) => c.key === key);
  const lead = document.getElementById("intro-lead");
  if (lead && def) lead.innerHTML = def.lead;
  renderKPIs();
  renderFilters();
  renderPatternsBand();
  renderTrends();
  // resetFilters already called applyFilters, but facet/intro DOM changed — re-run.
  applyFilters();
  scrollToTop();
  prefetchDetails(key); // warm the new tab's finding bodies while the user reads
}

function scrollToTop() {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
}

/* ---------- filters ---------- */
function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort();
}

function chip(label, count, group, value) {
  const c = el("button", {
    type: "button",
    class: "filter-chip",
    "aria-pressed": "false",
    "data-group": group,
    "data-value": value,
  });
  c.appendChild(el("span", { text: label }));
  if (count != null) c.appendChild(el("span", { class: "chip-count", text: String(count) }));
  c.addEventListener("click", () => toggleFilter(group, value, c));
  return c;
}

const _ABBR = { financial: "Financial (FA)", "non-financial": "Non-financial (PA)" };
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

/* Facets are derived from the ACTIVE collection's reports, so each tab shows only
   the industries/forms/years that exist within it. A facet field with no values
   is hidden so empty filter groups don't clutter a tab. */
function fillFacet(boxId, chips) {
  const box = document.getElementById(boxId);
  if (!box) return;
  box.replaceChildren(...chips);
  const field = box.closest(".field");
  if (field) field.hidden = chips.length === 0;
}

function renderFilters() {
  const reports = collectionReports();
  const industries = uniqueSorted(reports.map((r) => r.industry));
  const types = uniqueSorted(reports.map((r) => r.audit_type));
  const functions = uniqueSorted(reports.flatMap((r) => r.functions || []));
  const years = uniqueSorted(reports.map((r) => yearOf(r.issued_date))).reverse();
  const formsList = uniqueSorted(reports.flatMap((r) => r.forms || []));

  const harmCount = reports.filter((r) => r.cost_to_customers).length;
  const impactChips = harmCount
    ? [(() => { const c = chip("Cost to customers", harmCount, "impact", "cost_to_customers"); c.title = COST_TIP; return c; })()]
    : [];
  fillFacet("impact-options", impactChips);
  fillFacet("industry-options", industries.map((i) => chip(cap(i), null, "industry", i)));
  fillFacet("type-options", types.map((t) => chip(_ABBR[t] || t, null, "audit_type", t)));
  fillFacet("function-options", functions.map((fn) => chip(cap(fn), null, "functions", fn)));
  fillFacet("form-options", formsList.map((fm) => chip("No. " + fm, null, "form", fm)));
  fillFacet("year-options", years.map((y) => chip(y, null, "year", y)));
  renderYearPresets(years);
}

/* E1 — date facets ship as PRESETS, never a blank date picker (EDGAR's pattern).
   A preset is a shortcut that selects the underlying year chips, so it stays one
   filter model — nothing new to encode in state. */
const YEAR_PRESETS = [
  { label: "Last year", years: 1 },
  { label: "Last 5 years", years: 5 },
  { label: "All years", years: null },
];
function renderYearPresets(years) {
  const host = document.getElementById("year-presets");
  if (!host) return;
  if (!years.length) { host.replaceChildren(); return; }
  const newest = Number(years[0]); // years is sorted newest-first
  host.replaceChildren(
    ...YEAR_PRESETS.map((p) => {
      // Anchor on the newest year the CORPUS has, not today's date: "last year"
      // must mean "the most recent year with audits", or a preset silently
      // selects nothing whenever the regulator has been quiet (A9's honesty rule).
      const wanted = p.years === null ? years : years.filter((y) => Number(y) > newest - p.years);
      const btn = el("button", { type: "button", class: "preset-chip", text: p.label });
      btn.addEventListener("click", () => {
        state.filters.year = new Set(wanted);
        document.querySelectorAll('[data-group="year"]').forEach((c) =>
          c.setAttribute("aria-pressed", state.filters.year.has(c.dataset.value) ? "true" : "false")
        );
        applyFilters();
      });
      return btn;
    })
  );
}

function toggleFilter(group, value, btn) {
  const set = state.filters[group];
  if (set.has(value)) set.delete(value);
  else set.add(value);
  // keep every control for this group/value in sync (filter chips + pattern band)
  document
    .querySelectorAll(`[data-group="${CSS.escape(group)}"][data-value="${CSS.escape(value)}"]`)
    .forEach((c) => c.setAttribute("aria-pressed", set.has(value) ? "true" : "false"));
  applyFilters();
}

function resetFilters() {
  cancelPendingSearch(); // else a queued search re-applies itself after the reset
  state.filters.search = "";
  state.filters.industry.clear();
  state.filters.form.clear();
  state.filters.audit_type.clear();
  state.filters.functions.clear();
  state.filters.year.clear();
  state.filters.theme.clear();
  state.filters.impact.clear();
  setSearchInputs("");
  document.querySelectorAll('[aria-pressed="true"]').forEach((c) => c.setAttribute("aria-pressed", "false"));
  applyFilters();
}

function matches(report) {
  const f = state.filters;
  if (report.collection !== state.collection) return false;
  if (f.impact.size && !report.cost_to_customers) return false;
  if (f.industry.size && !f.industry.has(report.industry)) return false;
  if (f.form.size && !(report.forms || []).some((x) => f.form.has(x))) return false;
  if (f.audit_type.size && !f.audit_type.has(report.audit_type)) return false;
  if (f.functions.size && !(report.functions || []).some((x) => f.functions.has(x))) return false;
  if (f.year.size && !f.year.has(yearOf(report.issued_date))) return false;
  if (f.theme.size && !(report.themes || []).some((t) => f.theme.has(t))) return false;
  if (f.search) {
    // Finding bodies come from the lazily-fetched detail file. The search handler
    // awaits it before filtering, so by here findingsOf() is populated; if a fetch
    // failed we still match on the index fields rather than dropping the report.
    const hay = [
      report.company,
      report.docket_full,
      report.audit_period,
      ...findingsOf(report).map((x) => x.title + " " + (x.summary || "")),
    ]
      .join(" ")
      .toLowerCase();
    if (!hay.includes(f.search.toLowerCase())) return false;
  }
  return true;
}

/* ---------- sort (A3) ---------- */
/* Every comparator is a total order with a stable id tiebreak, so the stream
   never reshuffles between renders. Null issued_date / no cited $ sort last. */
const SORTS = {
  newest: { label: "Newest first", cmp: (a, b) => (b.issued_date || "").localeCompare(a.issued_date || "") },
  oldest: { label: "Oldest first", cmp: (a, b) => (a.issued_date || "￿").localeCompare(b.issued_date || "￿") },
  findings: { label: "Most findings", cmp: (a, b) => b.finding_count - a.finding_count },
  amount: { label: "Largest $", cmp: (a, b) => (b.amount_max || -1) - (a.amount_max || -1) },
  company: { label: "Company A–Z", cmp: (a, b) => a.company.localeCompare(b.company) },
};

function sortReports(list) {
  const { cmp } = SORTS[state.sort] || SORTS.newest;
  return list.slice().sort((a, b) => cmp(a, b) || a.id.localeCompare(b.id));
}

/* ---------- top patterns band ---------- */
/* Bring the (now-filtered) stream into view. JS-driven smooth scroll isn't
   covered by the reduced-motion CSS rule, so honor the preference here. */
function scrollToResults() {
  const main = document.getElementById("main");
  if (!main) return;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  main.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
}

function renderPatternsBand() {
  const rail = document.getElementById("patterns-rail");
  if (!rail) return;
  rail.replaceChildren();
  const p = activePatterns();
  // Hide the whole band when the active tab has no mined patterns yet.
  const band = rail.closest(".patterns-band");
  if (band) band.hidden = !p.themes.length;
  if (!p.themes.length) return;
  const total = p.report_count || 1;
  const themes = p.themes.slice().sort((a, b) => b.report_count - a.report_count);
  const max = Math.max(1, ...themes.map((t) => t.report_count));
  themes.forEach((t) => {
    const pct = Math.round((t.report_count / total) * 100);
    const card = el("button", {
      type: "button",
      class: "pattern-card",
      "aria-pressed": "false",
      "data-group": "theme",
      "data-value": t.theme,
      title: `${t.report_count} of ${total} reports (${pct}%)${t.finding_count ? ` · ${t.finding_count} findings` : ""} — tap to filter`,
    }, [
      el("span", { class: "pattern-name", text: t.theme }),
      t.description ? el("span", { class: "pattern-desc", text: t.description }) : null,
      el("span", { class: "pattern-stat" }, [
        el("span", { class: "pattern-count", text: String(t.report_count) }),
        el("span", { class: "pattern-of", text: ` of ${total} audits · ${pct}%` }),
      ]),
      el("span", { class: "pattern-track", "aria-hidden": "true" }, [
        el("span", { class: "pattern-bar", style: `width:${Math.round((t.report_count / max) * 100)}%` }),
      ]),
    ]);
    card.addEventListener("click", () => {
      toggleFilter("theme", t.theme, card);
      // Scroll down to the results only when turning the pattern on.
      if (state.filters.theme.has(t.theme)) scrollToResults();
    });
    rail.appendChild(el("li", {}, card));
  });
}

/* ---------- corpus trends (charts over the already-computed aggregates) ---------- */
/* A vertical column chart — used for the year timeline. */
function trendColumns(title, unit, entries) {
  const max = Math.max(1, ...entries.map(([, v]) => v));
  const cols = entries.map(([label, v]) =>
    el("div", { class: "trend-col", role: "listitem", "aria-label": `${label}: ${v} ${unit}`, title: `${label}: ${v} ${unit}` }, [
      el("span", { class: "trend-col-val", text: String(v) }),
      el("span", { class: "trend-col-bar", style: `height:${v ? Math.max(4, Math.round((v / max) * 80)) : 0}px`, "aria-hidden": "true" }),
      el("span", { class: "trend-col-yr", text: "’" + String(label).slice(2) }),
    ])
  );
  return el("div", { class: "trend-card" }, [
    el("h3", { class: "trend-card-title", text: title }),
    el("div", { class: "trend-cols", role: "list", "aria-label": `${title}, ${unit}` }, cols),
  ]);
}

/* A horizontal bar chart — used for the few-category breakdowns. */
function trendBars(title, unit, entries, note) {
  const max = Math.max(1, ...entries.map(([, v]) => v));
  const rows = entries.map(([label, v]) =>
    el("div", { class: "trend-row", role: "listitem", "aria-label": `${label}: ${v} ${unit}`, title: `${label}: ${v} ${unit}` }, [
      el("span", { class: "trend-row-label", text: label }),
      el("span", { class: "trend-track", "aria-hidden": "true" }, [el("span", { class: "trend-bar", style: `width:${Math.round((v / max) * 100)}%` })]),
      el("span", { class: "trend-row-val", text: String(v) }),
    ])
  );
  return el("div", { class: "trend-card" }, [
    el("h3", { class: "trend-card-title", text: title }),
    el("div", { class: "trend-rows", role: "list", "aria-label": `${title}, ${unit}` }, rows),
    note ? el("p", { class: "trend-note", text: note }) : null,
  ]);
}

function renderTrends() {
  const host = document.getElementById("trends");
  if (!host) return;
  const p = activePatterns();
  const band = host.closest(".trends-band");
  if (band) band.hidden = !p.report_count;
  if (!p.report_count) { host.replaceChildren(); return; }
  // By year & by industry are clean counts (one issued-year / one industry per report).
  const years = Object.keys(p.by_year).sort();
  const industries = Object.entries(p.by_industry).sort((a, b) => b[1] - a[1]);
  // A report can cover several functions, so these bars can sum past the report total.
  const functions = Object.entries(p.by_function).sort((a, b) => b[1] - a[1]);
  const cards = [
    trendColumns("By year issued", "reports", years.map((y) => [y, p.by_year[y]])),
    industries.length ? trendBars("By industry", "reports", industries.map(([k, v]) => [cap(k), v])) : null,
    // The function tagging is FERC-audit-specific; skip the card when a collection has none.
    functions.length ? trendBars("By function", "reports", functions.map(([k, v]) => [cap(k), v]), `A report may cover several functions, so these exceed ${p.report_count}.`) : null,
  ].filter(Boolean);
  host.replaceChildren(...cards);
}

/* ---------- active-filter chips (shows WHY the stream is narrowed) ---------- */
const _GROUP_ORDER = ["impact", "industry", "audit_type", "functions", "form", "year", "theme"];
function activeChipLabel(group, value) {
  if (group === "impact") return "Cost to customers";
  if (group === "audit_type") return _ABBR[value] || value;
  if (group === "form") return "Form No. " + value;
  if (group === "industry" || group === "functions") return cap(value);
  return value; // year, theme
}
function removeActiveFilter(group, value) {
  if (group === "search") {
    cancelPendingSearch();
    state.filters.search = "";
    setSearchInputs("");
  } else {
    state.filters[group].delete(value);
    document
      .querySelectorAll(`[data-group="${CSS.escape(group)}"][data-value="${CSS.escape(value)}"]`)
      .forEach((c) => c.setAttribute("aria-pressed", "false"));
  }
  applyFilters();
}
function activeChip(group, value, label) {
  const btn = el("button", { type: "button", class: "active-chip", "aria-label": `Remove filter: ${label}` }, [
    el("span", { text: label }),
    el("span", { class: "active-chip-x", "aria-hidden": "true", text: "✕" }),
  ]);
  btn.addEventListener("click", () => removeActiveFilter(group, value));
  return btn;
}
function renderActiveFilters() {
  const bar = document.getElementById("active-filters");
  if (!bar) return;
  const chips = [];
  if (state.filters.search) chips.push(activeChip("search", null, `“${state.filters.search}”`));
  _GROUP_ORDER.forEach((group) => {
    state.filters[group].forEach((value) => chips.push(activeChip(group, value, activeChipLabel(group, value))));
  });
  if (chips.length) chips.push(el("button", { type: "button", class: "active-clear", text: "Clear all", onclick: resetFilters }));
  bar.replaceChildren(...chips);
  bar.hidden = chips.length === 0;
}

/* ---------- card / thread ---------- */
function kv(label, value, muted) {
  return [
    el("dt", { text: label }),
    el("dd", muted ? { class: "muted-cell", text: value } : { text: value }),
  ];
}

function findingNode(f) {
  const head = el("div", { class: "finding-head" }, [
    el("span", { class: "dot " + (f.is_other_matter ? "other-dot" : "finding-dot"), "aria-hidden": "true" }),
    el("span", { class: "finding-title", text: f.title }),
    f.is_other_matter ? el("span", { class: "finding-flag", text: "Other matter" }) : null,
  ]);
  const parts = [head];
  if (f.summary) parts.push(el("p", { class: "finding-summary", text: f.summary }));
  const amount = fmtAmount(f.amount_usd);
  if (f.cost_to_customers || amount || (f.themes && f.themes.length)) {
    const tags = [];
    if (amount) {
      // Cited dollar figure: title carries the verbatim quote + source page it was located on.
      const tip = (f.amount_usd_quote ? '"' + f.amount_usd_quote + '"' : "Headline dollar figure") +
        (f.amount_usd_page != null ? ` (source p. ${f.amount_usd_page})` : "");
      tags.push(el("span", { class: "finding-tag amount-tag", title: tip, text: amount }));
    }
    if (f.cost_to_customers) tags.push(el("span", { class: "finding-tag cost-tag", title: COST_TIP, text: "Cost to customers" }));
    (f.themes || []).forEach((t) => tags.push(el("span", { class: "finding-tag", text: t })));
    parts.push(el("div", { class: "finding-tags" }, tags));
  }
  if (f.recommendations && f.recommendations.length) {
    const recs = el("ul", { class: "recs" });
    f.recommendations.forEach((r) => {
      const kids = [el("span", { class: "rec-num", text: `Rec ${r.number}. ` }), r.text];
      // Page in the source document where the rec is discussed (PA M&O Exhibit I-2).
      if (r.source_page != null)
        kids.push(
          el("span", {
            class: "rec-page",
            text: ` (p. ${r.source_page})`,
            title: `Discussed on page ${r.source_page} of the source document`,
          })
        );
      recs.appendChild(el("li", { class: "rec" }, kids));
    });
    parts.push(recs);
  }
  return el("div", { class: "finding" }, parts);
}

/* The source URL lives in the detail record (thread-only), so citations are only
   ever built where a thread is rendered. */
function citationText(r, detail) {
  const kind = r.doc_type || (r.collection === "prudence_review" ? "FERC order" : r.collection === "state_audit" ? "Audit report" : "FERC Audit Report");
  const docket = r.docket_full || r.docket;
  return `${r.company}, ${kind}${docket ? ", Docket No. " + docket : ""}` +
    `${r.issued_date ? " (issued " + fmtDate(r.issued_date) + ")" : ""}. ${r.source ? r.source + ". " : ""}${detail.source_page_url}`;
}

/* E1 — "See an issue? Report it": a prefilled GitHub issue (zero-backend
   analogue of ProPublica's "See an issue with the data? Contact Us"). The record
   id + docket travel in the body so a report is actionable without a round-trip. */
const ISSUE_URL = "https://github.com/pranava0x0/FERCforms/issues/new";
function reportIssueLink(r) {
  const body = [
    `Record: ${r.id}`,
    `Company: ${r.company}`,
    r.docket_full || r.docket ? `Docket: ${r.docket_full || r.docket}` : null,
    "",
    "What looks wrong?",
  ].filter((x) => x !== null).join("\n");
  const href = `${ISSUE_URL}?title=${encodeURIComponent(`Data issue: ${r.company} (${r.id})`)}&body=${encodeURIComponent(body)}`;
  return el("a", { class: "btn-secondary subtle", href, rel: "noopener", target: "_blank", text: "See an issue? Report it ↗" });
}

/* A2 — a mechanical one-line subject for the collapsed card. Composed only from
   fields the record already states (audit type/period, or document type); it
   never paraphrases a finding. Returns null when the record states neither. */
function cardSubject(r) {
  if (r.collection === "ferc_audit") {
    const bits = [];
    if (r.audit_type) bits.push((_ABBR[r.audit_type] || r.audit_type) + " audit");
    if (r.audit_period) bits.push(r.audit_period);
    return bits.length ? bits.join(" — ") : null;
  }
  return r.doc_type ? cap(r.doc_type) : null;
}

/* A2 — up to 3 theme chips + a "+N" overflow count. Themes are the best scent
   for both personas, and every report already carries its union at bake time. */
const THEME_CHIP_LIMIT = 3;
function cardThemeChips(r) {
  const themes = r.themes || [];
  if (!themes.length) return null;
  const shown = themes.slice(0, THEME_CHIP_LIMIT);
  const extra = themes.length - shown.length;
  return el("div", { class: "card-themes" }, [
    ...shown.map((t) => el("span", { class: "finding-tag", text: t })),
    extra ? el("span", { class: "finding-tag more-tag", title: themes.slice(THEME_CHIP_LIMIT).join(" · "), text: `+${extra}` }) : null,
  ]);
}

/* The expanded thread. Built from the lazily-fetched detail record, so it only
   runs on first open — which is also what keeps the whole-corpus render cheap. */
function threadNode(r, detail) {
  const rows = [];
  if (r.audit_period) rows.push(...kv("Audit period", r.audit_period, false));
  if (r.audit_type) rows.push(...kv("Audit type", _ABBR[r.audit_type] || r.audit_type, false));
  if (r.doc_type) rows.push(...kv("Document type", cap(r.doc_type), false));
  rows.push(...kv("Jurisdiction", detail.jurisdiction || "—", !detail.jurisdiction));
  if (r.functions && r.functions.length) rows.push(...kv("Function(s)", r.functions.map(cap).join(", "), false));
  if (r.forms && r.forms.length) rows.push(...kv("FERC forms", r.forms.map((f) => "No. " + f).join(", "), false));
  if (detail.page_count > 0) rows.push(...kv("Pages", String(detail.page_count), false));
  // A9 — surface the capture date on the card itself: "as of" is the difference
  // between absence-of-data and absence-of-issues.
  if (detail.captured_at) rows.push(...kv("Captured", fmtDate(detail.captured_at), false));
  rows.push(...kv("Source", r.source || detail.source_note || "Not stated", !(r.source || detail.source_note)));
  const root = el("div", { class: "thread-root" }, [el("dl", {}, rows)]);

  const findings = (detail.findings || []).length
    ? el("div", {}, detail.findings.map(findingNode))
    : el("div", { class: "no-findings" }, [
        r.structured === false
          ? el("p", {}, [
              el("strong", { text: "Listed for reference. " }),
              "This document is captured with its source for the pattern library; in this build it isn’t machine-parsed into individual findings — read the full report via the link below.",
            ])
          : el("p", {}, [
              el("strong", { text: "No findings extracted. " }),
              "This audit may have raised no noncompliance issues, or they aren’t yet machine-readable from the source PDF in this build — read the original via the links below.",
            ]),
        // Reference records carry descriptor-derived theme tags (from the document
        // type + source note shown on this card) — surface them like finding tags.
        r.themes && r.themes.length
          ? el("div", { class: "finding-tags" }, r.themes.map((t) => el("span", { class: "finding-tag", text: t })))
          : null,
      ]);

  const copyBtn = el("button", { type: "button", class: "btn-secondary", text: "Copy citation" });
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(citationText(r, detail));
      copyBtn.textContent = "Copied ✓";
      setTimeout(() => (copyBtn.textContent = "Copy citation"), 1800);
    } catch (e) {
      copyBtn.textContent = "Copy failed";
    }
  });

  const sourceLabel = detail.jurisdiction === "FERC" ? "View on eLibrary ↗" : "View source ↗";
  const footer = el("div", { class: "thread-footer" }, [
    el("a", { class: "btn-secondary", href: detail.source_page_url, rel: "noopener", target: "_blank", text: sourceLabel }),
    detail.archived_via
      ? el("a", { class: "btn-secondary", href: detail.archived_via, rel: "noopener", target: "_blank", text: "View Wayback snapshot ↗" })
      : null,
    copyBtn,
    reportIssueLink(r),
  ]);

  return el("div", { class: "thread" }, [root, findings, footer]);
}

/* Fill a card's thread on first expand. The detail file is usually already warm
   (prefetchDetails), so this resolves synchronously-ish; the placeholder only
   shows on a cold or slow fetch. */
async function fillThread(card, r) {
  if (card.dataset.filled) return;
  card.dataset.filled = "1";
  const detail = detailOf(r);
  if (detail) {
    card.appendChild(threadNode(r, detail));
    return;
  }
  const pending = el("div", { class: "thread thread-pending" }, [el("p", { class: "muted-cell", text: "Loading findings…" })]);
  card.appendChild(pending);
  try {
    await ensureDetails(r.collection);
    const loaded = detailOf(r);
    if (!loaded) throw new Error(`no detail record for ${r.id}`);
    pending.replaceWith(threadNode(r, loaded));
  } catch (e) {
    console.error(e);
    // Fail loud and offer a way out rather than leaving a dead "Loading…".
    const retry = el("button", { type: "button", class: "link-btn", text: "Retry" });
    retry.addEventListener("click", () => {
      pending.remove();
      delete card.dataset.filled;
      fillThread(card, r);
    });
    pending.replaceChildren(el("p", {}, ["Couldn’t load this report’s findings. ", retry]));
  }
}

function cardNode(r) {
  const card = el("details", { class: "card" });
  if (r.cost_to_customers) card.classList.add("has-cost"); // A2 — amber edge tick

  const docket = r.docket_full || r.docket;
  // Sub-meta: docket (if any) · issued date · source (for non-FERC provenance).
  // Each segment is its own node so it can wrap BETWEEN segments but never mid-phrase (F9/B3).
  const subBits = [];
  if (docket) subBits.push(el("span", { class: "sub-bit docket-bit", text: `Docket No. ${docket}` }));
  subBits.push(el("span", { class: "sub-bit", text: `Issued ${fmtDate(r.issued_date, true)}` }));
  if (r.collection !== "ferc_audit" && r.source) subBits.push(el("span", { class: "sub-bit", text: r.source }));

  // Status pill: real findings → count; metadata-only legal doc → "read source";
  // otherwise a genuinely finding-free audit.
  const statusPill = r.finding_count > 0
    ? el("span", { class: "pill solid", text: `${r.finding_count} finding${r.finding_count === 1 ? "" : "s"}` })
    : r.structured === false
      ? el("span", { class: "pill muted", text: "Listed for reference" })
      : el("span", { class: "pill muted", text: "No findings extracted" });

  // F2 — a "0 recs" pill reads as "auditors made no recommendations", which is
  // false for essentially every FERC audit; it really means recs weren't parsed.
  // Render the pill only when recommendations were actually extracted.
  const recPill = r.rec_count > 0
    ? el("span", { class: "pill outline", text: `${r.rec_count} rec${r.rec_count === 1 ? "" : "s"}` })
    : null;

  const amount = fmtAmount(r.amount_max);

  const summary = el("summary", { class: "card-summary" }, [
    el("div", { class: "source-line" }, [
      el("span", { class: "avatar", "aria-hidden": "true", text: initials(r.company) }),
      el("span", { class: "source-meta" }, [
        el("span", { class: "company", text: r.company }),
        el("span", { class: "sub-meta" }, subBits),
      ]),
      el("span", { class: "disclosure" }, [el("span", { class: "chev", "aria-hidden": "true", text: "▾" })]),
    ]),
    cardSubject(r) ? el("p", { class: "headline", text: cardSubject(r) }) : null,
    el("div", { class: "chips" }, [
      r.doc_type ? el("span", { class: "pill kind", text: cap(r.doc_type) })
        : r.audit_type ? el("span", { class: "pill kind", text: _ABBR[r.audit_type] || r.audit_type }) : null,
      statusPill,
      recPill,
      amount ? el("span", { class: "pill amount", title: "Largest dollar figure cited in this report's findings, as stated in the report", text: amount }) : null,
      r.cost_to_customers ? el("span", { class: "pill cost", title: COST_TIP, text: "Cost to customers" }) : null,
      ...(r.functions || []).map((fn) => el("span", { class: "pill func", text: fn })),
    ]),
    cardThemeChips(r),
  ]);

  card.appendChild(summary);
  card.addEventListener("toggle", () => {
    if (card.open) fillThread(card, r);
  });
  return card;
}

/* ---------- render stream ---------- */
/* B1 — the stream appends cards in pages behind an IntersectionObserver sentinel
   rather than rendering every match at once (123 cards on the FERC tab produced
   multi-second blank frames). Filtering stays whole-corpus, so the result count
   is always exact — only the DOM append is chunked. */
const PAGE_SIZE = 20;
const _render = { visible: [], shown: 0, observer: null, sentinel: null };

function appendPage() {
  const stream = document.getElementById("stream");
  const next = _render.visible.slice(_render.shown, _render.shown + PAGE_SIZE);
  if (!next.length) return;
  const frag = document.createDocumentFragment();
  next.forEach((r) => frag.appendChild(cardNode(r)));
  stream.appendChild(frag);
  _render.shown += next.length;
  if (_render.shown >= _render.visible.length) {
    // Everything rendered — retire the sentinel so the observer stops firing.
    if (_render.observer) _render.observer.disconnect();
    if (_render.sentinel) _render.sentinel.hidden = true;
  }
}

function renderStream(visible) {
  const stream = document.getElementById("stream");
  _render.visible = visible;
  _render.shown = 0;
  stream.replaceChildren();

  if (!_render.sentinel) {
    _render.sentinel = el("div", { class: "stream-sentinel", "aria-hidden": "true" });
    stream.after(_render.sentinel);
  }
  _render.sentinel.hidden = false;

  if (!_render.observer && "IntersectionObserver" in window) {
    // rootMargin pre-renders the next page before the sentinel is on screen, so
    // fast scrolling doesn't reach the end of the list first (DESIGN.md §12.3).
    _render.observer = new IntersectionObserver(
      (entries) => { if (entries.some((e) => e.isIntersecting)) appendPage(); },
      { rootMargin: "600px 0px" }
    );
  }
  appendPage();
  if (_render.observer) _render.observer.observe(_render.sentinel);
  // No IntersectionObserver (very old browser): render everything rather than
  // silently truncating the corpus.
  else while (_render.shown < _render.visible.length) appendPage();
}

function applyFilters() {
  const visible = sortReports(state.reports.filter(matches));
  renderStream(visible);

  const findings = visible.reduce((n, r) => n + r.finding_count, 0);
  document.getElementById("result-count").textContent =
    `${visible.length} report${visible.length === 1 ? "" : "s"} · ${findings} finding${findings === 1 ? "" : "s"}`;

  // Empty-state copy depends on WHY it's empty: a tab with no documents at all
  // gets the collection's "coming soon" line (and no Clear-filters button);
  // a filtered-to-nothing tab keeps the filter-clearing prompt.
  const collectionEmpty = collectionReports().length === 0;
  const def = COLLECTIONS.find((c) => c.key === state.collection);
  document.getElementById("empty-msg").textContent =
    collectionEmpty && def ? def.empty : "No reports match these filters.";
  document.getElementById("empty-reset").hidden = collectionEmpty;
  document.getElementById("empty-state").hidden = visible.length !== 0;

  renderActiveFilters();
  const activeCount = _GROUP_ORDER.reduce((n, g) => n + state.filters[g].size, 0) + (state.filters.search ? 1 : 0);
  const ft = document.getElementById("filters-toggle");
  if (ft) ft.textContent = activeCount ? `Filters · ${activeCount}` : "Filters";
}

/* ---------- hero trust line (E1) ---------- */
/* The genre's credibility stat, above the search box: what's in here, from whom,
   over what period, how fresh. Every number is a corpus count, never a claim. */
function renderTrustLine() {
  const host = document.getElementById("trust-line");
  if (!host) return;
  const p = state.patterns || {};
  const m = state.meta || {};
  // Counted at bake time (meta.jurisdictions_covered) — `jurisdiction` is a
  // detail field, so the index alone can't count regulators.
  const juris = m.jurisdictions_covered || [];
  const states = juris.filter((j) => j !== "FERC").length;
  const who = juris.includes("FERC") ? `FERC + ${states} state regulator${states === 1 ? "" : "s"}` : `${juris.length} regulators`;
  const years = Object.keys(p.by_year || {}).sort();
  const span = years.length ? `, ${years[0]}→present` : "";
  host.replaceChildren(
    el("strong", { text: `${p.finding_count || 0} verbatim findings` }),
    document.createTextNode(" from "),
    el("strong", { text: `${p.report_count || 0} audit & regulatory documents` }),
    document.createTextNode(` — ${who}${span} · updated ${fmtDate(m.generated_at)}`)
  );
}

/* ---------- footer ---------- */
function renderFooter() {
  const m = state.meta;
  const bc = m.by_collection || {};
  const colParts = COLLECTIONS.map((c) => `${bc[c.key] != null ? bc[c.key] : 0} ${c.label}`).join(" · ");
  document.getElementById("footer-meta").textContent =
    `${colParts}. FERC listing captured ${fmtDate(m.listing_captured_at)}; built ${fmtDate(m.generated_at)}.`;
  if (m.source) document.getElementById("footer-link").href = m.source;
}

/* ---------- theme toggle + mobile filters ---------- */
function wireChrome() {
  const toggle = document.getElementById("theme-toggle");
  toggle.addEventListener("click", () => {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
    try { localStorage.setItem("ferc-theme", dark ? "light" : "dark"); } catch (e) {}
  });

  const fToggle = document.getElementById("filters-toggle");
  const filters = document.getElementById("filters");
  const backdrop = document.getElementById("filters-backdrop");
  const setFilters = (open) => {
    filters.classList.toggle("open", open);
    fToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (backdrop) backdrop.hidden = !open;
  };
  fToggle.addEventListener("click", () => setFilters(!filters.classList.contains("open")));
  if (backdrop) backdrop.addEventListener("click", () => setFilters(false));
  const sheetClose = document.getElementById("sheet-close");
  if (sheetClose) sheetClose.addEventListener("click", () => setFilters(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && filters.classList.contains("open")) setFilters(false);
  });

  // Tablist keyboard support (Left/Right/Home/End move between collection tabs).
  const tabsNav = document.getElementById("tabs");
  if (tabsNav) {
    tabsNav.addEventListener("keydown", (e) => {
      const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
      if (!keys.includes(e.key)) return;
      e.preventDefault();
      const tabs = [...tabsNav.querySelectorAll(".tab")];
      const i = tabs.findIndex((t) => t.dataset.collection === state.collection);
      let n = i;
      if (e.key === "ArrowLeft") n = (i - 1 + tabs.length) % tabs.length;
      else if (e.key === "ArrowRight") n = (i + 1) % tabs.length;
      else if (e.key === "Home") n = 0;
      else if (e.key === "End") n = tabs.length - 1;
      switchCollection(tabs[n].dataset.collection);
      tabs[n].focus();
    });
  }

  // A11 — debounce: re-filtering the corpus on every keystroke compounds F4.
  // Searching also needs finding bodies, so the active tab's detail file is
  // fetched (once) before the filter runs; a failed fetch degrades to matching
  // company/docket only rather than blocking the search box.
  const onSearch = (value) => {
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(async () => {
      const seq = ++_searchSeq;
      // Pin the tab this run belongs to: the awaited file must be the one
      // matches() will read, and the result must not be applied to another tab.
      const collection = state.collection;
      if (value) {
        try { await ensureDetails(collection); } catch (e) { console.error(e); }
        // Bail if a newer keystroke, a filter reset, or a tab switch happened
        // while the fetch was in flight.
        if (seq !== _searchSeq || collection !== state.collection) return;
      }
      state.filters.search = value;
      applyFilters();
    }, SEARCH_DEBOUNCE_MS);
  };
  document.querySelectorAll(".search-input").forEach((input) =>
    input.addEventListener("input", (e) => onSearch(e.target.value))
  );

  // A3 — sort control. Pure client-side reorder of the current result set.
  const sortSel = document.getElementById("sort");
  if (sortSel) {
    sortSel.replaceChildren(
      ...Object.entries(SORTS).map(([k, { label }]) => el("option", { value: k, text: label }))
    );
    sortSel.value = state.sort;
    sortSel.addEventListener("change", (e) => {
      state.sort = e.target.value;
      applyFilters();
      scrollToResults();
    });
  }

  document.getElementById("reset-filters").addEventListener("click", resetFilters);
  document.getElementById("empty-reset").addEventListener("click", resetFilters);

  const toTop = document.getElementById("to-top");
  if (toTop) toTop.addEventListener("click", scrollToTop);
}

/* ---------- init ---------- */
(async function init() {
  wireChrome();
  try {
    await load();
  } catch (e) {
    console.error(e);
    // B4 — a dead "Failed to load data." leaves no way forward; offer a retry.
    const count = document.getElementById("result-count");
    count.textContent = "Failed to load data. ";
    const retry = el("button", { type: "button", class: "link-btn", text: "Retry" });
    retry.addEventListener("click", () => location.reload());
    count.appendChild(retry);
    return;
  }
  renderTabs();
  const def = COLLECTIONS.find((c) => c.key === state.collection);
  const lead = document.getElementById("intro-lead");
  if (lead && def) lead.innerHTML = def.lead;
  renderTrustLine();
  renderKPIs();
  renderFilters();
  renderPatternsBand();
  renderTrends();
  renderFooter();
  applyFilters();
  prefetchDetails(state.collection);
})();
