# Complete Localhost Example: Run Helm Chart Locally

This guide shows you how to deploy and test the Helm chart on your local machine using localhost.

## 🎯 Prerequisites

- **Docker Desktop** (with Kubernetes enabled) OR **minikube** OR **kind**
- **kubectl** configured
- **helm** 3.0+ installed
- **curl** for testing

## 🚀 Quick Start (5 minutes)

### Automated Deployment (Easiest)

```bash
cd helm/example

# 1. Deploy everything (builds image, creates namespace, deploys)
./deploy-localhost.sh v1.0.0

# 2. In another terminal, port-forward:
./port-forward.sh

# 3. Test:
./test-localhost.sh
```

### Manual Deployment

### Step 1: Start Local Kubernetes

**Option A: Docker Desktop**
1. Open Docker Desktop
2. Go to Settings → Kubernetes
3. Enable Kubernetes
4. Wait for it to start (green indicator)

**Option B: minikube**
```bash
minikube start
```

**Option C: kind**
```bash
kind create cluster --name obskit-test
```

### Step 2: Verify Kubernetes is Running

```bash
kubectl cluster-info
kubectl get nodes
```

### Step 3: Build the Service Image

```bash
cd helm/example

# Build image (use simplified version for reliability)
USE_SIMPLE=true ./build.sh v1.0.0 localhost/order-service

# OR if using minikube, load image into minikube
# minikube image load localhost/order-service:v1.0.0

# OR if using kind, load image into kind
# kind load docker-image localhost/order-service:v1.0.0 --name obskit-test
```

**Note:** For Docker Desktop, you can use `localhost/` as registry. For minikube/kind, you may need to use the cluster's registry or load images directly.

### Step 4: Create Namespace and Secrets

```bash
# Create namespace
kubectl create namespace local

# Create secrets
kubectl create secret generic order-service-secrets \
  --from-literal=metricsAuthToken='local-dev-token-123' \
  -n local
```

### Step 5: Deploy with Helm

```bash
# Deploy to local cluster
helm install order-service ../obskit \
  --namespace local \
  --values values.yaml \
  --set image.repository=localhost/order-service \
  --set image.tag=v1.0.0 \
  --set image.pullPolicy=IfNotPresent \
  --set obskit.serviceName=order-service \
  --set obskit.environment=local \
  --set replicaCount=1 \
  --set obskit.metricsAuthEnabled=false \
  --set obskit.tracingEnabled=false \
  --set obskit.otlpInsecure=true
```

### Step 6: Wait for Deployment

```bash
# Wait for pods to be ready
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=obskit-service \
  -n local \
  --timeout=120s

# Check status
kubectl get pods -n local
kubectl get svc -n local
```

### Step 7: Port Forward to Localhost

**Option A: Using the convenience script**
```bash
# Port forward both HTTP and metrics
./port-forward.sh local order-service
```

**Option B: Manual port-forward**
```bash
# Port forward service to localhost (both ports in one command)
kubectl port-forward -n local svc/order-service 8080:80 9090:9090
```

**Option C: Separate terminals**
```bash
# Terminal 1: HTTP service (port 8080)
kubectl port-forward -n local svc/order-service 8080:80

# Terminal 2: Metrics (port 9090)
kubectl port-forward -n local svc/order-service 9090:9090
```

### Step 8: Test the Service

**Option A: Using the test script (recommended)**
```bash
# In a new terminal (while port-forward is running)
./test-localhost.sh
```

**Option B: Manual testing**
```bash
# Health check
curl http://localhost:8080/health

# Readiness check
curl http://localhost:8080/ready

# Liveness check
curl http://localhost:8080/live

# Create an order
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"id": "123", "amount": 100.0}'

# Get order
curl http://localhost:8080/orders/123

# Metrics (no auth needed since we disabled it)
curl http://localhost:9090/metrics
```

## 📊 View Logs

