#!/bin/bash
# =============================================================================
# Test Script
# Runs pytest with coverage reporting and enforcement
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=============================================="
echo "Running Tests with Coverage"
echo "=============================================="
echo ""

# Default coverage threshold
COVERAGE_THRESHOLD=${COVERAGE_THRESHOLD:-100}

# Parse arguments
VERBOSE=""
PARALLEL=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -p|--parallel)
            PARALLEL="-n auto"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -v, --verbose   Verbose output"
            echo "  -p, --parallel  Run tests in parallel"
            echo "  -h, --help      Show this help"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "Error: pytest is not installed. Install with: pip install pytest pytest-cov"
    exit 1
fi

echo "Running pytest with coverage..."
echo "Coverage threshold: ${COVERAGE_THRESHOLD}%"
echo "----------------------------------------------"
echo ""

pytest tests/ $VERBOSE $PARALLEL \
    --cov=src/obskit \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-report=xml:coverage.xml \
    --cov-fail-under=$COVERAGE_THRESHOLD

echo ""
echo "=============================================="
echo "All tests passed with ${COVERAGE_THRESHOLD}%+ coverage!"
echo "=============================================="
echo ""
echo "Coverage reports generated:"
echo "  - Terminal: above"
echo "  - HTML: htmlcov/index.html"
echo "  - XML: coverage.xml"

