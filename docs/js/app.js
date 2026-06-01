"use strict";

/* FERC Audit Explorer — vanilla JS. Loads docs/data/*.json and renders a
   Google+ style stream of report cards, each expanding into a thread of
   findings -> recommendations. No framework, no build step. */

/* The three collections, one per tab. Keys mirror pipeline/build.py COLLECTIONS
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
];

const state = {
  collection: "ferc_audit",
  reports: [],
  patterns: null,          // global summary (all collections)
  patternsByCollection: {}, // { key: PatternsSummary }
  meta: null,
  filters: { search: "", industry: new Set(), form: new Set(), audit_type: new Set(), functions: new Set(), year: new Set(), theme: new Set(), impact: new Set() },
};

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

const fmtDate = (iso) => {
  if (!iso) return "Not stated";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
};
const yearOf = (iso) => (iso ? iso.slice(0, 4) : null);
const initials = (name) => (name || "?").replace(/[^A-Za-z ]/g, "").trim().charAt(0).toUpperCase() || "?";

/* ---------- data load ---------- */
async function load() {
  const [meta, patterns, byCollection, reports] = await Promise.all([
    fetch("data/meta.json").then((r) => r.json()),
    fetch("data/patterns.json").then((r) => r.json()),
    fetch("data/patterns_by_collection.json").then((r) => r.json()),
    fetch("data/reports.json").then((r) => r.json()),
  ]);
  state.meta = meta;
  state.patterns = patterns;
  state.patternsByCollection = byCollection;
  // Newest first — a feed-like default. Null issued_date sorts last.
  state.reports = reports.slice().sort((a, b) => (b.issued_date || "").localeCompare(a.issued_date || ""));
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
  state.filters.search = "";
  state.filters.industry.clear();
  state.filters.form.clear();
  state.filters.audit_type.clear();
  state.filters.functions.clear();
  state.filters.year.clear();
  state.filters.theme.clear();
  state.filters.impact.clear();
  document.getElementById("search").value = "";
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
    const hay = [
      report.company,
      report.docket_full,
      report.audit_period,
      ...report.findings.map((x) => x.title + " " + (x.summary || "")),
    ]
      .join(" ")
      .toLowerCase();
    if (!hay.includes(f.search.toLowerCase())) return false;
  }
  return true;
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
      title: `${t.report_count} of ${total} reports (${pct}%) · ${t.finding_count} findings — tap to filter`,
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
    state.filters.search = "";
    const s = document.getElementById("search");
    if (s) s.value = "";
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
  if (f.cost_to_customers || (f.themes && f.themes.length)) {
    const tags = [];
    if (f.cost_to_customers) tags.push(el("span", { class: "finding-tag cost-tag", title: COST_TIP, text: "Cost to customers" }));
    (f.themes || []).forEach((t) => tags.push(el("span", { class: "finding-tag", text: t })));
    parts.push(el("div", { class: "finding-tags" }, tags));
  }
  if (f.recommendations && f.recommendations.length) {
    const recs = el("ul", { class: "recs" });
    f.recommendations.forEach((r) =>
      recs.appendChild(
        el("li", { class: "rec" }, [el("span", { class: "rec-num", text: `Rec ${r.number}. ` }), r.text])
      )
    );
    parts.push(recs);
  }
  return el("div", { class: "finding" }, parts);
}

function citationText(r) {
  const kind = r.doc_type || (r.collection === "prudence_review" ? "FERC order" : r.collection === "state_audit" ? "Audit report" : "FERC Audit Report");
  const docket = r.docket_full || r.docket;
  return `${r.company}, ${kind}${docket ? ", Docket No. " + docket : ""}` +
    `${r.issued_date ? " (issued " + fmtDate(r.issued_date) + ")" : ""}. ${r.source ? r.source + ". " : ""}${r.source_page_url}`;
}

