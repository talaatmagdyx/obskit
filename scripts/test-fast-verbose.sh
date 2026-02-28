#!/bin/bash
# Fast test runner with verbose progress - useful for debugging hangs

set -e

echo "🚀 Running tests in FAST mode with verbose progress..."
python -m pytest packages/ tests/ \
    -v \
    -n auto \
    --dist=worksteal \
    --no-cov \
    --tb=short \
    --durations=10 \
    -W ignore::pytest_benchmark.logger.PytestBenchmarkWarning \
    "$@"

echo "✅ Tests completed!"

