#!/bin/bash
# =============================================================================
# Local CI Script
# Runs the full CI pipeline locally before pushing
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=============================================="
echo "Running Full CI Pipeline Locally"
echo "=============================================="
echo ""

# Track timing
START_TIME=$(date +%s)

# Step 1: Lint
echo ""
echo "STEP 1/5: Linting"
echo "=============================================="
"$SCRIPT_DIR/lint.sh"

# Step 2: Type Check
echo ""
echo "STEP 2/5: Type Checking"
echo "=============================================="
"$SCRIPT_DIR/typecheck.sh"

# Step 3: Tests
echo ""
echo "STEP 3/5: Running Tests"
echo "=============================================="
"$SCRIPT_DIR/test.sh"

# Step 4: Documentation
echo ""
echo "STEP 4/5: Building Documentation"
echo "=============================================="
"$SCRIPT_DIR/docs.sh"

# Step 5: Package Build
echo ""
echo "STEP 5/5: Building Package"
echo "=============================================="
"$SCRIPT_DIR/release.sh"

# Summary
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "=============================================="
echo "CI Pipeline Complete!"
echo "=============================================="
echo ""
echo "Total time: ${DURATION} seconds"
echo ""
echo "All checks passed:"
echo "  [x] Linting (ruff)"
echo "  [x] Type checking (mypy)"
echo "  [x] Tests (pytest with 100% coverage)"
echo "  [x] Documentation (Sphinx)"
echo "  [x] Package build (twine)"
echo ""
echo "Ready to push!"

