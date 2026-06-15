"""Test Texas PUC audit parser."""
import json
from pathlib import Path
from pipeline.state_structure import parse_tx_findings, structure_tx_audit
from pipeline.models import SourceSeed, PageText
from datetime import date


def test_parse_tx_findings():
    """Test TX findings extraction from sample document."""
    # Load a sample TX audit document
    doc_id = "tx_0000_023_audit-of-the-general-law-division-s-publ"
    text_path = Path("data/processed") / doc_id / "text.json"

    if not text_path.exists():
        print(f"SKIP: {text_path} not found")
        return

    text_data = json.loads(text_path.read_text())
    full_text = "\n".join(p['text'] for p in text_data['pages'])

    findings = parse_tx_findings(full_text)

    assert len(findings) == 3, f"Expected 3 findings, got {len(findings)}"

    # Verify structure
    for title, desc in findings:
        assert title, "Title should not be empty"
        assert desc, "Description should not be empty"
        assert len(title) > 10, "Title should be meaningful"
        assert len(desc) > 50, "Description should be substantial"

    print(f"✓ test_parse_tx_findings: {len(findings)} findings extracted correctly")


def test_structure_tx_audit():
    """Test full structuring of TX audit document."""
    # Load sample document
    doc_id = "tx_0000_018_audit-of-the-consumer-complaint-division"
    report_path = Path("data/processed") / doc_id / "report.json"
    text_path = Path("data/processed") / doc_id / "text.json"

    if not report_path.exists() or not text_path.exists():
        print(f"SKIP: Sample document not found")
        return

    report_data = json.loads(report_path.read_text())
    text_data = json.loads(text_path.read_text())

    # Create seed
    seed = SourceSeed(
        id=report_data['id'],
        company=report_data['company'],
        collection=report_data['collection'],
        jurisdiction=report_data['jurisdiction'],
        source=report_data['source'],
        doc_type=report_data['doc_type'],
        industry=report_data.get('industry'),
        pdf_url=report_data['pdf_download_url'],
        source_page_url=report_data['source_page_url'],
        issued_date=None,
        docket=None,
        captured_at=date.today(),
        source_note=report_data['source_note'],
        parse=True,
        fetch=False,
    )

    # Convert pages
    pages = [
        PageText(
            page=p['page'],
            char_count=p['char_count'],
            is_image_only=p['is_image_only'],
            extractor=p['extractor'],
            text=p['text']
        )
        for p in text_data['pages']
    ]

    # Structure
    result = structure_tx_audit(seed, pages, [])

    assert result is not None, "structure_tx_audit should return a result"
    assert result.finding_count > 0, "Should have extracted findings"
    assert len(result.findings) == result.finding_count, "Finding count should match"

    for finding in result.findings:
        assert finding.title, "Finding should have a title"
        assert finding.summary, "Finding should have a summary"
        assert finding.index > 0, "Finding should have a valid index"

    print(f"✓ test_structure_tx_audit: {result.finding_count} findings structured correctly")


if __name__ == "__main__":
    test_parse_tx_findings()
    test_structure_tx_audit()
    print("\n✓ All TX parser tests passed")
