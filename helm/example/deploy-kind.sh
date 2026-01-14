#!/bin/bash
# Complete Kind Deployment Script
# ================================
# This script sets up a Kind cluster and deploys the service

set -e

CLUSTER_NAME="${1:-obskit-test}"
NAMESPACE="local"
SERVICE="order-service"
IMAGE_TAG="${2:-v1.0.0}"
IMAGE_NAME="${3:-localhost/order-service}"

echo "🚀 Deploying to Kind cluster: $CLUSTER_NAME"
echo "📦 Image: ${IMAGE_NAME}:${IMAGE_TAG}"

# Step 1: Check/create kind cluster
echo ""
echo "📦 Step 1: Setting up Kind cluster..."
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  echo "Creating kind cluster: $CLUSTER_NAME"
  kind create cluster --name $CLUSTER_NAME
  echo "✅ Kind cluster created"
else
  echo "✅ Kind cluster already exists: $CLUSTER_NAME"
fi

# Set kubectl context and verify
kubectl config use-context kind-$CLUSTER_NAME
echo "✅ Using context: kind-$CLUSTER_NAME"

# Verify cluster is accessible
if ! kubectl cluster-info > /dev/null 2>&1; then
  echo "⚠️  Cluster not immediately accessible, waiting a moment..."
  sleep 3
  if ! kubectl cluster-info > /dev/null 2>&1; then
    echo "❌ Error: Cannot access kind cluster"
    echo "   Try: kind delete cluster --name $CLUSTER_NAME && kind create cluster --name $CLUSTER_NAME"
    exit 1
  fi
fi
echo "✅ Cluster is accessible"

# Step 2: Build image
echo ""
echo "🔨 Step 2: Building Docker image..."
cd "$(dirname "$0")"
USE_SIMPLE=true ./build.sh $IMAGE_TAG $IMAGE_NAME
echo "✅ Image built: ${IMAGE_NAME}:${IMAGE_TAG}"

# Step 3: Load image into kind (with timeout and alternative method)
echo ""
echo "📥 Step 3: Loading image into kind cluster..."

# Check if image is already loaded
if docker exec ${CLUSTER_NAME}-control-plane crictl images 2>/dev/null | grep -q "${IMAGE_NAME}"; then
  echo "✅ Image already loaded in kind cluster (skipping)"
else
  # Show image size before loading
  IMAGE_SIZE=$(docker images ${IMAGE_NAME}:${IMAGE_TAG} --format "{{.Size}}" 2>/dev/null || echo "unknown")
  echo "   Image: ${IMAGE_NAME}:${IMAGE_TAG}"
  echo "   Size: $IMAGE_SIZE"
  echo ""
  echo "   ⚠️  Using alternative method (docker save/load) - faster and more reliable"
  echo "   If this still hangs, use: ./deploy-kind-registry.sh (uses local registry)"
  echo ""
  
  # Alternative method: Use docker save/load directly (faster)
  echo "   Saving image to tar..."
  TEMP_TAR=$(mktemp /tmp/kind-image-XXXXXX.tar)
  docker save ${IMAGE_NAME}:${IMAGE_TAG} -o "$TEMP_TAR"
  
  echo "   Loading image into kind container..."
  docker exec -i ${CLUSTER_NAME}-control-plane ctr --namespace=k8s.io images import - < "$TEMP_TAR"
  
  # Cleanup
  rm -f "$TEMP_TAR"
  
  echo "✅ Image loaded into kind successfully"
fi

# Step 4: Deploy
echo ""
echo "📊 Step 4: Deploying with Helm..."
./deploy-localhost.sh $IMAGE_TAG $IMAGE_NAME

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔌 Next steps:"
echo ""
echo "1. Port forward (in another terminal):"
echo "   ./port-forward.sh"
echo "   # OR"
echo "   kubectl port-forward -n $NAMESPACE svc/$SERVICE 8080:80 9090:9090"
echo ""
echo "2. Test the service:"
echo "   ./test-localhost.sh"
echo "   # OR manually:"
echo "   curl http://localhost:8080/health"
echo "   curl http://localhost:9090/metrics"
echo ""
echo "3. View logs:"
echo "   kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=obskit-service -f"
echo ""
echo "🧹 Cleanup:"
echo "   kind delete cluster --name $CLUSTER_NAME"

