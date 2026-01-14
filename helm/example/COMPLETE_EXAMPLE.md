# Complete Helm Chart Example - Step by Step

This is a **complete, working example** of deploying a service with obskit using Helm.

## 📁 Files in This Example

```
helm/example/
├── values.yaml          # Complete production values
├── deploy.sh            # Automated deployment script
├── test-service.py      # Example FastAPI service
├── Dockerfile           # Container image
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## 🚀 Complete Deployment Workflow

### Step 1: Build the Service Image

```bash
cd helm/example

# Build Docker image (installs obskit from local source)
# Option 1: Using build script (recommended)
./build.sh v1.2.3 my-registry.example.com/order-service

# Option 2: Manual build from repo root
cd ../..  # Go to repository root
docker build \
  -f obskit/helm/example/Dockerfile.local \
  -t my-registry.example.com/order-service:v1.2.3 \
  .

# Push to registry
docker push my-registry.example.com/order-service:v1.2.3
```

**Note:** Since obskit is not published to PyPI yet, we use `Dockerfile.local` which installs obskit from the local source. See [BUILD_INSTRUCTIONS.md](./BUILD_INSTRUCTIONS.md) for more details.

### Step 2: Prepare Kubernetes Cluster

```bash
# Create namespace
kubectl create namespace production

# Create image pull secret (if using private registry)
kubectl create secret docker-registry registry-secret \
  --docker-server=my-registry.example.com \
  --docker-username=your-username \
  --docker-password=your-password \
  -n production
```

### Step 3: Create Application Secrets

```bash
# Create secrets for the service
kubectl create secret generic order-service-secrets \
  --from-literal=metricsAuthToken='prod-metrics-token-abc123xyz' \
  --from-literal=databaseUrl='postgresql://user:pass@db:5432/orders' \
  -n production
```

### Step 4: Deploy with Helm

#### Option A: Using the deployment script

```bash
cd helm/example
chmod +x deploy.sh
./deploy.sh v1.2.3
```

#### Option B: Manual deployment

```bash
# Install the chart
helm install order-service ../obskit \
  --namespace production \
  --values values.yaml \
  --set image.repository=my-registry.example.com/order-service \
  --set image.tag=v1.2.3 \
  --wait \
  --timeout 5m
```

### Step 5: Verify Deployment

```bash
# Check pods
kubectl get pods -n production -l app.kubernetes.io/name=obskit-service

# Check service
kubectl get svc -n production order-service

# Check logs
kubectl logs -n production -l app.kubernetes.io/name=obskit-service --tail=100

# Check deployment status
kubectl get deployment -n production order-service
```

### Step 6: Test the Service

```bash
# Port forward to access the service
kubectl port-forward -n production svc/order-service 8080:80 9090:9090

# In another terminal, test endpoints:

# Health check
curl http://localhost:8080/health

# Readiness check
curl http://localhost:8080/ready

# Liveness check
curl http://localhost:8080/live

# Metrics (with authentication)
curl -H "Authorization: Bearer prod-metrics-token-abc123xyz" \
  http://localhost:9090/metrics

# Create an order
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"id": "123", "amount": 100.0}'

# Get order
curl http://localhost:8080/orders/123
```

## 📊 Monitoring Setup

### Prometheus ServiceMonitor

The chart automatically creates a ServiceMonitor. Verify it:

```bash
kubectl get servicemonitor -n production order-service

# Check Prometheus targets
# (Access Prometheus UI and check targets)
```

### View Metrics in Prometheus

```bash
# Port forward Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090

# Access Prometheus UI
open http://localhost:9090

# Query metrics:
# - order_service_requests_total
# - order_service_request_duration_seconds
# - order_service_errors_total
```

### Grafana Dashboard

1. Import the obskit dashboard JSON
2. Set data source to Prometheus
3. View metrics for your service

## 🔧 Customization Examples

### Development Environment

```bash
helm install order-service-dev ../obskit \
  --namespace development \
  --set obskit.environment=development \
  --set obskit.logLevel=DEBUG \
  --set obskit.logFormat=console \
  --set obskit.metricsSampleRate=1.0 \
  --set obskit.logSampleRate=1.0 \
  --set obskit.traceSampleRate=1.0 \
  --set replicaCount=1 \
  --set image.tag=dev-latest \
  --set obskit.otlpInsecure=true
```

### High-Traffic Service

```bash
helm install order-service ../obskit \
  --namespace production \
  --values values.yaml \
  --set obskit.metricsSampleRate=0.01 \
  --set obskit.logSampleRate=0.001 \
  --set obskit.traceSampleRate=0.01 \
  --set autoscaling.enabled=true \
  --set autoscaling.minReplicas=5 \
  --set autoscaling.maxReplicas=50 \
  --set resources.limits.cpu=2000m \
  --set resources.limits.memory=2Gi
