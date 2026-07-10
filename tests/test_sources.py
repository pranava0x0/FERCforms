"""Tests for the generic source-ingestion path (pipeline/sources.py).

Covers the metadata-only structuring used for prudence / state-PUC documents:
the FERC executive-summary parser doesn't fit them, so they're captured with
their source and full provenance but NOT machine-extracted into findings
(see the module docstring + the multi-source policy).
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline import config, sources
from pipeline.models import SourceSeed


def _seed(**over) -> SourceSeed:
    base = dict(
        id="2024-07-11_ppl_pa-mo-audit",
        company="PPL Electric Utilities Corporation",
        collection="state_audit",
        jurisdiction="PA",
        source="PA PUC Bureau of Audits",
        doc_type="management & operations audit",
        industry="electric",
        pdf_url="https://www.puc.pa.gov/pcdocs/1837310.pdf",
        source_page_url="https://www.puc.pa.gov/press-release/2024/x",
        issued_date=date(2024, 7, 11),
        docket="D-2023-3039488",
        captured_at=date(2026, 6, 1),
        source_note="note",
    )
    base.update(over)
    return SourceSeed(**base)


def test_structure_seed_is_metadata_only():
    """A seed becomes an AuditReport carrying its provenance, with NO findings and
    structured=False so the UI shows the honest 'Listed for reference' state."""
    r = sources.structure_seed(_seed(), page_count=65, scanned_pages=[])
    assert r.collection == "state_audit"
    assert r.jurisdiction == "PA"
    assert r.source == "PA PUC Bureau of Audits"
    assert r.doc_type == "management & operations audit"
    assert r.industry == "electric"
    assert r.page_count == 65
    assert r.structured is False
    assert r.finding_count == 0 and r.findings == []
    # Provenance preserved end-to-end.
    assert r.pdf_download_url.endswith("1837310.pdf")
    assert r.issued_date == date(2024, 7, 11)


def test_source_seed_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        _seed(bogus_field="x")


def test_source_seed_defaults():
    s = _seed(doc_type=None, industry=None, docket=None)
    assert s.parse is False           # metadata-only by default
    assert s.fetch is True            # machine-fetch by default
    assert s.archived_via is None


def test_fetch_false_writes_metadata_only_without_network(tmp_path):
    """A fetch=False seed (browser-captured URL from a WAF-blocked source) writes a
    metadata-only record straight from the seed — no network, page_count 0."""
    seed = _seed(
        id="2026-01-07_x_oh-20-1502",
        jurisdiction="OH",
        # a host that would hard-fail if actually fetched — fetch=False must skip it
        pdf_url="https://dis.puc.state.oh.us/ViewImage.aspx?CMID=ZZZ",
        source_page_url="https://dis.puc.state.oh.us/CaseRecord.aspx?CaseNo=20-1502-EL-UNC",
        fetch=False,
    )
    seed_file = tmp_path / "oh.json"
    seed_file.write_text(json.dumps([seed.model_dump(mode="json")]), encoding="utf-8")

    written, no_pdf = sources.process_seed(
        seed_file, raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed"
    )
    assert written == 1
    assert no_pdf == [seed.id]                       # recorded as written-without-a-fetched-PDF
    report = json.loads((tmp_path / "processed" / seed.id / "report.json").read_text())
    assert report["structured"] is False
    assert report["page_count"] == 0
    assert report["finding_count"] == 0
    assert not (tmp_path / "raw" / f"{seed.id}.pdf").exists()  # nothing downloaded


def test_is_official_gov_accepts_gov_rejects_mirrors():
    assert sources.is_official_gov("https://www.puc.pa.gov/pcdocs/1.pdf")
    assert sources.is_official_gov("https://www.michigan.gov/mpsc/x.pdf")
    assert sources.is_official_gov("https://elibrary.ferc.gov/eLibrary/filelist?x")
    assert sources.is_official_gov("https://dis.puc.state.oh.us/ViewImage.aspx")  # legacy state gov
    # Deep South state hosts (GA / LA / MS) added in the 2026-06-02 expansion.
    assert sources.is_official_gov("https://services.psc.ga.gov/api/v1/External/Public/Get/Document/DownloadFile/222513/103670")
    assert sources.is_official_gov("https://psc.ga.gov/search/facts-document/?documentId=222513")
    assert sources.is_official_gov("https://lpscpubvalence.lpsc.louisiana.gov/portal/PSC/ViewFile?fileId=%2BTYZ0y9CRc0%3D")
    assert sources.is_official_gov("https://www.psc.ms.gov/sites/default/files/2024-MPUS-Annual-Report.pdf")
    assert sources.is_official_gov("https://www.psc.state.ms.us/InSiteConnect/InSiteView.aspx?docid=402655")  # legacy .state.ms.us
    assert sources.is_official_gov("https://apps.apsc.arkansas.gov/pdf/16/16-036-FR_1122_1.pdf")  # AR (*.arkansas.gov)
    assert sources.is_official_gov("https://efis.psc.mo.gov/Document/Display/854655")  # MO EFIS
    assert sources.is_official_gov("https://mn.gov/oah/assets/2500-39704-x_tcm19-650610.pdf")  # MN OAH (mn.gov)
    assert sources.is_official_gov("https://apps.psc.wi.gov/ERF/ERFview/viewdoc.aspx?docid=574424")  # WI ERF
    assert sources.is_official_gov("https://www.dora.state.co.us/pls/efi/efi.show_document?p_dms_document_id=984848")  # CO (.state.co.us)
    assert sources.is_official_gov("https://www.psc.state.fl.us/library/Orders/2024/09666-2024.pdf")  # FL PSC (legacy .state.fl.us)
    assert sources.is_official_gov("https://www.psc.nd.gov/webdocs/case/24-0376/086-010.pdf")  # ND PSC (psc.nd.gov)
    assert sources.is_official_gov("https://puc.sd.gov/commission/dockets/electric/2025/EL25-004/Application.pdf")  # SD PUC (puc.sd.gov)
    assert sources.is_official_gov("https://puc.idaho.gov/Fileroom/PublicFiles/ELEC/IPC/IPCE2520/OrdNotc/x.pdf")  # ID PUC (puc.idaho.gov)
    assert sources.is_official_gov("https://apps.puc.state.or.us/orders/2021ords/21-457.pdf")  # OR PUC (legacy .state.or.us)
    assert sources.is_official_gov("https://apiproxy.utc.wa.gov/cases/GetDocument?docID=4536")  # WA UTC (utc.wa.gov)
    assert sources.is_official_gov("https://psc.mt.gov/News/Special/FinalOrder7860y_DOC-26058.pdf")  # MT PSC (psc.mt.gov)
    assert sources.is_official_gov("https://pucweb1.state.nv.us/pdf/CS27269.pdf")  # NV PUCN (legacy .state.nv.us)
    assert sources.is_official_gov("https://docket.images.azcc.gov/0000209684.pdf")  # AZ ACC eDocket image host
    assert sources.is_official_gov("https://www.azcc.gov/divisions/utilities/electric/APS-FinalOrder.pdf")  # AZ ACC main site
    assert sources.is_official_gov("https://docs.cpuc.ca.gov/published/Final_decision/51417.htm")  # CA CPUC (.ca.gov)
    assert sources.is_official_gov("https://dps.ny.gov/system/files/documents/2025/08/x.pdf")  # NY DPS (.ny.gov)
    assert sources.is_official_gov("https://estar.kcc.ks.gov/estar/ViewFile.aspx/x.pdf?Id=y")  # KS KCC (.ks.gov)
    assert sources.is_official_gov("https://pscdocs.utah.gov/electric/24docs/2403504/x.pdf")  # UT PSC (.utah.gov)
    assert sources.is_official_gov("https://portal.ct.gov/-/media/pura/electric/x.pdf")  # CT PURA (.ct.gov)
    assert sources.is_official_gov("https://ripuc.ri.gov/sites/g/files/xkgbur841/files/2024-09/x.pdf")  # RI PUC (.ri.gov)
    assert sources.is_official_gov("https://www.nebraska.gov/psc/orders/natgas/NG-0086.30.pdf")  # NE PSC (nebraska.gov)
    assert sources.is_official_gov("https://tpucdockets.tn.gov/archive/filings/2025/2500044a.pdf")  # TN TPUC (.tn.gov)
    # Narrow .org allowlist: the DC PSC's own domain (it never adopted .gov).
    assert sources.is_official_gov("https://edocket.dcpsc.org/apis/api/Filing/download?attachId=1")
    assert sources.is_official_gov("https://dcpsc.org/CMSPages/GetFile.aspx?guid=x")
    # Third-party mirrors / aggregators / non-gov sources are rejected — incl. other .org.
    assert not sources.is_official_gov("https://www.documentcloud.org/documents/123")
    assert not sources.is_official_gov("https://example.org/audit.pdf")
    assert not sources.is_official_gov("https://notdcpsc.org/x")          # not a dcpsc.org subdomain
    assert not sources.is_official_gov("https://dcpsc.org.evil.io/x")     # suffix-spoof rejected
    assert not sources.is_official_gov("https://example.com/audit.pdf")
    assert not sources.is_official_gov("https://notgov.com.evil.io/x")
    assert not sources.is_official_gov("")


def test_load_seed_rejects_non_gov_source(tmp_path):
    bad = [{
        "id": "x", "company": "X", "collection": "state_audit", "jurisdiction": "PA",
        "source": "mirror", "pdf_url": "https://www.documentcloud.org/x.pdf",
        "source_page_url": "https://www.documentcloud.org/x", "captured_at": "2026-06-01",
    }]
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="official government source"):
        sources.load_seed(p)


def test_committed_seeds_are_all_official_gov():
    """Every committed seed must source from an official .gov host — no mirrors."""
    for path in sorted(config.SEEDS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue  # Skip non-list seed files (e.g., tier3_targets.json which is a dict)
        for d in data:
            assert sources.is_official_gov(d["pdf_url"]), f"{path.name}: {d['pdf_url']}"
            assert sources.is_official_gov(d["source_page_url"]), f"{path.name}: {d['source_page_url']}"


def test_committed_seeds_have_no_fabrication_markers():
    """Provenance integrity guard (regression for the 2026-06-07 fabricated-seed
    cleanup). A prior session generated ~59 fake `*_audits.json` "audit" records
    across ~40 states with invented docket numbers and guessed PDF URLs, marked
    `fetch=false` so they'd never be tested against a real source, and shipped them
    to the live site — a direct violation of the project's verbatim/real-source
    discipline. The two telltale signatures of that batch:

      1. a `source_note` admitting the URL is a guess ("placeholder",
         "pending verification"), and
      2. a `captured_at` in the FUTURE (they were stamped 2026-06-08 the day before).

    A second base-file batch (2026-06-07) leaked the same fakes into existing seed
    files (sc_psc/tx_puct/co_puc/mo_psc/oh_puco/fl_psc) with `placeholder` literally
    embedded in the PDF URL (`…/Attachments/Matter/placeholder-dec-order`,
    `…?p_dms_document_id=placeholder`). So the "placeholder"/"pending verification"
    scan runs over the URLs too, not just the note.

    No legitimate seed has any of these. This test fails loud if such a record reappears.
    (Sequential guessed doc-numbers like TX `…_1234567.PDF` slip past a pure-string
    check — those are caught by the live-URL verifier `pipeline.verify_sources`.)"""
    today = date.today()
    bad_phrases = ("placeholder", "pending verification")
    scanned_fields = ("source_note", "pdf_url", "source_page_url", "docket", "id")
    offenders: list[str] = []
    for path in sorted(config.SEEDS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue  # Skip non-list seed files (e.g., tier3_targets.json which is a dict)
        for d in data:
            blob = " ".join(str(d.get(f) or "") for f in scanned_fields).lower()
            if any(p in blob for p in bad_phrases):
                offenders.append(f"{path.name}:{d['id']} — fabrication marker (placeholder/unverified)")
            cap = d.get("captured_at")
            if cap and date.fromisoformat(cap) > today:
                offenders.append(f"{path.name}:{d['id']} — captured_at {cap} is in the future")
    assert not offenders, "fabricated/unverified seeds present:\n" + "\n".join(offenders)


def test_every_processed_report_is_git_tracked():
    """Phantom-record guard (regression for the 2026-06-08 gitignore trap). `.gitignore`
    ignores `data/processed/*/report.json` by default — committed records are force-added
    (`git add -f`), and git keeps honoring updates to already-tracked files. The trap: a
    NEW record written by the pipeline is silently skipped by a plain `git add data/processed`,
    so the baked docs/data/reports.json references a record whose report.json was never
    committed — exactly the phantom the corpus had (322 baked / 248 real). Every report.json
    on disk must be git-tracked (or staged) so the committed corpus == the baked corpus."""
    import subprocess

    try:
        tracked = set(subprocess.check_output(
            ["git", "ls-files", "data/processed/*/report.json"],
            cwd=config.ROOT, text=True,
        ).split())
        staged = set(subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--", "data/processed"],
            cwd=config.ROOT, text=True,
        ).split())
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("not a git checkout")
    committed = tracked | {s for s in staged if s.endswith("report.json")}

    on_disk = {
        p.relative_to(config.ROOT).as_posix()
        for p in config.PROCESSED_DIR.glob("*/report.json")
    }
    untracked = sorted(on_disk - committed)
    assert not untracked, (
        "report.json on disk but NOT git-tracked (gitignore phantom — force-add with "
        "`git add -f`):\n" + "\n".join(untracked)
    )


def test_every_committed_report_is_gov_sourced():
    """Corpus-wide provenance guard: EVERY structured report (FERC audits, prudence
    reviews, and state audits alike) must carry an official-government source_page_url
    AND pdf_download_url — not just the seeded ones. Encodes the 2026-06-02 corpus
    audit so a future non-gov record can never slip in unnoticed. (`archived_via` is
    exempt: it intentionally points to the Internet Archive snapshot used to recover
    a ferc.gov listing, while the document itself comes from elibrary.ferc.gov.)"""
    paths = sorted(config.PROCESSED_DIR.glob("*/report.json"))
    assert paths, "no processed report.json found"
    for p in paths:
        d = json.loads(p.read_text(encoding="utf-8"))
        assert sources.is_official_gov(d["source_page_url"]), f"{p.parent.name}: {d['source_page_url']}"
        assert sources.is_official_gov(d["pdf_download_url"]), f"{p.parent.name}: {d['pdf_download_url']}"


# Garbage signatures a loose/marker-based parser produces (regression for the
# 2026-06-23 cleanups: NJ Liberty TOC-leader "findings", the PSE&G Overland 1.8 MB
# runaway row, and rate-case TOC fragments). Findings/recs are verbatim quotes — none
# of these may ever appear in committed data again.
_TOC_LEADER_RE = re.compile(r"\.{6,}|…{2,}")   # dotted / middle-dot Table-of-Contents leaders
_CID_ARTIFACT = "(cid:"                          # PDF glyph-extraction artifact
_MAX_FIELD_CHARS = 15000                          # a real verbatim finding/rec is far shorter


def _finding_fields(finding: dict) -> list[tuple[str, str]]:
    """(label, text) for every quoted field on a finding + its recommendations."""
    out = [("title", finding.get("title") or ""), ("summary", finding.get("summary") or "")]
    out += [("rec", r.get("text") or "") for r in finding.get("recommendations", [])]
    return out


def test_no_garbled_findings_in_committed_corpus():
    """Corpus-wide data-quality guard. Every committed finding/recommendation is a
    verbatim quote, so none may be Table-of-Contents furniture, a glyph artifact, a
    runaway field that absorbed the document, or a contentless title. This catches the
    whole class of loose-parser garbage cleaned 2026-06-23 — see ISSUES.md."""
    offenders: list[str] = []
    for p in sorted(config.PROCESSED_DIR.glob("*/report.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        rid = p.parent.name
        for f in d.get("findings", []):
            title = (f.get("title") or "").strip()
            # A finding title must carry real content (the garbage titles were "s",
            # page numbers, bare punctuation).
            if len(re.sub(r"[^A-Za-z0-9]", "", title)) < 2:
                offenders.append(f"{rid}: contentless finding title {title!r}")
            for label, text in _finding_fields(f):
                if _TOC_LEADER_RE.search(text):
                    offenders.append(f"{rid}: {label} is a TOC leader: {text[:60]!r}")
                if _CID_ARTIFACT in text:
                    offenders.append(f"{rid}: {label} has a (cid:) artifact: {text[:60]!r}")
                if len(text) > _MAX_FIELD_CHARS:
                    offenders.append(f"{rid}: {label} is {len(text)} chars (runaway row?)")
    assert not offenders, "garbled findings in committed corpus:\n" + "\n".join(offenders[:40])


def test_state_rate_case_reports_are_metadata_only():
    """State rate-case orders/testimony/settlements are free-form legal prose with
    no enumerable findings structure to anchor a parser on. A prior parser
    (`_extract_rate_case_findings`, removed 2026-07-06) grabbed a blind +/-100/150
    char window around any "$N ... disallow/approve" or "settlement ... agreement"
    match and called it a "finding" — on real documents this produced mid-sentence
    fragments (titles like "Settlement: Agreement", summaries starting
    lowercase-mid-word) in 528 of the corpus's then-1341 findings, spanning 41
    reports — the same "loose marker-based parser harvests garbage" anti-pattern
    documented in CLAUDE.md/AGENTS.md. Every state_rate_case record must stay
    metadata-only (structured=False, findings=[]), matching the prudence_review
    default. See ISSUES.md 2026-07-06."""
    offenders = []
    for p in sorted(config.PROCESSED_DIR.glob("*/report.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("collection") != "state_rate_case":
            continue
        if d.get("findings") or d.get("structured", True):
            offenders.append(p.parent.name)
    assert not offenders, f"state_rate_case reports must be metadata-only: {offenders}"


def test_check_offline_rejects_quote_spanning_summary_and_recommendation():
    """Regression (2026-07-06 code review): check_offline used to join summary +
    every recommendation's text with a single space before the substring check, so
    a quote that only exists as an artifact of that join (never actually verbatim
    in either field) would incorrectly pass as 'self-consistent'."""
    from pipeline import verify_amounts

    finding = {
        "index": 1,
        "summary": "The company failed to recover",
        "recommendations": [{"number": 1, "text": "$500,000 from the disallowed costs."}],
        # This string never appears verbatim in EITHER field alone — only as an
        # artifact of joining them with " ".
        "amount_usd_quote": "failed to recover $500,000 from the disallowed costs.",
        "amount_usd": 500000.0,
        "amount_usd_page": 4,
    }
    fails = verify_amounts.check_offline("test-report", finding)
    assert any("not a substring" in f for f in fails), f"expected a substring failure, got: {fails}"


def test_amount_usd_citations_are_self_consistent():
    """Corpus-wide OFFLINE guard (BACKLOG P1 #4 pilot, 2026-07-06): every committed
    finding carrying amount_usd must have amount_usd/_quote/_page set together (never
    partial), the quote must be a verbatim substring of that SAME finding's own
    summary/recommendations (proves the citation wasn't invented), and the dollar
    figure embedded in the quote must re-parse to exactly amount_usd. This is the
    fast, no-network tier of pipeline.verify_amounts — run with --live for the
    additional live source-page recheck."""
    from pipeline import verify_amounts

    offenders: list[str] = []
    checked = 0
    for p in sorted(config.PROCESSED_DIR.glob("*/report.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for f in d.get("findings", []):
            if f.get("amount_usd") is None:
                continue
            checked += 1
            offenders.extend(verify_amounts.check_offline(p.parent.name, f))
    assert not offenders, "amount_usd citation problems:\n" + "\n".join(offenders[:40])
    # Not a hard requirement (the pilot may still be in progress), but surface the
    # count so a future reader can see how far the rollout has gotten.
    logging.getLogger(__name__).info("checked %d cited finding(s)", checked)


def test_committed_seeds_have_unique_pdf_urls():
    """No two seeds may point at the same PDF URL — that's the same document seeded
    twice (regression for the 2026-06-08 wave-2 dedup: parallel research agents
    re-found records already in the corpus). Distinct documents within one docket
    (testimony panels, audit parts) legitimately share a docket but NOT a pdf_url."""
    seen: dict[str, str] = {}
    dupes: list[str] = []
    for path in sorted(config.SEEDS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue  # Skip non-list seed files (e.g., tier3_targets.json which is a dict)
        for d in data:
            url = d["pdf_url"]
            if url in seen:
                dupes.append(f"{d['id']} == {seen[url]} (same pdf_url {url})")
            else:
                seen[url] = d["id"]
    assert not dupes, "duplicate pdf_url across seeds:\n" + "\n".join(dupes)


def test_ferc_audits_trace_to_listing():
    """Provenance guard for the FERC-audit corpus: every structured `ferc_audit`
    report must trace back to a record in the browser-captured `data/listing.json`
    (by accession number or id). The listing IS the official ferc.gov/audits index,
    so a `ferc_audit` report that isn't in it would be an invented document — the
    same fabrication failure mode caught for seed-backed records, on the FERC side."""
    listing = json.loads(config.LISTING_PATH.read_text(encoding="utf-8"))
    listing_acc = {e.get("accession_number") for e in listing}
    listing_ids = {e.get("id") for e in listing}
    untraceable: list[str] = []
    n = 0
    for p in sorted(config.PROCESSED_DIR.glob("*/report.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("collection") != "ferc_audit":
            continue
        n += 1
        if d.get("accession_number") not in listing_acc and d["id"] not in listing_ids:
            untraceable.append(f"{d['id']} (acc={d.get('accession_number')})")
    assert n > 0, "no ferc_audit reports found"
    assert not untraceable, "ferc_audit reports not traceable to listing.json:\n" + "\n".join(untraceable)


def test_all_seed_files_validate_and_have_unique_ids():
    """Every committed seed must parse cleanly (each record a valid SourceSeed) and
    use globally-unique ids — the id is also the on-disk processed dir + raw
    filename, so a collision would silently overwrite another document."""
    seed_paths = sorted(config.SEEDS_DIR.glob("*.json"))
    assert seed_paths, "no seed files found"
    all_ids: list[str] = []
    for path in seed_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue  # Skip non-list seed files (e.g., tier3_targets.json which is a dict)
        seeds = [SourceSeed.model_validate(d) for d in data]  # raises on any bad record
        assert seeds, f"{path.name} is empty"
        assert all(s.collection in {"state_audit", "prudence_review", "state_rate_case", "state_reference"} for s in seeds)
        all_ids += [s.id for s in seeds]
    assert len(set(all_ids)) == len(all_ids), "duplicate seed id across seed files"


def test_verify_sources_load_seeds_skips_non_list_files():
    """`verify_sources._load_seeds` must tolerate non-SourceSeed files in
    data/seeds/ (e.g. tier3_targets.json, a state-keyed planning dict) instead of
    crashing with 'str object does not support item assignment'. Regression for the
    fabrication-sweep crash that blocked pre-commit verification (2026-06-18)."""
    from pipeline import verify_sources

    seeds = verify_sources._load_seeds()  # must not raise
    assert seeds, "expected seeds to load"
    assert all(isinstance(rec, dict) and "id" in rec for rec in seeds.values())


def test_verify_sources_company_token_matching():
    """`verify_sources` --live content-match: distinctive company tokens are found
    in real document text (no false MISMATCH), and a genuinely wrong document — one
    that never names the claimed company — is flagged. Guards the offline core of
    the deep re-fetch check so a future tweak can't silently gut it (the WGL
    PROJECTpipes false-positive that first-6-pages scanning produced, 2026-07-10)."""
    from pipeline import verify_sources as vs

    # Corporate suffixes / industry words are dropped; the brand/geographic
    # remainder is what proves identity.
    assert vs.company_tokens("Pacific Gas and Electric Company") == ["pacific"]
    assert "pepco" in vs.company_tokens("Potomac Electric Power Company (Pepco)")
    assert vs.company_tokens("Avista Corporation") == ["avista"]

    # A real audit that names the utility only deep inside still matches on the
    # full-doc fallback text.
    body = "Management Audit of PROJECTpipes ... the Washington Gas Light Company system"
    assert vs.content_match_fails("Washington Gas Light Company", body) == []

    # Glyph-spaced covers ("F P L") still match via the despaced pass.
    assert vs.content_match_fails("Florida Power & Light Company", "review of f l o r i d a") == []

    # A wrong document — never mentions the claimed company — is flagged.
    wrong = "This is the annual report of Some Other Utility, Inc. for fiscal year 2024."
    assert vs.content_match_fails("Pacific Gas and Electric Company", wrong)


def test_seed_inventory_covers_every_committed_seed():
    """`pipeline.seed_inventory.load_inventory` (the finder-agent dedup harness)
    must list every committed seed id, so a finder agent dedupes against the full
    corpus — not a hand-written partial list (which let the 2026-06-19 CA/MO
    near-duplicates through). Tolerates non-list planning files."""
    from pipeline import seed_inventory

    rows = seed_inventory.load_inventory()
    assert rows, "inventory is empty"
    assert all(r.get("id") and r.get("jurisdiction") for r in rows)
    inv_ids = {r["id"] for r in rows}
    assert len(inv_ids) == len(rows), "duplicate id in inventory"

    seed_ids: set[str] = set()
    for path in sorted(config.SEEDS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            seed_ids |= {r["id"] for r in data if isinstance(r, dict) and "id" in r}
    missing = seed_ids - inv_ids
    assert not missing, f"inventory omits seeded docs: {sorted(missing)[:5]}"


# --- fetch resilience (timeouts / throttling / broken TLS / WAF / placeholders) ---

import logging  # noqa: E402

import requests as _requests  # noqa: E402


class _FakeResp:
    def __init__(self, status_code, content=b"", content_type=""):
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}


class _FakeSession:
    """Yields a queued list of outcomes (a _FakeResp to return, or an Exception
    to raise); repeats the last outcome once the queue is drained."""

    def __init__(self, *outcomes):
        self._q = list(outcomes)
        self.calls = 0

    def get(self, url, timeout=None, headers=None):
        self.calls += 1
        self.last_headers = headers
        o = self._q.pop(0) if len(self._q) > 1 else self._q[0]
        if isinstance(o, Exception):
            raise o
        return o


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(sources.time, "sleep", lambda *_: None)


def test_fetch_doc_fails_fast_on_broken_tls(tmp_path):
    s = _FakeSession(_requests.exceptions.SSLError("hostname mismatch"))
    with pytest.raises(sources.SourceFetchError, match="TLS verification failed"):
        sources.fetch_doc(s, _seed(), tmp_path)
    assert s.calls == 1  # no pointless retries on a broken cert


def test_fetch_doc_fails_on_waf_after_browser_ua_fallback(tmp_path):
    """A 403 triggers ONE honest-first browser-UA retry; if that is ALSO blocked,
    fetch fails with the WAF guidance. Two calls total (informative UA, then browser UA)."""
    s = _FakeSession(_FakeResp(403, b"<html>Access Denied</html>", "text/html"))
    with pytest.raises(sources.SourceFetchError, match="browser-UA fallback also failed"):
        sources.fetch_doc(s, _seed(), tmp_path)
    assert s.calls == 2


def test_fetch_doc_browser_ua_fallback_succeeds(tmp_path):
    """The michigan.gov MPSC case: our informative UA gets 403, but the same public
    PDF is served to a browser UA. The 403→browser-UA retry downloads it."""
    pdf = b"%PDF-" + b"y" * 20000
    s = _FakeSession(_FakeResp(403, b"<html>Access Denied</html>", "text/html"),
                     _FakeResp(200, pdf, "application/pdf"))
    out = sources.fetch_doc(s, _seed(), tmp_path)
    assert out.read_bytes() == pdf
    assert s.calls == 2
    assert s.last_headers["User-Agent"] == config.BROWSER_USER_AGENT  # retry used the browser UA


def test_fetch_doc_retries_connection_error_then_succeeds(tmp_path):
    pdf = b"%PDF-" + b"x" * 4000
    s = _FakeSession(_requests.exceptions.ConnectionError("reset"), _FakeResp(200, pdf, "application/pdf"))
    out = sources.fetch_doc(s, _seed(), tmp_path)
    assert out.exists() and out.read_bytes() == pdf
    assert s.calls == 2  # backed off and retried the throttled connection


def test_fetch_doc_warns_on_suspiciously_small_pdf(tmp_path, caplog):
    tiny = b"%PDF-1.4 blank"  # has the magic but well under _SUSPICIOUS_PDF_BYTES
    s = _FakeSession(_FakeResp(200, tiny, "application/pdf"))
    with caplog.at_level(logging.WARNING):
        out = sources.fetch_doc(s, _seed(), tmp_path)
    assert out.exists()
    assert any("possible placeholder" in r.message for r in caplog.records)


def test_fetch_doc_warns_on_5kb_placeholder(tmp_path, caplog):
    # The observed real failure mode: AZ edocket.azcc.gov/docketpdf/ returns a
    # blank ~5 KB %PDF. The threshold must sit ABOVE this size (it didn't at 3 KB).
    blank_5kb = b"%PDF-1.4\n" + b"\x00" * 5000  # ~5 KB, valid magic
    assert len(blank_5kb) > 3000 and len(blank_5kb) < sources._SUSPICIOUS_PDF_BYTES
    s = _FakeSession(_FakeResp(200, blank_5kb, "application/pdf"))
    with caplog.at_level(logging.WARNING):
        out = sources.fetch_doc(s, _seed(), tmp_path)
    assert out.exists()
    assert any("possible placeholder" in r.message for r in caplog.records)


def test_cached_small_pdf_rewarns_on_rerun(tmp_path, caplog):
    # A previously-cached blank placeholder must NOT go silent on a re-run.
    seed = _seed()
    dest = tmp_path / f"{seed.id}.pdf"
    dest.write_bytes(b"%PDF-1.4\n" + b"\x00" * 5000)  # ~5 KB cached placeholder
    s = _FakeSession(_FakeResp(500, b"should-not-be-called"))  # cache hit => no fetch
    with caplog.at_level(logging.WARNING):
        out = sources.fetch_doc(s, seed, tmp_path)
    assert out == dest and s.calls == 0  # served from cache, no network
    assert any("possible placeholder" in r.message for r in caplog.records)


def test_cached_full_size_pdf_is_silent(tmp_path, caplog):
    seed = _seed()
    dest = tmp_path / f"{seed.id}.pdf"
    dest.write_bytes(b"%PDF-1.4\n" + b"x" * 20000)  # a normal-size cached doc
    s = _FakeSession(_FakeResp(500, b"x"))
    with caplog.at_level(logging.WARNING):
        sources.fetch_doc(s, seed, tmp_path)
    assert not any("possible placeholder" in r.message for r in caplog.records)


def test_fetch_doc_exhausts_retries_on_server_error(tmp_path):
    s = _FakeSession(_FakeResp(500, b"oops", "text/html"))
    with pytest.raises(sources.SourceFetchError, match="unexpected response: 500"):
        sources.fetch_doc(s, _seed(), tmp_path)
    assert s.calls == config.MAX_RETRIES


# --- live source verifier (pipeline.verify_sources) classification logic ---

from pipeline import verify_sources  # noqa: E402


def test_verify_sources_classifies_dead_nonpdf_and_proven(monkeypatch):
    """The fabrication catcher's classification rules:
      - fetch=true that 404s (TX `…_1234567.PDF`) → DEAD.
      - fetch=true that 200s with non-PDF (FL `06790-2024.pdf` HTML) → NON_PDF.
      - page_count>0 fetched record → PROVEN (no network call).
      - a 404 on a BROWSER-CAPTURED (fetch=false) URL is still DEAD (the captured URL
        is wrong/invented) — but a WAF/HTML response on one is CHECK, not a failure.
      - eLibrary accession-backed records (FERC prudence) → CHECK (need the cookie
        dance, not a plain GET) — never a false NON_PDF.
    Regression for the 2026-06-08 verifier false-positive fix."""
    seeds = {
        "fetch-true-404": {"id": "fetch-true-404", "pdf_url": "https://x.gov/a.PDF", "fetch": True, "_file": "x.json"},
        "fetch-true-html": {"id": "fetch-true-html", "pdf_url": "https://x.gov/b.pdf", "fetch": True, "_file": "x.json"},
        "real-fetched": {"id": "real-fetched", "pdf_url": "https://x.gov/c.pdf", "fetch": True, "_file": "x.json"},
        "captured-html": {"id": "captured-html", "pdf_url": "https://x.gov/d.htm", "fetch": False, "_file": "x.json"},
        "captured-404": {"id": "captured-404", "pdf_url": "https://x.gov/e", "fetch": False, "_file": "x.json"},
        "elibrary-acc": {"id": "elibrary-acc", "pdf_url": "https://elibrary.ferc.gov/...DownloadPDF", "fetch": True, "accession": "20230515-3006", "_file": "ferc_prudence.json"},
    }
    reports = {
        "fetch-true-404": {"id": "fetch-true-404", "collection": "state_audit", "page_count": 0},
        "fetch-true-html": {"id": "fetch-true-html", "collection": "state_audit", "page_count": 0},
        "real-fetched": {"id": "real-fetched", "collection": "state_rate_case", "page_count": 42},
        "captured-html": {"id": "captured-html", "collection": "state_audit", "page_count": 0},
        "captured-404": {"id": "captured-404", "collection": "state_audit", "page_count": 0},
        "elibrary-acc": {"id": "elibrary-acc", "collection": "prudence_review", "page_count": 0},
    }
    probes = {
        "https://x.gov/a.PDF": (404, "text/html", False),
        "https://x.gov/b.pdf": (200, "text/html", False),   # resolves, but NOT a pdf
        "https://x.gov/d.htm": (200, "text/html", False),   # browser-captured HTML — CHECK
        "https://x.gov/e": (404, "text/html", False),       # captured URL that 404s — DEAD
    }
    monkeypatch.setattr(verify_sources, "_load_seeds", lambda: seeds)
    monkeypatch.setattr(verify_sources, "_load_reports", lambda: reports)
    monkeypatch.setattr(verify_sources, "probe", lambda url, timeout=25: probes[url])

    v = verify_sources.verify()
    assert any("fetch-true-404" in s for s in v["DEAD"])
    assert any("fetch-true-html" in s for s in v["NON_PDF"])
    assert "real-fetched" in v["PROVEN"]
    assert any("captured-html" in s for s in v["CHECK"])
    assert any("captured-404" in s for s in v["DEAD"])        # 404 is suspicious even when browser-captured
    assert any("elibrary-acc" in s for s in v["CHECK"])       # accession-backed -> CHECK, not NON_PDF
    assert not any("elibrary-acc" in s for s in v["NON_PDF"])


def test_process_seed_does_not_clobber_existing_findings(tmp_path):
    """No-clobber guard (regression for the recurring 2026-06-08 footgun): re-running
    pipeline.sources on a seed whose record was already structured by pipeline.structure
    must NOT overwrite its findings with a metadata-only record. Repeatedly wiped ComEd,
    BGE (17 findings), PSE&G, etc. when a seed file mixed structured + new records."""
    seed = _seed(id="2024-01-01_x_state-rate-case", collection="state_rate_case", parse=False, fetch=False)
    processed = tmp_path / "processed"
    out = processed / seed.id
    out.mkdir(parents=True)
    # An existing report.json with findings (as pipeline.structure would have written).
    structured = {"id": seed.id, "collection": "state_rate_case", "finding_count": 17,
                  "findings": [{"index": 1, "title": "t", "summary": None, "recommendations": []}],
                  "structured": True}
    (out / "report.json").write_text(json.dumps(structured), encoding="utf-8")

    seed_file = tmp_path / "s.json"
    seed_file.write_text(json.dumps([seed.model_dump(mode="json")]), encoding="utf-8")
    sources.process_seed(seed_file, raw_dir=tmp_path / "raw", processed_dir=processed)

    after = json.loads((out / "report.json").read_text())
    assert after["finding_count"] == 17        # findings preserved, not clobbered
    assert after["structured"] is True
