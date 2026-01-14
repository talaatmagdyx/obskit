# Kubernetes Deployment Tutorial

Deploy an obskit-instrumented application to Kubernetes with full observability.

## Video Tutorial

<!-- Placeholder for asciinema embed -->
<div id="k8s-demo">
<p><em>Record this tutorial: <code>asciinema rec kubernetes.cast -c "bash docs/source/tutorials/scripts/kubernetes.sh"</code></em></p>
</div>

## What You'll Learn

1. Containerizing an obskit application
2. Deploying to Kubernetes
3. Setting up Prometheus scraping
4. Configuring health checks

## Prerequisites

- Docker
- kubectl configured
- A Kubernetes cluster (minikube, kind, or cloud)

## Step-by-Step

### 1. Create the application

```python
# app.py
from fastapi import FastAPI
from obskit import configure, get_red_metrics, start_http_server
from obskit.middleware import ObskitMiddleware
from obskit.health import get_health_checker
import os

# Configure from environment
configure(
    service_name=os.getenv("SERVICE_NAME", "k8s-demo"),
    environment=os.getenv("ENVIRONMENT", "production"),
    log_format="json",
)

app = FastAPI()
app.add_middleware(ObskitMiddleware)

metrics = get_red_metrics()
health = get_health_checker()

# Start metrics server
start_http_server(9090)

@health.add_readiness_check("self")
async def check_ready():
    return True

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/health")
async def health_endpoint():
    result = await health.check_health()
    return result.to_dict()

@app.get("/ready")
async def ready_endpoint():
    result = await health.check_readiness()
    return result.to_dict()
```

### 2. Create Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8000 9090

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

```
# requirements.txt
obskit[fastapi]
uvicorn
```

### 3. Build and push image

```bash
docker build -t myregistry/obskit-demo:latest .
docker push myregistry/obskit-demo:latest
```

### 4. Create Kubernetes manifests

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: obskit-demo
  labels:
    app: obskit-demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: obskit-demo
  template:
    metadata:
      labels:
        app: obskit-demo
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: app
        image: myregistry/obskit-demo:latest
        ports:
        - containerPort: 8000
          name: http
        - containerPort: 9090
          name: metrics
        env:
        - name: SERVICE_NAME
          value: "obskit-demo"
        - name: ENVIRONMENT
          value: "production"
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 5
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: obskit-demo
  labels:
    app: obskit-demo
spec:
  ports:
  - port: 80
    targetPort: 8000
    name: http
  - port: 9090
    targetPort: 9090
    name: metrics
  selector:
    app: obskit-demo
```

### 5. Deploy to Kubernetes

```bash
kubectl apply -f deployment.yaml

# Check status
kubectl get pods -l app=obskit-demo
kubectl get svc obskit-demo
```

### 6. Verify observability

```bash
# Port forward to test
kubectl port-forward svc/obskit-demo 8080:80 &
kubectl port-forward svc/obskit-demo 9090:9090 &

# Test endpoint
curl http://localhost:8080/

# View metrics
curl http://localhost:9090/metrics

# Check health
curl http://localhost:8080/health
```

### 7. Configure Prometheus ServiceMonitor (if using Prometheus Operator)

```yaml
# servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: obskit-demo
  labels:
    release: prometheus  # Match your Prometheus installation
spec:
  selector:
    matchLabels:
      app: obskit-demo
  endpoints:
  - port: metrics
    interval: 15s
    path: /metrics
```

## Using Helm

For production, use the obskit Helm chart:

```bash
helm install my-service ./helm/obskit \
  --set image.repository=myregistry/obskit-demo \
  --set image.tag=latest \
  --set service.name=obskit-demo \
  --set prometheus.enabled=true
```

## Script for Recording

```bash
#!/bin/bash
# Kubernetes deployment tutorial

clear
echo "# Kubernetes Deployment with obskit"
sleep 1

echo "# Using kind for local cluster"
kind create cluster --name obskit-demo 2>/dev/null || true

echo ""
echo "# Build container image"
# (Build steps)

echo ""
echo "# Deploy to Kubernetes"
kubectl apply -f deployment.yaml

echo ""
echo "# Wait for pods"
kubectl wait --for=condition=ready pod -l app=obskit-demo --timeout=60s

echo ""
echo "# Check pods"
kubectl get pods -l app=obskit-demo

echo ""
echo "# Port forward and test"
kubectl port-forward svc/obskit-demo 8080:80 &
sleep 2
curl -s http://localhost:8080/ | python -m json.tool

echo ""
echo "# View metrics"
kubectl port-forward svc/obskit-demo 9090:9090 &
sleep 2
curl -s http://localhost:9090/metrics | head -20

echo ""
echo "# Cleanup"
pkill -f "port-forward"
kind delete cluster --name obskit-demo

echo "# Done!"
```

## Production Checklist

- [ ] Resource limits configured
- [ ] Liveness/readiness probes set
- [ ] Prometheus annotations added
- [ ] ServiceMonitor created (if using Operator)
- [ ] Environment variables configured
- [ ] Replica count appropriate
- [ ] PodDisruptionBudget defined
- [ ] Network policies in place

## Next Steps

- [Helm Charts](../examples/helm.md)
- [Grafana Dashboards](../examples/kubernetes.md#grafana)
- [Alert Rules](../config/index.md#alerting)

