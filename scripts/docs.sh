#!/bin/bash
# =============================================================================
# Documentation Build Script
# Builds Sphinx documentation
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=============================================="
echo "Building Documentation"
echo "=============================================="
echo ""

# Parse arguments
SERVE=""
CLEAN=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--serve)
            SERVE=true
            shift
            ;;
        -c|--clean)
            CLEAN=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -s, --serve   Start live-reload server after build"
            echo "  -c, --clean   Clean build directory first"
            echo "  -h, --help    Show this help"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

cd docs

# Clean if requested
if [ "$CLEAN" = true ]; then
    echo "Cleaning build directory..."
    make clean
    echo ""
fi

echo "Building HTML documentation..."
echo "----------------------------------------------"
make html

echo ""
echo "=============================================="
echo "Documentation built successfully!"
echo "=============================================="
echo ""
echo "View at: docs/_build/html/index.html"

# Serve if requested
if [ "$SERVE" = true ]; then
    echo ""
    echo "Starting live-reload server..."
    echo "Open http://localhost:8000 in your browser"
    echo "Press Ctrl+C to stop"
    echo ""
    sphinx-autobuild source _build/html --host 0.0.0.0 --port 8000
fi

