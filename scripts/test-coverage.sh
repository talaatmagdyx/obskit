#!/bin/bash
# Full test runner with coverage

set -e

echo "📊 Running tests with FULL coverage..."
python -m pytest tests/ \
    --cov=src/obskit \
    --cov-config=.coveragerc \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-report=json:coverage.json \
    --cov-fail-under=100 \
    -n auto \
    --dist=worksteal \
    -W ignore::pytest_benchmark.logger.PytestBenchmarkWarning \
    -W ignore::pluggy.PluggyTeardownRaisedWarning \
    "$@"

echo "✅ Coverage report generated in htmlcov/index.html"

