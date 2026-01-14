#!/bin/bash
# Check Test Coverage Script
# ==========================
# This script runs tests and generates a coverage report

set -e

echo "🧪 Running tests with coverage..."
echo ""

# Clean previous coverage data
rm -f .coverage coverage.xml
rm -rf htmlcov/

# Run tests with coverage
python3 -m pytest tests/ \
    -v \
    --cov=src/obskit \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=xml \
    --tb=short

echo ""
echo "📊 Coverage report generated!"
echo ""
echo "View HTML report:"
echo "  open htmlcov/index.html"
echo ""
echo "Coverage summary:"
python3 -m coverage report

