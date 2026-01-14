#!/bin/bash
# Run Service Locally (No Docker, No Kubernetes)
# =============================================
# This script runs the example service directly with Python

set -e

echo "🚀 Starting service locally (no Docker, no Kubernetes)"
echo ""

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Calculate repo root: helm/example -> helm -> obskit -> monitoring (repo root)
# We're in: monitoring/obskit/helm/example
# Go up 3 levels to get to monitoring/
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
  echo "❌ Error: python3 not found"
  echo "   Please install Python 3.11+"
  exit 1
fi

# Check if obskit source exists
OBSKIT_SRC="$REPO_ROOT/obskit/src/obskit"
if [ ! -d "$OBSKIT_SRC" ]; then
  echo "❌ Error: obskit source not found at $OBSKIT_SRC"
  echo "   Expected path: $OBSKIT_SRC"
  echo "   Current directory: $(pwd)"
  echo "   Script directory: $SCRIPT_DIR"
  echo "   Repo root: $REPO_ROOT"
  echo ""
  echo "   Please make sure you're running from the correct location"
  exit 1
fi

echo "📦 Setting up Python environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "$SCRIPT_DIR/venv" ]; then
  echo "   Creating virtual environment..."
  python3 -m venv "$SCRIPT_DIR/venv"
fi

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Install dependencies
echo "   Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet \
  fastapi==0.104.1 \
  uvicorn[standard]==0.24.0 \
  pydantic>=2.0.0 \
  structlog>=24.1.0 \
  pydantic-settings>=2.0.0 \
  prometheus-client>=0.19.0 \
  opentelemetry-api>=1.20.0 \
  opentelemetry-sdk>=1.20.0 \
  opentelemetry-exporter-otlp>=1.20.0

# Add obskit to Python path
export PYTHONPATH="$REPO_ROOT/obskit/src:$PYTHONPATH"
echo "   PYTHONPATH: $PYTHONPATH"

# Set environment variables for local development
export OBSKIT_SERVICE_NAME="order-service"
export OBSKIT_ENVIRONMENT="local"
export OBSKIT_METRICS_ENABLED="true"
export OBSKIT_TRACING_ENABLED="false"  # Disable tracing for local dev (no collector)
export OBSKIT_METRICS_AUTH_ENABLED="false"
export OBSKIT_METRICS_PORT="9090"
export OBSKIT_HTTP_PORT="8080"

echo "✅ Environment ready"
echo ""
echo "🌐 Starting service..."
echo "   Service: http://localhost:8080"
echo "   Metrics: http://localhost:9090/metrics"
echo "   Health: http://localhost:8080/health"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run the service
cd "$SCRIPT_DIR"
python3 test-service.py

