/*
 * Privacy-hardened Google Analytics 4 loader for the FERC Audit Explorer.
 *
 * Single source of truth for the GA Measurement ID (see GA_MEASUREMENT_ID below)
 * — both index.html and about.html load THIS file, so the id lives in one place.
 *
 * Privacy posture (per the project's commitment in CLAUDE.md — "Respect user
 * privacy choices"):
 *   - gtag.js is loaded DIRECTLY from googletagmanager.com — never proxied through
 *     this site's own domain (proxying to defeat blockers erodes trust).
 *   - We bail out entirely when the visitor signals Do-Not-Track (DNT) or Global
 *     Privacy Control (GPC) — no script injected, no requests made.
 *   - IP anonymization on; Google Signals and ad-personalization off (no
 *     advertising/remarketing use of the data).
 *
 * SETUP: replace the placeholder below with your GA4 Measurement ID. Until then
 * this script is a safe no-op (nothing loads).
 */
(function () {
  "use strict";

  // ── The one value to configure ──────────────────────────────────────────────
  var GA_MEASUREMENT_ID = "G-8K4GBB47BF"; // GA4 "FERC Audit Explorer" property (Mint Test account)

  // No-op until a real id is set, so committing the placeholder ships nothing live.
  if (!GA_MEASUREMENT_ID || GA_MEASUREMENT_ID === "G-XXXXXXXXXX") return;

  // Honor Do-Not-Track / Global Privacy Control: if set, load nothing at all.
  var dnt =
    navigator.doNotTrack === "1" ||
    window.doNotTrack === "1" ||
    navigator.msDoNotTrack === "1" ||
    navigator.globalPrivacyControl === true;
  if (dnt) return;

  // Standard gtag.js bootstrap, loaded from Google's own CDN (not proxied).
  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.gtag = gtag;
  gtag("js", new Date());
  gtag("config", GA_MEASUREMENT_ID, {
    anonymize_ip: true,
    allow_google_signals: false,
    allow_ad_personalization_signals: false,
  });

  var s = document.createElement("script");
  s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(GA_MEASUREMENT_ID);
  document.head.appendChild(s);
})();