```

### Multi-Region Deployment

```bash
# US East
helm install order-service-us-east ../obskit \
  --namespace production \
  --values values.yaml \
  --set obskit.serviceName=order-service-us-east \
  --set nodeSelector.region=us-east-1

# US West
helm install order-service-us-west ../obskit \
  --namespace production \
  --values values.yaml \
  --set obskit.serviceName=order-service-us-west \
  --set nodeSelector.region=us-west-2
```

## 🔄 Updates and Rollbacks

### Update to New Version

```bash
# Build new image
docker build -t my-registry.example.com/order-service:v1.2.4 .
docker push my-registry.example.com/order-service:v1.2.4

# Upgrade Helm release
helm upgrade order-service ../obskit \
  --namespace production \
  --set image.tag=v1.2.4 \
  --reuse-values \
  --wait
```

### Rollback

```bash
# List releases
helm history order-service -n production

# Rollback to previous version
helm rollback order-service -n production

# Rollback to specific revision
helm rollback order-service 2 -n production
```

## 🧪 Testing

### Load Testing

```bash
# Install k6
brew install k6  # macOS
# or
apt-get install k6  # Linux

# Create load test script
cat > load-test.js <<EOF
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  vus: 100,
  duration: '5m',
};

export default function() {
  let res = http.post('http://order-service.production.svc.cluster.local/orders', 
    JSON.stringify({ id: 'test', amount: 100 }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  check(res, { 'status was 200': (r) => r.status == 200 });
}
EOF

# Run load test
k6 run load-test.js
```

### Health Check Testing

```bash
# Test all health endpoints
for endpoint in health ready live; do
  echo "Testing /$endpoint:"
  curl -s http://localhost:8080/$endpoint | jq .
  echo ""
done
```

## 🔒 Security

### Network Policies

```bash
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: order-service-netpol
  namespace: production
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: obskit-service
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 80
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 9090
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: database
    ports:
    - protocol: TCP
      port: 5432
EOF
```

### Pod Security

The values.yaml already includes security best practices:
- Non-root user
- Read-only root filesystem
- Dropped capabilities

## 📈 Scaling

### Manual Scaling

```bash
kubectl scale deployment order-service -n production --replicas=10
```

### Auto Scaling (HPA)

Already configured in values.yaml:

```yaml
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70
```

Check HPA:

```bash
kubectl get hpa -n production order-service
```

## 🗑️ Cleanup

```bash
# Uninstall Helm release
helm uninstall order-service -n production

# Delete secrets
kubectl delete secret order-service-secrets -n production

# Delete namespace (if empty)
kubectl delete namespace production
```

## 📚 Next Steps

1. **Customize values.yaml** for your service
2. **Set up CI/CD** to automate deployments
3. **Configure alerting** in Prometheus
4. **Create Grafana dashboards** for your metrics
5. **Set up log aggregation** (ELK, Loki, etc.)
6. **Configure distributed tracing** (Jaeger, Tempo)

## 🆘 Troubleshooting

### Pods Not Starting

```bash
# Check pod events
kubectl describe pod -n production -l app.kubernetes.io/name=obskit-service

# Check logs
kubectl logs -n production -l app.kubernetes.io/name=obskit-service
```

### Metrics Not Appearing

```bash
# Check metrics endpoint
kubectl port-forward -n production svc/order-service 9090:9090
curl -H "Authorization: Bearer prod-metrics-token-abc123xyz" \
  http://localhost:9090/metrics

# Check ServiceMonitor
kubectl get servicemonitor -n production order-service -o yaml
```

### Health Checks Failing

```bash
# Check health endpoint
kubectl exec -n production -it deployment/order-service -- \
  curl http://localhost:8080/health

# Check readiness
kubectl get pods -n production -l app.kubernetes.io/name=obskit-service
```

## ✅ Success Criteria

Your deployment is successful when:

- ✅ All pods are running: `kubectl get pods` shows all pods as `Running`
- ✅ Health endpoint returns 200: `curl http://localhost:8080/health`
- ✅ Metrics endpoint accessible: `curl http://localhost:9090/metrics` (with auth)
- ✅ ServiceMonitor created: `kubectl get servicemonitor`
- ✅ Prometheus scraping: Check Prometheus targets
- ✅ Logs are structured: `kubectl logs` shows JSON logs

---

**🎉 Congratulations!** You now have a complete, production-ready deployment with obskit!

