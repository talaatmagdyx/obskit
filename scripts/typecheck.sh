#!/bin/bash
# =============================================================================
# Type Check Script
# Runs mypy with strict mode for type checking
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=============================================="
echo "Running Type Checks (mypy --strict)"
echo "=============================================="
echo ""

# Check if mypy is installed
if ! command -v mypy &> /dev/null; then
    echo "Error: mypy is not installed. Install with: pip install mypy"
    exit 1
fi

echo "Running mypy..."
echo "----------------------------------------------"

mypy src/obskit --strict

echo ""
echo "=============================================="
echo "Type checking passed!"
echo "=============================================="

