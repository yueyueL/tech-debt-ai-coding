#!/bin/bash
# =============================================================================
# AI-Code Collector - Docker runner
#
# Usage:
#   ./run.sh discover-test              # Quick test: 1 month, 100 rows
#   ./run.sh discover 2025-01-01 2025-12-31  # Full range
#   ./run.sh scan owner/repo            # Scan a specific repo
#   ./run.sh batch-scan 50 20           # Batch scan: min 50 stars, top 20
#   ./run.sh metadata                   # Fetch GitHub metadata
#   ./run.sh tests                      # Run detection tests
#   ./run.sh shell                      # Interactive shell
# =============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Build image if needed
build() {
    echo "Building Docker image..."
    docker compose build --quiet
}

case "${1:-help}" in
    # =========================================================================
    # DISCOVER
    # =========================================================================
    discover-test)
        build
        echo "Running discover test (1 month, 100 rows)..."
        START_DATE="${2:-2025-06-01}" \
        END_DATE="${3:-2025-06-30}" \
        LIMIT="${4:-100}" \
        docker compose run --rm discover
        ;;

    discover)
        build
        START="${2:?Usage: ./run.sh discover START_DATE END_DATE}"
        END="${3:?Usage: ./run.sh discover START_DATE END_DATE}"
        echo "Running full discover: $START to $END..."
        START_DATE="$START" \
        END_DATE="$END" \
        docker compose run --rm discover-full
        ;;

    discover-dry)
        build
        START_DATE="${2:-2025-01-01}" \
        END_DATE="${3:-2025-01-31}" \
        docker compose run --rm discover-dry
        ;;

    # =========================================================================
    # SCAN
    # =========================================================================
    scan)
        REPO="${2:?Usage: ./run.sh scan owner/repo [limit]}"
        LIMIT="${3:-1000}"
        build
        echo "Scanning $REPO (git clone, limit $LIMIT)..."
        REPO="$REPO" LIMIT="$LIMIT" docker compose run --rm scan
        ;;

    scan-api)
        REPO="${2:?Usage: ./run.sh scan-api owner/repo [limit]}"
        LIMIT="${3:-500}"
        build
        echo "Scanning $REPO (GitHub API, limit $LIMIT)..."
        REPO="$REPO" LIMIT="$LIMIT" docker compose run --rm scan-api
        ;;

    # =========================================================================
    # BATCH-SCAN
    # =========================================================================
    batch-scan)
        MIN_STARS="${2:-50}"
        LIMIT="${3:-20}"
        build
        echo "Batch scanning: min $MIN_STARS stars, top $LIMIT repos..."
        MIN_STARS="$MIN_STARS" LIMIT="$LIMIT" docker compose run --rm batch-scan
        ;;

    # =========================================================================
    # METADATA
    # =========================================================================
    metadata)
        build
        docker compose run --rm metadata
        ;;

    metadata-loop)
        build
        echo "Starting metadata fetch loop (auto-retry, runs every hour)..."
        docker compose run --rm -d metadata-loop
        echo "Running in background. Check result/ for progress."
        ;;

    # =========================================================================
    # TESTS
    # =========================================================================
    tests)
        build
        echo "Running detection tests..."
        docker compose run --rm test-detection
        echo ""
        echo "Running pattern audit..."
        docker compose run --rm test-audit
        ;;

    # =========================================================================
    # SHELL
    # =========================================================================
    shell)
        build
        docker compose run --rm shell
        ;;

    # =========================================================================
    # HELP
    # =========================================================================
    *)
        cat <<'EOF'
AI-Code Collector - Docker runner

DISCOVER (BigQuery - find AI repos):
  ./run.sh discover-test                          Quick test: 1 month, 100 rows
  ./run.sh discover-test 2025-01-01 2025-01-31    Custom date range test
  ./run.sh discover 2024-01-01 2026-01-31         Full collection (with checkpoint)
  ./run.sh discover-dry                           Show SQL without executing

SCAN (Deep scan a repo for AI commits):
  ./run.sh scan Aider-AI/aider                    Git clone mode (no token needed)
  ./run.sh scan n8n-io/n8n 2000                   With commit limit
  ./run.sh scan-api n8n-io/n8n                    GitHub API mode (needs GITHUB_TOKEN)

BATCH-SCAN (Scan multiple repos from discover results):
  ./run.sh batch-scan                             Default: min 50 stars, top 20
  ./run.sh batch-scan 100 50                      Min 100 stars, top 50 repos

METADATA (Enrich repos with stars/language):
  ./run.sh metadata                               One-time fetch
  ./run.sh metadata-loop                          Auto-retry loop (background)

TESTS:
  ./run.sh tests                                  Run all tests

UTILITIES:
  ./run.sh shell                                  Interactive shell

ENVIRONMENT VARIABLES:
  GITHUB_TOKEN          GitHub personal access token (for scan-api, metadata)
  GOOGLE_APPLICATION_CREDENTIALS   GCP service account JSON (for discover)
EOF
        ;;
esac
