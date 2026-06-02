# FERC Form 1 analysis — feasibility & plan (eval 2026-06-02)

A strategic evaluation (not yet built) of three asks: (1) analyze Form 1 over time for changes in
rate-case inputs, (2) identify the stated reasoning for each field that rolls into the rate, (3) flag
form entries that are incorrect / merit scrutiny (e.g. lobbying in the rate, and less-obvious errors).

## The reframe — we already hold the hard part

The corpus today holds FERC's **audit findings** (602 findings = what auditors actually flag, tagged
into 13 themes in `pipeline/patterns.py`), **not** the raw **Form 1** financial data (the inputs).
That labeled findings set is the scarce asset — a ground-truth answer key for ask #3. So the work is
mostly **ingesting Form 1 and joining it to assets we already have**, not new research.

Top flag themes (count of real findings backing each): Accounting misclassification (191), Form
reporting / Page 700 (183), Property & plant records (63), Depreciation (62), **Below-the-line
lobbying/charitable (53)**, AFUDC (46), Cost of service & rates (46), Affiliate/intercompany (34),
Tariff (27), Capitalization-vs-expense (20), Informational postings (15), Trade dues (11).

## Data gap & source (Phase-0 to verify before committing)

- **Have:** audit findings → recommendations; state rate-case orders/testimony; prudence reviews.
- **Need:** raw **Form 1** (Annual Report of Major Electric Utilities) + Form 2 (gas) / Form 6 (oil).
  FERC publishes this as bulk data: historically **Visual FoxPro `.DBF` databases** (one zip/year;
  pages → tables like `F1_PLANT_IN_SERVICE`, `F1_INCOME`, `F1_ELC_OP_MAINT_EXPN`, the Account-426
  below-the-line page), and **2021+ as XBRL** (the eForms transition → two parsers). Gov-sourced, free.
- **Phase-0 check:** confirm the current download path — `www.ferc.gov` HTML is Cloudflare-blocked, so
  the bulk files likely live on a static/eForms host (a ~30-min verification gates the whole effort).

## Ask-by-ask

1. **Changes over time — HIGH feasibility, medium effort.** Ingest N years/utility; extract the rate-
   base + cost-of-service schedules (rate base = plant-in-service + CWIP + working capital −
   accum. depreciation − ADIT; COS = O&M, A&G, depreciation expense, taxes, return). Per-utility
   per-account time series + YoY anomaly flags. Pages: 110-117 (balance sheet / plant), 320-323
   (income), 336 (depreciation), **350-351 (Account 426 below-the-line)**, 930.2 (dues). The DBF→XBRL
   break (2021) is the main effort.
2. **Stated reasoning per rate field — HIGH for the structural layer.** Two layers: **(a) structural**
   — what each account is and whether it belongs in rates — from FERC's **Uniform System of Accounts,
   18 CFR Part 101** (eCFR, clean gov reference; defines every account + the below-the-line exclusions,
   e.g. 426.4 lobbying / 426.1 donations / 426.3 penalties are non-recoverable). Map each Form 1 line →
   its Part-101 definition. **(b) case-specific** — why a utility included/excluded a cost in a given
   rate case — lives in the rate-case orders/testimony, i.e. **the state-PUC + prudence corpus we're
   already building.** So ask #2 is mostly a join, not new research.
3. **Flag errors / scrutiny — HIGH; this IS the north-star "audit-my-document" mode.** A deterministic
   rules engine over Form 1, seeded by the 13 themes and **validated against the 602 findings** (does a
   rule fire on the utility-years FERC actually cited?):
   - **Below-the-line leakage** (the lobbying example): flag any Account 426.x / EEI-style dues in a
     rate rollup. (53 + 11 findings → highest-yield rule.)
   - **Ratio/anomaly:** AFUDC rate vs. allowed, depreciation rate vs. approved, affiliate-charge
     ratios, capitalize-vs-expense, YoY spikes. (62 + 46 + 34 findings.)
   - **Reporting-consistency:** Page 700 ↔ Form 1 cross-foots, balance-sheet ties. (183 findings.)
   - The "less obvious" errors are *discovered* by mining the findings text against the accounts each
     one cites. Keep it deterministic rules + Part-101 citations — **no LLM judgment** (preserves the
     verbatim discipline).

## Recommended phased path (cheap, boring-tech, static-first)

- **Phase 0** — download 2-3 Form-1 years for 2-3 utilities we already have audits for; confirm we can
  parse the rate accounts. (gates everything)
- **Phase 1** — Account→Part-101→rate-treatment table (powers #2 + the rules).
- **Phase 2** — time series + YoY flags (#1).
- **Phase 3** — flag engine, validated by checking it fires on the utility-years FERC actually cited (#3).

**Jurisdictional caveat:** Form 1 is FERC/wholesale-transmission; retail rate cases are state filings —
so Form 1 anomalies are a strong *proxy* for the cost structure, and our state docs carry the actual
retail-rate litigation. State precisely so we don't over-claim.