function cardNode(r) {
  const card = el("details", { class: "card" });

  const recCount = r.findings.reduce((n, f) => n + (f.recommendations ? f.recommendations.length : 0), 0);
  const docket = r.docket_full || r.docket;
  // Sub-meta: docket (if any) · issued date · source (for non-FERC provenance).
  const subBits = [];
  if (docket) subBits.push(`Docket No. ${docket}`);
  subBits.push(`Issued ${fmtDate(r.issued_date)}`);
  if (r.collection !== "ferc_audit" && r.source) subBits.push(r.source);

  // Status pill: real findings → count; metadata-only legal doc → "read source";
  // otherwise a genuinely finding-free audit.
  const statusPill = r.finding_count > 0
    ? el("span", { class: "pill solid", text: `${r.finding_count} finding${r.finding_count === 1 ? "" : "s"}` })
    : r.structured === false
      ? el("span", { class: "pill muted", text: "Listed for reference" })
      : el("span", { class: "pill muted", text: "No findings extracted" });

  const summary = el("summary", { class: "card-summary" }, [
    el("div", { class: "source-line" }, [
      el("span", { class: "avatar", "aria-hidden": "true", text: initials(r.company) }),
      el("span", { class: "source-meta" }, [
        el("span", { class: "company", text: r.company }),
        el("br"),
        el("span", { class: "sub-meta", text: subBits.join(" · ") }),
      ]),
      el("span", { class: "disclosure" }, [el("span", { class: "chev", "aria-hidden": "true", text: "▾" })]),
    ]),
    el("div", { class: "chips" }, [
      r.doc_type ? el("span", { class: "pill kind", text: cap(r.doc_type) })
        : r.audit_type ? el("span", { class: "pill kind", text: _ABBR[r.audit_type] || r.audit_type }) : null,
      statusPill,
      r.finding_count > 0 ? el("span", { class: "pill outline", text: `${recCount} rec${recCount === 1 ? "" : "s"}` }) : null,
      ...(r.functions || []).map((fn) => el("span", { class: "pill func", text: fn })),
    ]),
  ]);

  // Metadata rows — only include those that apply to this record's collection.
  const rows = [];
  if (r.audit_period) rows.push(...kv("Audit period", r.audit_period, false));
  if (r.audit_type) rows.push(...kv("Audit type", _ABBR[r.audit_type] || r.audit_type, false));
  if (r.doc_type) rows.push(...kv("Document type", cap(r.doc_type), false));
  rows.push(...kv("Jurisdiction", r.jurisdiction || "—", !r.jurisdiction));
  if (r.functions && r.functions.length) rows.push(...kv("Function(s)", r.functions.map(cap).join(", "), false));
  if (r.forms && r.forms.length) rows.push(...kv("FERC forms", r.forms.map((f) => "No. " + f).join(", "), false));
  if (r.page_count > 0) rows.push(...kv("Pages", String(r.page_count), false));
  rows.push(...kv("Source", r.source || r.source_note || "Not stated", !(r.source || r.source_note)));
  const root = el("div", { class: "thread-root" }, [el("dl", {}, rows)]);

  const findings = r.finding_count > 0
    ? el("div", {}, r.findings.map(findingNode))
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
      ]);

  const copyBtn = el("button", { type: "button", class: "btn-secondary", text: "Copy citation" });
  copyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(citationText(r));
      copyBtn.textContent = "Copied ✓";
      setTimeout(() => (copyBtn.textContent = "Copy citation"), 1800);
    } catch (e) {
      copyBtn.textContent = "Copy failed";
    }
  });

  const sourceLabel = r.jurisdiction === "FERC" ? "View on eLibrary ↗" : "View source ↗";
  const footer = el("div", { class: "thread-footer" }, [
    el("a", { class: "btn-secondary", href: r.source_page_url, rel: "noopener", target: "_blank", text: sourceLabel }),
    r.archived_via
      ? el("a", { class: "btn-secondary", href: r.archived_via, rel: "noopener", target: "_blank", text: "View Wayback snapshot ↗" })
      : null,
    copyBtn,
  ]);

  card.appendChild(summary);
  card.appendChild(el("div", { class: "thread" }, [root, findings, footer]));
  return card;
}

/* ---------- render stream ---------- */
function applyFilters() {
  const visible = state.reports.filter(matches);
  const stream = document.getElementById("stream");
  stream.replaceChildren(...visible.map(cardNode));

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

  document.getElementById("search").addEventListener("input", (e) => {
    state.filters.search = e.target.value;
    applyFilters();
  });
  document.getElementById("reset-filters").addEventListener("click", resetFilters);
  document.getElementById("empty-reset").addEventListener("click", resetFilters);
}

/* ---------- init ---------- */
(async function init() {
  wireChrome();
  try {
    await load();
  } catch (e) {
    document.getElementById("result-count").textContent = "Failed to load data.";
    console.error(e);
    return;
  }
  renderTabs();
  const def = COLLECTIONS.find((c) => c.key === state.collection);
  const lead = document.getElementById("intro-lead");
  if (lead && def) lead.innerHTML = def.lead;
  renderKPIs();
  renderFilters();
  renderPatternsBand();
  renderTrends();
  renderFooter();
  applyFilters();
})();
