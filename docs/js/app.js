"use strict";

/* FERC Audit Explorer — vanilla JS. Loads docs/data/*.json and renders a
   Google+ style stream of report cards, each expanding into a thread of
   findings -> recommendations. No framework, no build step. */

const state = {
  reports: [],
  patterns: null,
  meta: null,
  filters: { search: "", industry: new Set(), form: new Set(), audit_type: new Set(), functions: new Set(), year: new Set(), theme: new Set() },
};

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
  const [meta, patterns, reports] = await Promise.all([
    fetch("data/meta.json").then((r) => r.json()),
    fetch("data/patterns.json").then((r) => r.json()),
    fetch("data/reports.json").then((r) => r.json()),
  ]);
  state.meta = meta;
  state.patterns = patterns;
  // Newest first — a feed-like default. Null issued_date sorts last.
  state.reports = reports.slice().sort((a, b) => (b.issued_date || "").localeCompare(a.issued_date || ""));
}

/* ---------- KPIs ---------- */
function renderKPIs() {
  const p = state.patterns;
  document.getElementById("kpi-reports").textContent = p.report_count;
  document.getElementById("kpi-findings").textContent = p.finding_count;
  document.getElementById("kpi-recs").textContent = p.recommendation_count;
  document.getElementById("kpi-themes").textContent = p.themes.length;
  const introCount = document.getElementById("intro-count");
  if (introCount) introCount.textContent = p.report_count;
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

function renderFilters() {
  const industries = uniqueSorted(state.reports.map((r) => r.industry));
  const types = uniqueSorted(state.reports.map((r) => r.audit_type));
  const functions = uniqueSorted(state.reports.flatMap((r) => r.functions || []));
  const years = uniqueSorted(state.reports.map((r) => yearOf(r.issued_date))).reverse();

  const indBox = document.getElementById("industry-options");
  if (indBox) industries.forEach((i) => indBox.appendChild(chip(cap(i), null, "industry", i)));

  const typeBox = document.getElementById("type-options");
  types.forEach((t) => typeBox.appendChild(chip(_ABBR[t] || t, null, "audit_type", t)));

  const fnBox = document.getElementById("function-options");
  functions.forEach((fn) => fnBox.appendChild(chip(cap(fn), null, "functions", fn)));

  const formsList = uniqueSorted(state.reports.flatMap((r) => r.forms || []));
  const formBox = document.getElementById("form-options");
  if (formBox) formsList.forEach((fm) => formBox.appendChild(chip("No. " + fm, null, "form", fm)));

  const yearBox = document.getElementById("year-options");
  years.forEach((y) => yearBox.appendChild(chip(y, null, "year", y)));
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
  document.getElementById("search").value = "";
  document.querySelectorAll('[aria-pressed="true"]').forEach((c) => c.setAttribute("aria-pressed", "false"));
  applyFilters();
}

function matches(report) {
  const f = state.filters;
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
function renderPatternsBand() {
  const rail = document.getElementById("patterns-rail");
  if (!rail) return;
  const total = state.patterns.report_count || state.reports.length || 1;
  const themes = state.patterns.themes.slice().sort((a, b) => b.report_count - a.report_count);
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
      el("span", { class: "pattern-stat" }, [
        el("span", { class: "pattern-count", text: String(t.report_count) }),
        el("span", { class: "pattern-of", text: ` of ${total} audits · ${pct}%` }),
      ]),
      el("span", { class: "pattern-track", "aria-hidden": "true" }, [
        el("span", { class: "pattern-bar", style: `width:${Math.round((t.report_count / max) * 100)}%` }),
      ]),
    ]);
    card.addEventListener("click", () => toggleFilter("theme", t.theme, card));
    rail.appendChild(el("li", {}, card));
  });
}

/* ---------- active-filter chips (shows WHY the stream is narrowed) ---------- */
const _GROUP_ORDER = ["industry", "audit_type", "functions", "form", "year", "theme"];
function activeChipLabel(group, value) {
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
  return `${r.company}, FERC Audit Report, Docket No. ${r.docket_full || r.docket || "N/A"}` +
    `${r.issued_date ? " (issued " + fmtDate(r.issued_date) + ")" : ""}. ${r.source_page_url}`;
}

