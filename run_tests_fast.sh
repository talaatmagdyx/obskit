#!/bin/bash
# Fast Test Runner
# ================
# Optimized for speed with parallel execution

set -e

echo "🚀 Running tests in parallel (fast mode)..."
echo ""

# Clean previous coverage
rm -f .coverage coverage.xml
rm -rf htmlcov/

# Run tests in parallel with pytest-xdist
# -n auto: Use all available CPU cores
# --durations=10: Show 10 slowest tests
pytest tests/ \
    -v \
    -n auto \
    --durations=10 \
    --cov=src/obskit \
    --cov-report=term-missing \
    --cov-report=html \
    --tb=short \
    -x  # Stop on first failure

echo ""
echo "✅ Tests completed!"
echo ""
echo "View coverage report:"
echo "  open htmlcov/index.html"
echo ""
echo "View slowest tests:"
echo "  pytest tests/ --durations=10"

