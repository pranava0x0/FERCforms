#!/bin/bash
# Ingest state PUC seeds through the pipeline
# Usage: ./scripts/ingest_state_puc_seeds.sh [seed_file]
# Default: all *.json in data/seeds/ matching state_puc*

set -euo pipefail

SEED_DIR="data/seeds"
LOG_FILE="logs/ingest_$(date +%Y%m%d_%H%M%S).log"

mkdir -p logs

# If specific seed provided, use that; otherwise find all state_puc seeds
if [ $# -eq 1 ]; then
    SEEDS=("$1")
else
    mapfile -t SEEDS < <(find "$SEED_DIR" -name "state_puc*.json" -type f | sort)
fi

if [ ${#SEEDS[@]} -eq 0 ]; then
    echo "ERROR: No seed files found in $SEED_DIR"
    exit 1
fi

echo "Ingesting ${#SEEDS[@]} seed file(s) at $(date)" | tee -a "$LOG_FILE"

TOTAL_INGESTED=0
TOTAL_FAILED=0

for seed_file in "${SEEDS[@]}"; do
    echo ""
    echo "=== Processing: $seed_file ===" | tee -a "$LOG_FILE"

    # Count records in seed
    seed_count=$(jq 'length' "$seed_file" 2>/dev/null || echo "0")
    echo "Seed file contains $seed_count records" | tee -a "$LOG_FILE"

    # Run pipeline
    if python3 -m pipeline.sources --seed "$seed_file" 2>&1 | tee -a "$LOG_FILE"; then
        echo "✓ Successfully ingested $seed_file" | tee -a "$LOG_FILE"
        ((TOTAL_INGESTED += seed_count))
    else
        echo "✗ Failed to ingest $seed_file" | tee -a "$LOG_FILE"
        ((TOTAL_FAILED += seed_count))
    fi
done

echo ""
echo "=== INGESTION SUMMARY ===" | tee -a "$LOG_FILE"
echo "Total seeds ingested: $TOTAL_INGESTED" | tee -a "$LOG_FILE"
echo "Failed seeds: $TOTAL_FAILED" | tee -a "$LOG_FILE"
echo "Processed documents: $(ls -d data/processed/*/ 2>/dev/null | wc -l)" | tee -a "$LOG_FILE"
echo "Log saved to: $LOG_FILE" | tee -a "$LOG_FILE"

exit 0