function cardNode(r) {
  const card = el("details", { class: "card" });

  const recCount = r.findings.reduce((n, f) => n + (f.recommendations ? f.recommendations.length : 0), 0);
  const summary = el("summary", { class: "card-summary" }, [
    el("div", { class: "source-line" }, [
      el("span", { class: "avatar", "aria-hidden": "true", text: initials(r.company) }),
      el("span", { class: "source-meta" }, [
        el("span", { class: "company", text: r.company }),
        el("br"),
        el("span", {
          class: "sub-meta",
          text: `Docket No. ${r.docket_full || r.docket || "—"} · Issued ${fmtDate(r.issued_date)}`,
        }),
      ]),
      el("span", { class: "disclosure" }, [el("span", { class: "chev", "aria-hidden": "true", text: "▾" })]),
    ]),
    el("div", { class: "chips" }, [
      r.audit_type ? el("span", { class: "pill kind", text: _ABBR[r.audit_type] || r.audit_type }) : null,
      r.finding_count > 0
        ? el("span", { class: "pill solid", text: `${r.finding_count} finding${r.finding_count === 1 ? "" : "s"}` })
        : el("span", { class: "pill muted", text: "No findings extracted" }),
      r.finding_count > 0 ? el("span", { class: "pill outline", text: `${recCount} rec${recCount === 1 ? "" : "s"}` }) : null,
      ...(r.functions || []).map((fn) => el("span", { class: "pill func", text: fn })),
    ]),
  ]);

  const root = el("div", { class: "thread-root" }, [
    el("dl", {}, [
      ...kv("Audit period", r.audit_period || "Not stated", !r.audit_period),
      ...kv("Audit type", r.audit_type ? (_ABBR[r.audit_type] || r.audit_type) : "Not stated", !r.audit_type),
      ...kv("Function(s)", r.functions && r.functions.length ? r.functions.map(cap).join(", ") : "Not stated", !(r.functions || []).length),
      ...kv("FERC forms", r.forms && r.forms.length ? r.forms.map((f) => "No. " + f).join(", ") : "Not stated", !(r.forms || []).length),
      ...kv("Pages", String(r.page_count), false),
      ...kv("Source", r.source_note || "Not stated", !r.source_note),
    ]),
  ]);

  const findings = r.finding_count > 0
    ? el("div", {}, r.findings.map(findingNode))
    : el("div", { class: "no-findings" }, [
        el("p", {}, [
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

  const footer = el("div", { class: "thread-footer" }, [
    el("a", { class: "btn-secondary", href: r.source_page_url, rel: "noopener", target: "_blank", text: "View on eLibrary ↗" }),
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
  document.getElementById("empty-state").hidden = visible.length !== 0;

  renderActiveFilters();
  const activeCount = _GROUP_ORDER.reduce((n, g) => n + state.filters[g].size, 0) + (state.filters.search ? 1 : 0);
  const ft = document.getElementById("filters-toggle");
  if (ft) ft.textContent = activeCount ? `Filters · ${activeCount}` : "Filters";
}

/* ---------- footer ---------- */
function renderFooter() {
  const m = state.meta;
  const bi = m.by_industry_identified || {};
  const idents = Object.entries(bi)
    .filter(([k]) => k !== "unknown")
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${v} ${k}`)
    .join(", ");
  document.getElementById("footer-meta").textContent =
    `Scope: ${m.scope}. ${m.reports_structured} of ${m.reports_total_listed} listed audits structured` +
    (idents ? ` (${idents} identified)` : "") + `. ` +
    `Listing captured ${fmtDate(m.listing_captured_at)}; built ${fmtDate(m.generated_at)}.`;
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
  fToggle.addEventListener("click", () => {
    const open = filters.classList.toggle("open");
    fToggle.setAttribute("aria-expanded", open ? "true" : "false");
  });

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
  renderKPIs();
  renderFilters();
  renderPatternsBand();
  renderFooter();
  applyFilters();
})();
