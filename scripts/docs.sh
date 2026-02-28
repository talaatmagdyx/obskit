#!/bin/bash
# =============================================================================
# Documentation Build Script
# Builds MkDocs documentation
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

# Check if mkdocs is installed
if ! command -v mkdocs &> /dev/null; then
    echo "Error: mkdocs is not installed. Install with: pip install mkdocs-material"
    exit 1
fi

# Clean if requested
if [ "$CLEAN" = true ]; then
    echo "Cleaning site directory..."
    rm -rf site/
    echo ""
fi

if [ "$SERVE" = true ]; then
    echo "Starting live-reload server..."
    echo "Open http://localhost:8000 in your browser"
    echo "Press Ctrl+C to stop"
    echo ""
    mkdocs serve
else
    echo "Building HTML documentation..."
    echo "----------------------------------------------"
    mkdocs build --strict

    echo ""
    echo "=============================================="
    echo "Documentation built successfully!"
    echo "=============================================="
    echo ""
    echo "View at: site/index.html"
fi