```bash
# View pod logs
kubectl logs -n local -l app.kubernetes.io/name=obskit-service --tail=100 -f

# View specific pod logs
POD_NAME=$(kubectl get pods -n local -l app.kubernetes.io/name=obskit-service -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n local $POD_NAME -f
```

## 🔍 Inspect Resources

```bash
# View deployment
kubectl get deployment -n local order-service -o yaml

# View service
kubectl get svc -n local order-service -o yaml

# View pods
kubectl describe pod -n local -l app.kubernetes.io/name=obskit-service

# View events
kubectl get events -n local --sort-by='.lastTimestamp'
```

## 🧪 Complete Test Script

Create `test-localhost.sh`:

```bash
#!/bin/bash
# Complete localhost testing script

set -e

NAMESPACE="local"
SERVICE="order-service"

echo "🧪 Testing $SERVICE on localhost"

# Wait for service to be ready
echo "⏳ Waiting for service to be ready..."
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=obskit-service \
  -n $NAMESPACE \
  --timeout=120s

# Test health endpoints
echo ""
echo "🏥 Testing health endpoints..."

echo "  Health:"
curl -s http://localhost:8080/health | jq . || echo "  ❌ Failed"

echo "  Readiness:"
curl -s http://localhost:8080/ready | jq . || echo "  ❌ Failed"

echo "  Liveness:"
curl -s http://localhost:8080/live | jq . || echo "  ❌ Failed"

# Test business endpoints
echo ""
echo "📦 Testing business endpoints..."

echo "  Creating order..."
ORDER_RESPONSE=$(curl -s -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"id": "test-123", "amount": 99.99}')

echo "$ORDER_RESPONSE" | jq . || echo "$ORDER_RESPONSE"

ORDER_ID=$(echo "$ORDER_RESPONSE" | jq -r '.order_id // "test-123"')

echo "  Getting order $ORDER_ID..."
curl -s http://localhost:8080/orders/$ORDER_ID | jq . || echo "  ❌ Failed"

# Test metrics
echo ""
echo "📊 Testing metrics endpoint..."
METRICS=$(curl -s http://localhost:9090/metrics)
echo "$METRICS" | grep -E "^order_service" | head -10 || echo "  No metrics found"

echo ""
echo "✅ Testing complete!"
```

Make it executable and run:

```bash
chmod +x test-localhost.sh

# Make sure port-forward is running in another terminal, then:
./test-localhost.sh
```

## 🔧 Configuration for Local Development

Create `values-localhost.yaml`:

```yaml
# Localhost-specific values
replicaCount: 1

image:
  repository: localhost/order-service
  pullPolicy: IfNotPresent
  tag: "v1.0.0"

obskit:
  serviceName: "order-service"
  environment: "local"
  version: "v1.0.0"
  
  # Logging - use console for local development
  logLevel: "DEBUG"
  logFormat: "console"
  logSampleRate: 1.0  # No sampling in local dev
  
  # Metrics - disable auth for local
  metricsEnabled: true
  metricsPort: 9090
  metricsSampleRate: 1.0  # No sampling
  metricsAuthEnabled: false  # No auth needed locally
  
  # Tracing - disable for local (optional)
  tracingEnabled: false
  # Or enable with local collector:
  # tracingEnabled: true
  # otlpEndpoint: "http://localhost:4317"
  # otlpInsecure: true
  # traceSampleRate: 1.0

# Resources - minimal for local
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 256Mi

# Disable autoscaling for local
autoscaling:
  enabled: false

# ServiceMonitor - disable if Prometheus Operator not installed
serviceMonitor:
  enabled: false

# Health checks - shorter timeouts for local
livenessProbe:
  httpGet:
    path: /live
    port: http
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: http
  initialDelaySeconds: 3
  periodSeconds: 3
  timeoutSeconds: 2
  failureThreshold: 3
```

Deploy with localhost values:

```bash
helm install order-service ../obskit \
  --namespace local \
  --values values-localhost.yaml \
  --set image.repository=localhost/order-service \
  --set image.tag=v1.0.0
```

## 🌐 Access via Ingress (Optional)

If you have an ingress controller installed:

