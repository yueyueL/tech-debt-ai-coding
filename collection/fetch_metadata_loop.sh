#!/bin/bash
# Auto-retry metadata fetch script
# Runs every hour until all repos have metadata
#
# Usage:
#   chmod +x fetch_metadata_loop.sh
#   nohup ./fetch_metadata_loop.sh > fetch_metadata.log 2>&1 &

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

REPOS_FILE="${1:-result/ai_repos.json}"

echo "=========================================="
echo "Starting metadata fetch loop"
echo "Repos file: $REPOS_FILE"
echo "Time: $(date)"
echo "=========================================="

MAX_RETRIES=20          # Maximum 20 runs (~20 hours)
WAIT_SECONDS=3660       # Wait 61 minutes between runs (respects rate limits)

for i in $(seq 1 $MAX_RETRIES); do
    echo ""
    echo "=========================================="
    echo "Run $i of $MAX_RETRIES"
    echo "Time: $(date)"
    echo "=========================================="
    
    # Run metadata fetch
    python3 main.py metadata "$REPOS_FILE"
    
    # Check if all repos have metadata
    if python3 -c "
import json
data = json.load(open('$REPOS_FILE'))
repos = data.get('repos', [])
missing = sum(1 for r in repos if r.get('stars') == 0 and r.get('language') is None)
print(f'Repos without metadata: {missing}/{len(repos)}')
if missing == 0:
    print('ALL DONE!')
    exit(0)
else:
    exit(1)
" 2>/dev/null; then
        echo ""
        echo "=========================================="
        echo "All repos have metadata! Exiting."
        echo "Time: $(date)"
        echo "=========================================="
        exit 0
    fi
    
    if [ $i -lt $MAX_RETRIES ]; then
        echo ""
        echo "Waiting $(($WAIT_SECONDS / 60)) minutes for rate limit reset..."
        sleep $WAIT_SECONDS
    fi
done

echo ""
echo "=========================================="
echo "Reached max retries ($MAX_RETRIES). Some repos may still need metadata."
echo "Run again later if needed."
echo "=========================================="
