#!/bin/bash
# Complete Localhost Deployment Script
# =====================================
# This script deploys the service to local Kubernetes and sets up port-forwarding

set -e

NAMESPACE="local"
SERVICE="order-service"
IMAGE_TAG="${1:-v1.0.0}"
IMAGE_NAME="${2:-localhost/order-service}"

echo "🚀 Deploying $SERVICE to localhost Kubernetes"
echo "📦 Image: ${IMAGE_NAME}:${IMAGE_TAG}"

# Step 1: Check Kubernetes is running
echo ""
echo "📦 Step 1: Checking Kubernetes cluster..."

# Try to set kind context if kind is being used
if command -v kind &> /dev/null; then
  CLUSTER_NAME=$(kind get clusters 2>/dev/null | head -1)
  if [ -n "$CLUSTER_NAME" ]; then
    echo "   Detected kind cluster: $CLUSTER_NAME"
    kubectl config use-context kind-$CLUSTER_NAME 2>/dev/null || true
  fi
fi

# Check cluster access (with retry for kind)
if ! kubectl cluster-info > /dev/null 2>&1; then
  echo "⚠️  Initial cluster check failed, retrying..."
  sleep 2
  if ! kubectl cluster-info > /dev/null 2>&1; then
    echo "❌ Error: Kubernetes cluster not accessible"
    echo "   Current context: $(kubectl config current-context 2>/dev/null || echo 'none')"
    echo "   Available contexts:"
    kubectl config get-contexts 2>/dev/null || true
    echo ""
    echo "   Make sure:"
    echo "   - Docker Desktop Kubernetes is enabled, OR"
    echo "   - minikube is running (minikube start), OR"
    echo "   - kind cluster exists (kind get clusters)"
    exit 1
  fi
fi
echo "✅ Kubernetes cluster is running"

# Step 2: Build image
echo ""
echo "🔨 Step 2: Building Docker image..."
cd "$(dirname "$0")"
USE_SIMPLE=true ./build.sh "$IMAGE_TAG" "$IMAGE_NAME"

# Detect and handle different local Kubernetes setups
if command -v kind &> /dev/null; then
  CLUSTER_NAME=$(kind get clusters 2>/dev/null | head -1)
  if [ -n "$CLUSTER_NAME" ]; then
    echo "📥 Loading image into kind cluster: $CLUSTER_NAME"
    kind load docker-image "${IMAGE_NAME}:${IMAGE_TAG}" --name "$CLUSTER_NAME" || true
  fi
elif command -v minikube &> /dev/null && minikube status &> /dev/null; then
  echo "📥 Loading image into minikube..."
  minikube image load "${IMAGE_NAME}:${IMAGE_TAG}" || true
fi

# Step 3: Create namespace
echo ""
echo "📁 Step 3: Creating namespace..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
echo "✅ Namespace created"

# Step 4: Create secrets
echo ""
echo "🔐 Step 4: Creating secrets..."
kubectl create secret generic ${SERVICE}-secrets \
  --from-literal=metricsAuthToken='local-dev-token-123' \
  -n $NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -
echo "✅ Secrets created"

# Step 5: Deploy with Helm
echo ""
echo "📊 Step 5: Deploying with Helm..."
IMAGE_REPO=$(echo $IMAGE_NAME | cut -d'/' -f1)
helm upgrade --install $SERVICE ../obskit \
  --namespace $NAMESPACE \
  --create-namespace \
  --values values-localhost.yaml \
  --set image.repository=$IMAGE_REPO \
  --set image.tag=$IMAGE_TAG \
  --set image.pullPolicy=IfNotPresent \
  --set obskit.serviceName=$SERVICE \
  --wait \
  --timeout 5m

echo "✅ Helm deployment complete"

# Step 6: Wait for pods
echo ""
echo "⏳ Step 6: Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=obskit-service \
  -n $NAMESPACE \
  --timeout=120s || {
  echo "⚠️  Pods not ready, checking status..."
  kubectl get pods -n $NAMESPACE
  kubectl describe pod -n $NAMESPACE -l app.kubernetes.io/name=obskit-service | tail -20
  exit 1
}

echo "✅ Pods are ready"

# Step 7: Show status
echo ""
echo "📊 Step 7: Deployment status..."
kubectl get pods -n $NAMESPACE
kubectl get svc -n $NAMESPACE

# Step 8: Port forward instructions
echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔌 Next steps:"
echo ""
echo "1. Port forward the service (run in another terminal):"
echo "   kubectl port-forward -n $NAMESPACE svc/$SERVICE 8080:80 9090:9090"
echo ""
echo "2. Test the service:"
echo "   curl http://localhost:8080/health"
echo "   curl http://localhost:8080/ready"
echo "   curl http://localhost:8080/live"
echo "   curl http://localhost:9090/metrics"
echo ""
echo "3. Create an order:"
echo "   curl -X POST http://localhost:8080/orders \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"id\": \"123\", \"amount\": 100.0}'"
echo ""
echo "4. View logs:"
echo "   kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=obskit-service -f"
echo ""
echo "5. Cleanup (when done):"
echo "   helm uninstall $SERVICE -n $NAMESPACE"
echo "   kubectl delete namespace $NAMESPACE"

