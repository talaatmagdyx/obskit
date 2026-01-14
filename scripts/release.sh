#!/bin/bash
# =============================================================================
# Release Build Script
# Builds and validates the package for release
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=============================================="
echo "Building Release Package"
echo "=============================================="
echo ""

# Check for required tools
for cmd in python pip; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd is not installed"
        exit 1
    fi
done

# Install build tools if needed
echo "1. Installing build tools..."
echo "----------------------------------------------"
pip install --quiet build twine
echo "   Done!"
echo ""

# Clean previous builds
echo "2. Cleaning previous builds..."
echo "----------------------------------------------"
rm -rf dist/ build/ *.egg-info src/*.egg-info
echo "   Done!"
echo ""

# Build package
echo "3. Building package..."
echo "----------------------------------------------"
python -m build
echo "   Done!"
echo ""

# Validate package
echo "4. Validating package..."
echo "----------------------------------------------"
twine check dist/*
echo "   Done!"
echo ""

# Show built files
echo "=============================================="
echo "Release package built successfully!"
echo "=============================================="
echo ""
echo "Built files:"
ls -la dist/
echo ""
echo "To upload to TestPyPI:"
echo "  twine upload --repository testpypi dist/*"
echo ""
echo "To upload to PyPI:"
echo "  twine upload dist/*"

