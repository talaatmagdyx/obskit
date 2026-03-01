#!/bin/bash
# =============================================================================
# Release Build Script
# Builds and validates all packages in the monorepo for release
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=============================================="
echo "Building Release Packages"
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

# All packages in dependency order
PACKAGES=(
    "obskit-core"
    "obskit-logging"
    "obskit-metrics"
    "obskit-tracing"
    "obskit-health"
    "obskit-resilience"
    "obskit-slo"
    "obskit-middleware-fastapi"
    "obskit-middleware-flask"
    "obskit-middleware-django"
    "obskit-middleware-grpc"
    "obskit-dashboards"
    "obskit-db"
    "obskit-queue"
    "obskit-decorators"
    "obskit"
)

# Clean previous builds
echo "2. Cleaning previous builds..."
echo "----------------------------------------------"
for pkg in "${PACKAGES[@]}"; do
    rm -rf "packages/$pkg/dist/" "packages/$pkg/build/"
done
echo "   Done!"
echo ""

# Build each package
echo "3. Building packages..."
echo "----------------------------------------------"
for pkg in "${PACKAGES[@]}"; do
    echo "   Building $pkg..."
    python -m build "packages/$pkg/" --outdir "packages/$pkg/dist/"
done
echo "   Done!"
echo ""

# Validate all packages
echo "4. Validating packages..."
echo "----------------------------------------------"
for pkg in "${PACKAGES[@]}"; do
    if [[ -d "packages/$pkg/dist/" ]]; then
        twine check "packages/$pkg/dist/"*
    fi
done
echo "   Done!"
echo ""

# Show built files
echo "=============================================="
echo "All release packages built successfully!"
echo "=============================================="
echo ""
echo "Built packages:"
for pkg in "${PACKAGES[@]}"; do
    if [[ -d "packages/$pkg/dist/" ]]; then
        echo "  packages/$pkg/dist/"
        ls "packages/$pkg/dist/" | sed 's/^/    /'
    fi
done
echo ""
echo "To upload to TestPyPI:"
echo "  for pkg in packages/*/dist/; do twine upload --repository testpypi \"\$pkg\"*; done"
echo ""
echo "To upload to PyPI:"
echo "  for pkg in packages/*/dist/; do twine upload \"\$pkg\"*; done"
