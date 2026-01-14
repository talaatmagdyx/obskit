#!/bin/bash
# Kind Deployment Script using Local Registry (FASTER)
# ====================================================
# This script uses a local Docker registry instead of kind load docker-image
# which is much faster and more reliable

set -e

CLUSTER_NAME="${1:-obskit-test}"
NAMESPACE="local"
SERVICE="order-service"
IMAGE_TAG="${2:-v1.0.0}"
IMAGE_NAME="${3:-localhost:5000/order-service}"
REGISTRY_PORT="${4:-5000}"

echo "🚀 Deploying to Kind cluster: $CLUSTER_NAME (using local registry)"
echo "📦 Image: ${IMAGE_NAME}:${IMAGE_TAG}"

# Step 1: Check/create kind cluster with registry
echo ""
echo "📦 Step 1: Setting up Kind cluster with local registry..."

CLUSTER_EXISTS=false
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  CLUSTER_EXISTS=true
  echo "✅ Kind cluster already exists: $CLUSTER_NAME"
  
  # Check if cluster is actually accessible
  kubectl config use-context kind-$CLUSTER_NAME > /dev/null 2>&1
  if ! kubectl cluster-info > /dev/null 2>&1; then
    echo "⚠️  Cluster exists but is not accessible - recreating..."
    echo "   Deleting broken cluster..."
    kind delete cluster --name $CLUSTER_NAME 2>/dev/null || true
    CLUSTER_EXISTS=false
  fi
fi

if [ "$CLUSTER_EXISTS" = false ]; then
  echo "Creating kind cluster with local registry: $CLUSTER_NAME"
  
  # Create kind config with registry
  cat <<EOF | kind create cluster --name $CLUSTER_NAME --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:${REGISTRY_PORT}"]
    endpoint = ["http://localhost:${REGISTRY_PORT}"]
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: ${REGISTRY_PORT}
    hostPort: ${REGISTRY_PORT}
    protocol: TCP
EOF
  echo "✅ Kind cluster created with registry support"
  
  # Wait for cluster to be ready
  echo "   Waiting for cluster to be ready..."
  sleep 5
fi

# Set kubectl context and verify
kubectl config use-context kind-$CLUSTER_NAME
echo "✅ Using context: kind-$CLUSTER_NAME"

# Verify cluster is accessible with retries
echo "   Verifying cluster access..."
for i in {1..5}; do
  if kubectl cluster-info > /dev/null 2>&1; then
    echo "✅ Cluster is accessible"
    break
  fi
  if [ $i -eq 5 ]; then
    echo "❌ Error: Cannot access kind cluster after multiple attempts"
    echo ""
    echo "   Troubleshooting steps:"
    echo "   1. Check if Docker is running: docker ps"
    echo "   2. Delete and recreate cluster:"
    echo "      kind delete cluster --name $CLUSTER_NAME"
    echo "      kind create cluster --name $CLUSTER_NAME"
    echo "   3. Check cluster status:"
    echo "      kind get clusters"
    echo "      docker ps | grep $CLUSTER_NAME"
    exit 1
  fi
  echo "   Attempt $i/5 failed, retrying in 2 seconds..."
  sleep 2
done

# Step 2: Start local registry if not running
echo ""
echo "🐳 Step 2: Starting local Docker registry..."
if ! docker ps | grep -q "registry:2"; then
  echo "Starting local registry on port $REGISTRY_PORT..."
  docker run -d --name kind-registry \
    --restart=unless-stopped \
    -p "${REGISTRY_PORT}:5000" \
    registry:2
  echo "✅ Local registry started"
else
  echo "✅ Local registry already running"
fi

# Connect kind network to registry
if ! docker network inspect kind | grep -q "kind-registry"; then
  echo "Connecting registry to kind network..."
  docker network connect kind kind-registry 2>/dev/null || true
fi

# Step 3: Build image
echo ""
echo "🔨 Step 3: Building Docker image..."
cd "$(dirname "$0")"
USE_SIMPLE=true ./build.sh $IMAGE_TAG $IMAGE_NAME
echo "✅ Image built: ${IMAGE_NAME}:${IMAGE_TAG}"

# Step 4: Push to local registry
echo ""
echo "📤 Step 4: Pushing image to local registry..."
docker push ${IMAGE_NAME}:${IMAGE_TAG}
echo "✅ Image pushed to local registry"

# Step 5: Deploy
echo ""
echo "📊 Step 5: Deploying with Helm..."
./deploy-localhost.sh $IMAGE_TAG $IMAGE_NAME

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔌 Next steps:"
echo ""
echo "1. Port forward (in another terminal):"
echo "   ./port-forward.sh"
echo ""
echo "2. Test the service:"
echo "   ./test-localhost.sh"
echo ""
echo "🧹 Cleanup:"
echo "   docker stop kind-registry && docker rm kind-registry"
echo "   kind delete cluster --name $CLUSTER_NAME"

