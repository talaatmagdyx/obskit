# Quick Start: Deploy Order Service with Helm

This is a **5-minute quick start** guide to deploy a service with obskit using Helm.

## Prerequisites

- Kubernetes cluster running
- `kubectl` configured
- `helm` 3.0+ installed
- Docker (for building image)

## 🚀 Deploy in 5 Steps

### Step 1: Build and Push Image

```bash
cd helm/example

# Build using the build script (installs obskit from local source)
./build.sh v1.0.0 my-registry.example.com/order-service

# Push (adjust registry as needed)
docker push my-registry.example.com/order-service:v1.0.0

# OR build and push in one command
./build.sh v1.0.0 my-registry.example.com/order-service push
```

**Note:** Since obskit is not published to PyPI yet, the build script installs it from the local source. See [BUILD_INSTRUCTIONS.md](./BUILD_INSTRUCTIONS.md) for details.

### Step 2: Create Namespace

```bash
kubectl create namespace production
```

### Step 3: Create Secrets

```bash
kubectl create secret generic order-service-secrets \
  --from-literal=metricsAuthToken='my-secret-token' \
  -n production
```

### Step 4: Deploy with Helm

```bash
helm install order-service ../obskit \
  --namespace production \
  --values values.yaml \
  --set image.repository=my-registry.example.com/order-service \
  --set image.tag=v1.0.0
```

### Step 5: Verify

```bash
# Check pods
kubectl get pods -n production

# Port forward
kubectl port-forward -n production svc/order-service 8080:80 9090:9090

# Test (in another terminal)
curl http://localhost:8080/health
curl -H "Authorization: Bearer my-secret-token" http://localhost:9090/metrics
```

## ✅ Done!

Your service is now running with full observability!

## Next Steps

- View logs: `kubectl logs -n production -l app.kubernetes.io/name=obskit-service`
- Check metrics: Access Prometheus and query `order_service_requests_total`
- Scale: `kubectl scale deployment order-service -n production --replicas=5`

For more details, see [COMPLETE_EXAMPLE.md](./COMPLETE_EXAMPLE.md)

