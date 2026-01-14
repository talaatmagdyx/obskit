#!/bin/bash
# Complete Deployment Script for Order Service
# ============================================
# This script demonstrates a complete deployment workflow

set -e

# Configuration
NAMESPACE="production"
SERVICE_NAME="order-service"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-my-registry.example.com}"
IMAGE_TAG="${1:-v1.2.3}"
CHART_PATH="../obskit"

echo "🚀 Deploying $SERVICE_NAME to $NAMESPACE"
echo "📦 Image: ${IMAGE_REGISTRY}/${SERVICE_NAME}:${IMAGE_TAG}"

# Step 1: Create namespace if it doesn't exist
echo "📦 Creating namespace..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Step 2: Create secrets
echo "🔐 Creating secrets..."
kubectl create secret generic ${SERVICE_NAME}-secrets \
  --from-literal=metricsAuthToken='prod-metrics-token-abc123xyz' \
  --from-literal=databaseUrl='postgresql://user:pass@db:5432/orders' \
  -n $NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -

# Step 3: Install/Upgrade Helm chart
echo "📊 Installing Helm chart..."
helm upgrade --install $SERVICE_NAME $CHART_PATH \
  --namespace $NAMESPACE \
  --values values.yaml \
  --set image.repository=${IMAGE_REGISTRY}/${SERVICE_NAME} \
  --set image.tag=${IMAGE_TAG} \
  --set obskit.serviceName=${SERVICE_NAME} \
  --wait \
  --timeout 5m \
  --create-namespace

# Step 4: Wait for deployment
echo "⏳ Waiting for deployment..."
kubectl wait --for=condition=available \
  --timeout=300s \
  deployment/${SERVICE_NAME} \
  -n $NAMESPACE

# Step 5: Verify deployment
echo "✅ Verifying deployment..."
kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=obskit-service

# Step 6: Check service
echo "🌐 Checking service..."
kubectl get svc -n $NAMESPACE ${SERVICE_NAME}

# Step 7: Test health endpoints
echo "🏥 Testing health endpoints..."
POD_NAME=$(kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=obskit-service -o jsonpath='{.items[0].metadata.name}')

kubectl exec -n $NAMESPACE $POD_NAME -- \
  curl -s http://localhost:8080/health | jq .

# Step 8: Port forward for testing
echo "🔌 Setting up port forward..."
echo "Metrics endpoint: http://localhost:9090/metrics"
echo "Health endpoint: http://localhost:8080/health"
echo ""
echo "Run in another terminal:"
echo "  kubectl port-forward -n $NAMESPACE svc/${SERVICE_NAME} 9090:9090 8080:80"
echo ""
echo "Then test:"
echo "  curl -H 'Authorization: Bearer prod-metrics-token-abc123xyz' http://localhost:9090/metrics"
echo "  curl http://localhost:8080/health"

echo ""
echo "✅ Deployment complete!"
echo "📊 View logs: kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=obskit-service --tail=100"

