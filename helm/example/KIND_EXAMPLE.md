# Complete Kind (Kubernetes in Docker) Example

This guide shows you how to deploy and test the Helm chart using **kind** (Kubernetes in Docker) on your local machine.

## 🎯 Prerequisites

- **Docker** installed and running
- **kind** installed: `brew install kind` (macOS) or see [kind installation](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- **kubectl** installed and configured
- **helm** 3.0+ installed
- **curl** for testing

## 🚀 Quick Start (3 commands)

### One-Command Deployment (Easiest)

**⚠️ If `kind load docker-image` hangs, use the registry method instead!**

```bash
cd helm/example

# Fast method using local registry (RECOMMENDED)
./deploy-kind-registry.sh obskit-test v1.0.0

# OR traditional method (may hang with large images)
./deploy-kind.sh obskit-test v1.0.0
```

**Why use registry method?**
- ✅ Much faster (seconds vs minutes)
- ✅ More reliable (no hanging)
- ✅ Standard Docker workflow

### Access the Service

**Terminal 1: Port-forward**
```bash
./port-forward.sh
```

**Terminal 2: Test**
```bash
./test-localhost.sh
```

## 📋 Manual Step-by-Step (Alternative)

### Step 1: Create Kind Cluster

```bash
# Create a new kind cluster
kind create cluster --name obskit-test

# Verify cluster is running
kubectl cluster-info
kubectl get nodes
```

### Step 2: Build and Load Image

```bash
cd helm/example

# Build the image
USE_SIMPLE=true ./build.sh v1.0.0 localhost/order-service

# Load image into kind cluster
kind load docker-image localhost/order-service:v1.0.0 --name obskit-test
```

### Step 3: Deploy with Helm

```bash
# Deploy to kind cluster
./deploy-localhost.sh v1.0.0 localhost/order-service
```

### Step 4: Port Forward

```bash
# In another terminal, port-forward to localhost
./port-forward.sh

# OR manually:
kubectl port-forward -n local svc/order-service 8080:80 9090:9090
```

### Step 5: Test

```bash
# In another terminal, test the service
./test-localhost.sh

# OR manually:
curl http://localhost:8080/health
curl http://localhost:9090/metrics
```

## 📋 Complete Step-by-Step Guide

### 1. Setup Kind Cluster

```bash
# Create cluster
kind create cluster --name obskit-test

# Verify
kubectl get nodes
kubectl cluster-info --context kind-obskit-test
```

### 2. Build Docker Image

```bash
cd helm/example

# Build using simplified Dockerfile (more reliable)
USE_SIMPLE=true ./build.sh v1.0.0 localhost/order-service

# Verify image exists
docker images | grep order-service
```

### 3. Load Image into Kind

```bash
# Load image into kind cluster
kind load docker-image localhost/order-service:v1.0.0 --name obskit-test

# Verify image is loaded
docker exec obskit-test-control-plane crictl images | grep order-service
```

### 4. Create Namespace and Secrets

```bash
# Create namespace
kubectl create namespace local

# Create secrets
kubectl create secret generic order-service-secrets \
  --from-literal=metricsAuthToken='local-dev-token-123' \
  -n local
```

### 5. Deploy with Helm

```bash
# Deploy using localhost values
helm install order-service ../obskit \
  --namespace local \
  --values values-localhost.yaml \
  --set image.repository=localhost/order-service \
  --set image.tag=v1.0.0 \
  --set image.pullPolicy=IfNotPresent \
  --set obskit.serviceName=order-service \
  --set obskit.environment=local \
  --set obskit.metricsAuthEnabled=false \
  --wait \
  --timeout 5m
```

### 6. Verify Deployment

```bash
# Check pods
kubectl get pods -n local

# Check service
kubectl get svc -n local

# View logs
kubectl logs -n local -l app.kubernetes.io/name=obskit-service --tail=100
```

### 7. Port Forward to Localhost

```bash
# Port forward both HTTP and metrics
kubectl port-forward -n local svc/order-service 8080:80 9090:9090
```

### 8. Test Endpoints

**In a new terminal:**

```bash
# Health endpoints
curl http://localhost:8080/health
curl http://localhost:8080/ready
curl http://localhost:8080/live

# Metrics
curl http://localhost:9090/metrics

# Create an order
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"id": "123", "amount": 100.0}'

# Get order
curl http://localhost:8080/orders/123
```

## 🔧 Automated Script for Kind

Create `deploy-kind.sh`:

```bash
#!/bin/bash
# Complete Kind Deployment Script
# ================================

set -e

CLUSTER_NAME="${1:-obskit-test}"
NAMESPACE="local"
SERVICE="order-service"
IMAGE_TAG="${2:-v1.0.0}"
IMAGE_NAME="localhost/order-service"

echo "🚀 Deploying to Kind cluster: $CLUSTER_NAME"

# Step 1: Check/create kind cluster
echo ""
echo "📦 Step 1: Setting up Kind cluster..."
if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
  echo "Creating kind cluster..."
  kind create cluster --name $CLUSTER_NAME
else
  echo "Kind cluster already exists"
fi

# Set kubectl context
kubectl config use-context kind-$CLUSTER_NAME

# Step 2: Build image
echo ""
echo "🔨 Step 2: Building Docker image..."
cd "$(dirname "$0")"
USE_SIMPLE=true ./build.sh $IMAGE_TAG $IMAGE_NAME

# Step 3: Load image into kind
echo ""
echo "📥 Step 3: Loading image into kind..."
kind load docker-image ${IMAGE_NAME}:${IMAGE_TAG} --name $CLUSTER_NAME

# Step 4: Deploy
echo ""
echo "📊 Step 4: Deploying with Helm..."
./deploy-localhost.sh $IMAGE_TAG $IMAGE_NAME

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔌 Next steps:"
echo "  1. Port forward: ./port-forward.sh"
echo "  2. Test: ./test-localhost.sh"
echo ""
echo "🧹 Cleanup:"
echo "  kind delete cluster --name $CLUSTER_NAME"
```

## 🧪 Testing

### Using Test Script

```bash
# Make sure port-forward is running in another terminal
./port-forward.sh

# Then test
./test-localhost.sh
```

### Manual Testing

```bash
# Health check
curl http://localhost:8080/health | jq .

# Metrics
curl http://localhost:9090/metrics | grep order_service

# Create order
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"id": "test-123", "amount": 99.99}' | jq .
```

## 📊 View Logs

```bash
# Follow logs
kubectl logs -n local -l app.kubernetes.io/name=obskit-service -f

# View specific pod logs
POD_NAME=$(kubectl get pods -n local -l app.kubernetes.io/name=obskit-service -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n local $POD_NAME -f
```

## 🔍 Inspect Resources

```bash
# View all resources
kubectl get all -n local

# Describe deployment
kubectl describe deployment -n local order-service

# Describe pod
kubectl describe pod -n local -l app.kubernetes.io/name=obskit-service

# View events
kubectl get events -n local --sort-by='.lastTimestamp'
```

## 🔄 Update Deployment

```bash
# Rebuild image
USE_SIMPLE=true ./build.sh v1.0.1 localhost/order-service

# Load new image
kind load docker-image localhost/order-service:v1.0.1 --name obskit-test

# Upgrade deployment
helm upgrade order-service ../obskit \
  --namespace local \
  --values values-localhost.yaml \
  --set image.tag=v1.0.1 \
  --reuse-values

# Restart to pick up new image
kubectl rollout restart deployment/order-service -n local
```

## 🧹 Cleanup

```bash
# Uninstall Helm release
helm uninstall order-service -n local

# Delete namespace
kubectl delete namespace local

# Delete kind cluster
kind delete cluster --name obskit-test
```

## 🎯 Complete One-Command Setup

Save this as `setup-kind.sh`:

```bash
#!/bin/bash
# One-command Kind setup
# ======================

set -e

CLUSTER_NAME="obskit-test"
IMAGE_TAG="v1.0.0"

echo "🚀 Setting up Kind cluster and deploying service..."

# Create cluster if it doesn't exist
if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
  echo "📦 Creating Kind cluster..."
  kind create cluster --name $CLUSTER_NAME
fi

# Set context
kubectl config use-context kind-$CLUSTER_NAME

# Build and load image
cd helm/example
echo "🔨 Building image..."
USE_SIMPLE=true ./build.sh $IMAGE_TAG localhost/order-service

echo "📥 Loading image into Kind..."
kind load docker-image localhost/order-service:$IMAGE_TAG --name $CLUSTER_NAME

# Deploy
echo "📊 Deploying with Helm..."
./deploy-localhost.sh $IMAGE_TAG localhost/order-service

echo ""
echo "✅ Setup complete!"
echo ""
echo "🔌 Next steps:"
echo "  1. Port forward: ./port-forward.sh"
echo "  2. Test: ./test-localhost.sh"
echo ""
echo "📋 Access:"
echo "  - Service: http://localhost:8080"
echo "  - Metrics: http://localhost:9090/metrics"
```

Make executable and run:

```bash
chmod +x setup-kind.sh
./setup-kind.sh
```

## 🐛 Troubleshooting

### Image Not Found

```bash
# Verify image is loaded
docker exec ${CLUSTER_NAME}-control-plane crictl images | grep order-service

# Reload if needed
kind load docker-image localhost/order-service:v1.0.0 --name $CLUSTER_NAME
```

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod -n local -l app.kubernetes.io/name=obskit-service

# Check events
kubectl get events -n local --sort-by='.lastTimestamp'
```

### Port Forward Issues

```bash
# Check if service exists
kubectl get svc -n local

# Check if pods are running
kubectl get pods -n local

# Try different ports
kubectl port-forward -n local svc/order-service 8081:80 9091:9090
```

## 📚 Additional Resources

- [Kind Documentation](https://kind.sigs.k8s.io/)
- [Localhost Example](./LOCALHOST_EXAMPLE.md) - General localhost guide
- [Complete Example](./COMPLETE_EXAMPLE.md) - Production deployment