```bash
# Install ingress (nginx example)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml

# Create ingress
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: order-service-ingress
  namespace: local
spec:
  rules:
  - host: order-service.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: order-service
            port:
              number: 80
EOF

# Add to /etc/hosts (or use hosts file)
echo "127.0.0.1 order-service.local" | sudo tee -a /etc/hosts

# Access via browser
curl http://order-service.local/health
```

## 📊 View Metrics in Browser

```bash
# Port forward metrics
kubectl port-forward -n local svc/order-service 9090:9090

# Open in browser
open http://localhost:9090/metrics
```

## 🔄 Update and Redeploy

```bash
# Rebuild image
USE_SIMPLE=true ./build.sh v1.0.1 localhost/order-service

# Upgrade deployment
helm upgrade order-service ../obskit \
  --namespace local \
  --values values-localhost.yaml \
  --set image.tag=v1.0.1 \
  --reuse-values

# Restart pods to pick up new image
kubectl rollout restart deployment/order-service -n local
```

## 🧹 Cleanup

```bash
# Uninstall Helm release
helm uninstall order-service -n local

# Delete secrets
kubectl delete secret order-service-secrets -n local

# Delete namespace
kubectl delete namespace local

# Stop port-forward (Ctrl+C in terminal)
```

## 🎯 Complete Example: End-to-End

Here's a complete script that does everything:

```bash
#!/bin/bash
# Complete localhost deployment script

set -e

NAMESPACE="local"
SERVICE="order-service"
IMAGE_TAG="v1.0.0"

echo "🚀 Deploying $SERVICE to localhost Kubernetes"

# Step 1: Check Kubernetes
echo "📦 Checking Kubernetes cluster..."
kubectl cluster-info > /dev/null || { echo "❌ Kubernetes not running"; exit 1; }

# Step 2: Build image
echo "🔨 Building Docker image..."
cd helm/example
USE_SIMPLE=true ./build.sh $IMAGE_TAG localhost/$SERVICE

# Step 3: Create namespace
echo "📁 Creating namespace..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Step 4: Create secrets
echo "🔐 Creating secrets..."
kubectl create secret generic ${SERVICE}-secrets \
  --from-literal=metricsAuthToken='local-dev-token' \
  -n $NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -

# Step 5: Deploy with Helm
echo "📊 Deploying with Helm..."
helm upgrade --install $SERVICE ../obskit \
  --namespace $NAMESPACE \
  --create-namespace \
  --values values-localhost.yaml \
  --set image.repository=localhost/$SERVICE \
  --set image.tag=$IMAGE_TAG \
  --set image.pullPolicy=IfNotPresent \
  --wait \
  --timeout 5m

# Step 6: Wait for ready
echo "⏳ Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=obskit-service \
  -n $NAMESPACE \
  --timeout=120s

# Step 7: Port forward
echo "🔌 Setting up port forwarding..."
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "  1. In another terminal, run:"
echo "     kubectl port-forward -n $NAMESPACE svc/$SERVICE 8080:80 9090:9090"
echo ""
echo "  2. Then test:"
echo "     curl http://localhost:8080/health"
echo "     curl http://localhost:9090/metrics"
echo ""
echo "  3. View logs:"
echo "     kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=obskit-service -f"
```

Save as `deploy-localhost.sh`, make executable, and run:

```bash
chmod +x deploy-localhost.sh
./deploy-localhost.sh
```

## 🎉 Success!

Once deployed, you can:

- ✅ Access service at `http://localhost:8080`
- ✅ View metrics at `http://localhost:9090/metrics`
- ✅ Test health endpoints
- ✅ View logs with `kubectl logs`
- ✅ Scale: `kubectl scale deployment order-service -n local --replicas=3`

## 📚 Additional Resources

- [Complete Example Guide](./COMPLETE_EXAMPLE.md) - Full production deployment
- [Quick Start](./QUICK_START.md) - 5-minute guide
- [Troubleshooting](./TROUBLESHOOTING.md) - Common issues and solutions

