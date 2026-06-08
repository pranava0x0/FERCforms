#!/bin/bash
# Batch extract and structure rate-case findings (Option D)
# Prerequisite: Rate-case PDFs must be in data/raw/
# Output: Structured findings in docs/data/patterns_by_collection.json

set -e

echo "================================"
echo "RATE-CASE EXTRACTION & STRUCTURING"
echo "================================"

# Step 1: Extract text from rate-case PDFs
echo ""
echo "Step 1/3: Extracting text from rate-case PDFs..."
echo "  (This processes all recent reports; extraction is automatic for PDFs in data/raw/)"
python3 -m pipeline.extract --limit 120

# Step 2: Structure rate-case findings
echo ""
echo "Step 2/3: Structuring rate-case documents with findings extractor..."
python3 -m pipeline.structure

# Step 3: Build final data files
echo ""
echo "Step 3/3: Building final site data files..."
python3 -m pipeline.build

# Step 4: Report results
echo ""
echo "Extraction complete. Summary:"
python3 << 'PYTHON_EOF'
import json
from pathlib import Path

with open('docs/data/reports.json') as f:
    reports = json.load(f)

rate_cases = [r for r in reports if r.get('collection') == 'state_rate_case']
total_findings = sum(r.get('finding_count', 0) for r in rate_cases)
docs_with_findings = len([r for r in rate_cases if r.get('finding_count', 0) > 0])

print(f"Rate cases processed: {len(rate_cases)}")
print(f"Total findings extracted: {total_findings}")
print(f"Documents with findings: {docs_with_findings}")

if total_findings > 0:
    print(f"Average findings per doc: {total_findings / docs_with_findings:.1f}")

    # Show top documents
    print("\nTop rate-case documents by findings:")
    sorted_rc = sorted(rate_cases, key=lambda r: r.get('finding_count', 0), reverse=True)[:10]
    for r in sorted_rc:
        if r.get('finding_count', 0) > 0:
            print(f"  {r['company'][:45]:45} {r.get('finding_count', 0):3} findings")

# Check themes
with open('docs/data/patterns_by_collection.json') as f:
    by_coll = json.load(f)

if 'state_rate_case' in by_coll:
    themes = by_coll['state_rate_case'].get('themes', [])
    print(f"\nRate-case themes identified: {len(themes)}")
    for theme in themes[:5]:
        print(f"  - {theme}")
    if len(themes) > 5:
        print(f"  ... and {len(themes) - 5} more")

PYTHON_EOF

echo ""
echo "Done! Check docs/data/patterns_by_collection.json for rate-case findings."
