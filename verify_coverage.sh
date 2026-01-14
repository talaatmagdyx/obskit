#!/bin/bash
# Verify 100% Test Coverage
# ==========================
# This script runs tests and verifies 100% coverage is achieved

set -e

echo "🧪 Running tests with coverage..."
echo ""

# Clean previous coverage data
rm -f .coverage coverage.xml
rm -rf htmlcov/

# Run tests with coverage
pytest tests/ \
    -v \
    --cov=src/obskit \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=xml \
    --tb=short \
    -x  # Stop on first failure

echo ""
echo "📊 Coverage Summary:"
echo ""

# Extract coverage percentage
COVERAGE=$(pytest tests/ --cov=src/obskit --cov-report=term-missing --quiet 2>&1 | grep "TOTAL" | awk '{print $NF}' | sed 's/%//')

if [ -n "$COVERAGE" ]; then
    echo "Coverage: ${COVERAGE}%"
    
    if (( $(echo "$COVERAGE >= 100" | bc -l) )); then
        echo ""
        echo "✅ SUCCESS: 100% coverage achieved!"
        echo ""
        echo "View detailed report:"
        echo "  open htmlcov/index.html"
        exit 0
    else
        echo ""
        echo "❌ FAILURE: Coverage is ${COVERAGE}%, need 100%"
        echo ""
        echo "View missing lines:"
        echo "  open htmlcov/index.html"
        echo ""
        echo "Or check terminal output above for missing lines"
        exit 1
    fi
else
    echo "⚠️  Could not determine coverage percentage"
    echo "Check the output above for details"
    exit 1
fi

