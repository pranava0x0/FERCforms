# PA/MI findings parser — plan (2026-06-02)

Backlog item: *"Findings parser for the clean PA/MI management-audit subset … a `parse=True`
extractor (verbatim, no LLM) gated by a no-regression snapshot, with real table handling.
Flip `parse` on a per-seed basis as coverage proves out."*

## What the docs actually look like (explored PPL M&O audit, 1837310.pdf, 93pp)

PA **Management & Operations (M&O) audits** carry **Exhibit I-2 "Summary of Recommendations"** —
a clean, structured table linearizing (via pymupdf) as:

```
Chapter III – Executive Management and Organizational Structure
III-1
<verbatim recommendation text, 1–4 lines>
16            <- page no.
0-6 Months    <- initiation time frame
Medium        <- benefits
III-2
...
Chapter IV – Corporate Governance
None
Chapter V – Cost Allocations and Affiliated Interests
V-1
...
```

- **Chapter headers** `Chapter {ROMAN} – {Functional Area}` = the natural **finding/functional-area** unit.
- **Rec rows** `{ROMAN}-{N}` + verbatim text + (page, timeframe, benefit) trailing columns.
- **`None`** marks chapters with no recommendations (genuinely clean areas).

This is the **clean, enumerated, verbatim source** — the PA analogue of the FERC exec-summary list.
Exhibit I-1 (Functional Rating Summary, a matrix of X-marks) gives each area's severity rating but
linearizes messily; treat it as optional enrichment, not the spine.

**Out of scope for v1** (stay metadata-only — formats are messy / heterogeneous, and a naive parser
would emit garbled "verbatim" text, violating quote discipline):
- PA **focused audits** (multi-column summary tables that linearize badly)
- PA **Management Efficiency Investigation** (FirstEnergy 2025 — different structure)
- **MI** Liberty Consulting reports (different consultant format)

## Proposed approach

1. **Model mapping (verbatim, no LLM).** For each PA M&O audit with an Exhibit I-2:
   - `Finding` per chapter that has ≥1 recommendation: `title` = functional area (verbatim),
     `summary` = None (or the Exhibit I-1 rating if cleanly available), `is_other_matter=False`.
   - `Recommendation` per `{ROMAN}-{N}` row: `number` = sequential index, `text` = verbatim rec
     (page/timeframe/benefit columns stripped), grouped under its chapter `Finding`.
   - `structured=True`, `finding_count` = chapters with recs.
2. **New parser** `pipeline/state_structure.py::structure_mo_audit(seed, pages)` — pure functions,
   regex/line-state machine over the Exhibit I-2 block (bounded by "Summary of Recommendations" …
   next "II. BACKGROUND"/end). No network, no LLM.
3. **Wire into `sources.py`.** When `seed.parse=True`: save `text.json` (so it's re-runnable/testable
   like FERC), run `structure_mo_audit`; on parse failure or zero chapters, **fall back to
   metadata-only** (never emit a broken structured record). `parse=False` path unchanged.
4. **No-regression gate.** `tests/test_state_structure.py`:
   - Unit test over a synthetic Exhibit I-2 fixture (chapters, multi-line recs, `None`, trailing cols).
   - Real-report regression for the 3 PA M&O ids (skips if PDF/text absent locally), asserting
     `finding_count`/`rec_count` ≥ a snapshot floor and every finding has a title + every rec verbatim.
5. **Flip `parse=True`** for the 3 PA M&O seeds (PPL, FirstEnergy, PGW) in `pa_puc.json`; re-ingest +
   rebuild. The other PA/MI seeds stay `parse=False` (metadata-only).
6. **UI:** structured PA records now show real finding/rec counts instead of "Listed for reference" —
   no UI change needed (the tab already renders findings when `structured=True`).

## Why this scope

Targets only the format that parses **cleanly and verbatim**, gated so it can never regress the FERC
path or emit garbled quotes. Proves the mechanism on 3 docs; `parse` flips per-seed as more formats
are handled later (focused/MEI/MI), exactly as the backlog prescribes.
