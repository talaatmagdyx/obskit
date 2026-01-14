#!/bin/bash
# Build script for the example service
# ====================================
# This script builds the Docker image with obskit from local source

set -e

IMAGE_TAG="${1:-v1.0.0}"
IMAGE_NAME="${2:-my-registry.example.com/order-service}"

echo "🔨 Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"

# Get the repository root (assuming we're in helm/example)
# Go up: helm/example -> helm -> obskit -> monitoring (repo root)
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

echo "📦 Repository root: $REPO_ROOT"
echo "📁 Current directory: $(pwd)"

# Verify obskit source exists
if [ ! -d "$REPO_ROOT/obskit/src/obskit" ]; then
  echo "❌ Error: obskit source not found at $REPO_ROOT/obskit/src/obskit"
  echo "   Make sure you're running this from the correct location"
  exit 1
fi

# Verify required files exist
if [ ! -f "$REPO_ROOT/obskit/pyproject.toml" ]; then
  echo "❌ Error: pyproject.toml not found at $REPO_ROOT/obskit/pyproject.toml"
  exit 1
fi

if [ ! -f "$REPO_ROOT/obskit/README.md" ]; then
  echo "❌ Error: README.md not found at $REPO_ROOT/obskit/README.md"
  exit 1
fi

# Try Dockerfile.local first, fallback to simple version if it fails
DOCKERFILE="$(dirname "$0")/Dockerfile.local"

# Check if simple version should be used
if [ "${USE_SIMPLE:-}" == "true" ]; then
  DOCKERFILE="$(dirname "$0")/Dockerfile.local-simple"
  echo "📝 Using simplified Dockerfile (no editable install)"
fi

# Build using Dockerfile.local with build context at repo root
echo "🔨 Building image with $DOCKERFILE..."
docker build \
  -f "$DOCKERFILE" \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  "$REPO_ROOT"

echo "✅ Image built successfully: ${IMAGE_NAME}:${IMAGE_TAG}"

# Optionally push
if [ "${3}" == "push" ]; then
  echo "📤 Pushing image..."
  docker push "${IMAGE_NAME}:${IMAGE_TAG}"
  echo "✅ Image pushed successfully"
fi

echo ""
echo "🚀 To deploy:"
echo "  ./deploy.sh ${IMAGE_TAG}"

