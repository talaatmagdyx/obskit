#!/bin/bash
# =============================================================================
# Lint Script
# Runs all code quality checks: ruff linting and formatting
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=============================================="
echo "Running Code Quality Checks"
echo "=============================================="
echo ""

# Check if ruff is installed
if ! command -v ruff &> /dev/null; then
    echo "Error: ruff is not installed. Install with: pip install ruff"
    exit 1
fi

echo "1. Running ruff linter..."
echo "----------------------------------------------"
ruff check src/ tests/
echo "   Linting passed!"
echo ""

echo "2. Checking code formatting..."
echo "----------------------------------------------"
ruff format --check src/ tests/
echo "   Formatting check passed!"
echo ""

echo "=============================================="
echo "All code quality checks passed!"
echo "=============================================="

