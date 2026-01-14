#!/bin/bash
# Show test failures summary

set -e

echo "🔍 Running tests (will show summary of failures)..."
echo "💡 This may take a moment - tests run in parallel"
echo ""

WORKERS=${WORKERS:-auto}
python -m pytest tests/ \
    -n "$WORKERS" \
    --dist=worksteal \
    --no-cov \
    --tb=line \
    -q \
    --maxfail=20 \
    -W ignore::pytest_benchmark.logger.PytestBenchmarkWarning \
    -W ignore::pluggy.PluggyTeardownRaisedWarning \
    "$@" || true

echo ""
echo "💡 For detailed failure messages, run:"
echo "   pytest tests/ -v --tb=short --no-cov"

