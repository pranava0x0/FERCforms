"""Tests for the generic source-ingestion path (pipeline/sources.py).

Covers the metadata-only structuring used for prudence / state-PUC documents:
the FERC executive-summary parser doesn't fit them, so they're captured with
their source and full provenance but NOT machine-extracted into findings
(see the module docstring + the multi-source policy).
"""
from __future__ import annotations

import json
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
        for d in json.loads(path.read_text(encoding="utf-8")):
            assert sources.is_official_gov(d["pdf_url"]), f"{path.name}: {d['pdf_url']}"
            assert sources.is_official_gov(d["source_page_url"]), f"{path.name}: {d['source_page_url']}"


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


def test_all_seed_files_validate_and_have_unique_ids():
    """Every committed seed must parse cleanly (each record a valid SourceSeed) and
    use globally-unique ids — the id is also the on-disk processed dir + raw
    filename, so a collision would silently overwrite another document."""
    seed_paths = sorted(config.SEEDS_DIR.glob("*.json"))
    assert seed_paths, "no seed files found"
    all_ids: list[str] = []
    for path in seed_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        seeds = [SourceSeed.model_validate(d) for d in data]  # raises on any bad record
        assert seeds, f"{path.name} is empty"
        assert all(s.collection in {"state_audit", "prudence_review"} for s in seeds)
        all_ids += [s.id for s in seeds]
    assert len(set(all_ids)) == len(all_ids), "duplicate seed id across seed files"


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

    def get(self, url, timeout=None):
        self.calls += 1
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


def test_fetch_doc_fails_fast_on_waf_or_login_wall(tmp_path):
    s = _FakeSession(_FakeResp(403, b"<html>Access Denied</html>", "text/html"))
    with pytest.raises(sources.SourceFetchError, match="WAF or login wall"):
        sources.fetch_doc(s, _seed(), tmp_path)
    assert s.calls == 1


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


def test_fetch_doc_exhausts_retries_on_server_error(tmp_path):
    s = _FakeSession(_FakeResp(500, b"oops", "text/html"))
    with pytest.raises(sources.SourceFetchError, match="unexpected response: 500"):
        sources.fetch_doc(s, _seed(), tmp_path)
    assert s.calls == config.MAX_RETRIES
