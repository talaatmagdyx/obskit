#!/bin/bash
# Fast test runner - skips coverage for maximum speed

set -e

echo "🚀 Running tests in FAST mode (no coverage)..."
echo "💡 Tip: If tests seem stuck, try: WORKERS=4 $0 (limits parallel workers)"
echo ""

WORKERS=${WORKERS:-auto}
python -m pytest tests/ \
    -q \
    -n "$WORKERS" \
    --dist=worksteal \
    --no-cov \
    --tb=line \
    --durations=5 \
    -W ignore::pytest_benchmark.logger.PytestBenchmarkWarning \
    -W ignore::pluggy.PluggyTeardownRaisedWarning \
    "$@"

echo "✅ Tests completed!"

