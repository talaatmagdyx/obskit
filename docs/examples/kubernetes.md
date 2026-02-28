# Kubernetes Deployment Tutorial

Deploy the Order Service from the [FastAPI example](fastapi.md) to Kubernetes with a full production-grade observability stack — Prometheus, Grafana, Grafana Tempo, and Loki — in approximately 15 minutes.

---

## Prerequisites

- `kubectl` configured against a cluster (local: `kind`, `k3d`, or `minikube`)
- `helm` v3.x installed
- Docker registry access (or local registry for `kind`)

---

## Overview

```mermaid
flowchart LR
    subgraph Cluster["Kubernetes Cluster"]
        subgraph App["Namespace: production"]
            SVC["order-service\nDeployment × 3"]
        end
        subgraph Mon["Namespace: monitoring"]
            Prom["Prometheus\n:9090"]
            Grafana["Grafana\n:3000"]
            Tempo["Grafana Tempo\nOTLP :4317"]
            Loki["Grafana Loki\n:3100"]
            Promtail["Promtail\n(DaemonSet)"]
        end
    end
    SVC -- "OTLP gRPC traces" --> Tempo
    Prom -- "scrape /metrics" --> SVC
    Promtail -- "ship logs" --> Loki
    Tempo --> Grafana
    Prom --> Grafana
    Loki --> Grafana
```

---

## Step 1: Build and Push the Docker Image

```bash
# Build the order-service image
docker build -t ghcr.io/acme/order-service:2.1.0 .

# Push to registry
docker push ghcr.io/acme/order-service:2.1.0

# For kind clusters: load directly (no push needed)
kind load docker-image ghcr.io/acme/order-service:2.1.0
```

---

## Step 2: Install the Observability Stack with Helm

```bash
# Add Helm repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana             https://grafana.github.io/helm-charts
helm repo update

# Create monitoring namespace
kubectl create namespace monitoring

# Install kube-prometheus-stack (Prometheus + Grafana + Alertmanager)
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set grafana.adminPassword=admin \
  --set grafana.sidecar.dashboards.enabled=true \
  --set grafana.sidecar.datasources.enabled=true \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --wait

# Install Grafana Tempo (distributed tracing)
helm install tempo grafana/tempo \
  --namespace monitoring \
  --set tempo.storage.trace.backend=local \
  --set tempo.reportingEnabled=false \
  --wait

# Install Grafana Loki + Promtail (log aggregation)
helm install loki grafana/loki-stack \
  --namespace monitoring \
  --set loki.enabled=true \
  --set promtail.enabled=true \
  --wait
```

---

## Step 3: Configure Grafana Datasources

```yaml
# k8s/grafana-datasources-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-datasources
  namespace: monitoring
  labels:
    grafana_datasource: "1"
data:
  datasources.yaml: |
    apiVersion: 1
    datasources:
      - name: Prometheus
        type: prometheus
        uid: prometheus
        url: http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090
        isDefault: true
        jsonData:
          timeInterval: "15s"
          exemplarTraceIdDestinations:
            - name: trace_id
              datasourceUid: tempo

      - name: Tempo
        type: tempo
        uid: tempo
        url: http://tempo.monitoring.svc.cluster.local:3100
        jsonData:
          httpMethod: GET
          tracesToLogsV2:
            datasourceUid: loki
            spanStartTimeShift: "-1m"
            spanEndTimeShift: "1m"
            filterByTraceID: true
            customQuery: true
            query: '{service_name="${__span.tags["service.name"]}"} | json | trace_id="${__trace.traceId}"'
          serviceMap:
            datasourceUid: prometheus
          nodeGraph:
            enabled: true
          lokiSearch:
            datasourceUid: loki

      - name: Loki
        type: loki
        uid: loki
        url: http://loki.monitoring.svc.cluster.local:3100
        jsonData:
          derivedFields:
            - matcherRegex: '"trace_id":"(\w+)"'
              name: trace_id
              url: "${__value.raw}"
              datasourceUid: tempo
```

```bash
kubectl apply -f k8s/grafana-datasources-configmap.yaml
```

---

## Step 4: Deploy the Application

Create all application manifests:

```bash
# Create production namespace
kubectl create namespace production
```

```yaml
# k8s/all-in-one.yaml — apply with a single command
---
# ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: order-service-obskit
  namespace: production
data:
  OBSKIT_SERVICE_NAME: "order-service"
  OBSKIT_ENVIRONMENT: "production"
  OBSKIT_TRACING_ENABLED: "true"
  OBSKIT_OTLP_ENDPOINT: "http://tempo.monitoring.svc.cluster.local:4317"
  OBSKIT_OTLP_INSECURE: "true"
  OBSKIT_TRACE_SAMPLE_RATE: "0.1"
  OBSKIT_METRICS_ENABLED: "true"
  OBSKIT_METRICS_PORT: "9090"
  OBSKIT_LOG_LEVEL: "INFO"
  OBSKIT_LOG_FORMAT: "json"
  OBSKIT_HEALTH_CHECK_TIMEOUT: "5.0"
  OBSKIT_CIRCUIT_BREAKER_FAILURE_THRESHOLD: "5"
  OBSKIT_RETRY_MAX_ATTEMPTS: "3"
---
# Secret
apiVersion: v1
kind: Secret
metadata:
  name: order-service-db
  namespace: production
type: Opaque
stringData:
  DATABASE_URL: "postgresql://user:pass@postgres.production:5432/orders"
  REDIS_URL: "redis://redis.production:6379"
---
# ServiceAccount
apiVersion: v1
kind: ServiceAccount
metadata:
  name: order-service
  namespace: production
---
# Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: production
  labels:
    app: order-service
    version: "2.1.0"
spec:
  replicas: 3
  selector:
    matchLabels:
      app: order-service
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: order-service
        version: "2.1.0"
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: order-service
      terminationGracePeriodSeconds: 60
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
        - name: order-service
          image: ghcr.io/acme/order-service:2.1.0
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8000
            - name: metrics
              containerPort: 9090
            - name: health
              containerPort: 8001
          envFrom:
            - configMapRef:
                name: order-service-obskit
            - secretRef:
                name: order-service-db
          env:
            - name: OBSKIT_VERSION
              value: "2.1.0"
          resources:
            requests:
              cpu: "100m"
              memory: "256Mi"
            limits:
              cpu: "1000m"
              memory: "512Mi"
          startupProbe:
            httpGet:
              path: /health/startup
              port: 8000
            failureThreshold: 30
            periodSeconds: 3
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            periodSeconds: 5
            failureThreshold: 3
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 10"]
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: [ALL]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
---
# Service — application traffic
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: production
spec:
  selector:
    app: order-service
  ports:
    - name: http
      port: 80
      targetPort: http
---
# Service — metrics scraping
apiVersion: v1
kind: Service
metadata:
  name: order-service-metrics
  namespace: production
  labels:
    app: order-service
    monitoring: "true"
spec:
  selector:
    app: order-service
  ports:
    - name: metrics
      port: 9090
      targetPort: metrics
---
# HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

```bash
kubectl apply -f k8s/all-in-one.yaml
```

---

## Step 5: Prometheus ServiceMonitor

```yaml
# k8s/servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: order-service
  namespace: monitoring
  labels:
    release: kube-prometheus-stack
spec:
  namespaceSelector:
    matchNames:
      - production
  selector:
    matchLabels:
      app: order-service
      monitoring: "true"
  endpoints:
    - port: metrics
      path: /metrics
      interval: 15s
      scrapeTimeout: 10s
```

```bash
kubectl apply -f k8s/servicemonitor.yaml

# Verify it appears in Prometheus targets
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090 &
open http://localhost:9090/targets
# Look for "order-service" — it should show State: UP
```

---

## Step 6: Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: order-service
  namespace: production
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/configuration-snippet: |
      proxy_set_header X-Request-ID   $request_id;
      proxy_set_header traceparent    $http_traceparent;
      proxy_set_header tracestate     $http_tracestate;
spec:
  ingressClassName: nginx
  rules:
    - host: api.acme.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: order-service
                port:
                  name: http
```

```bash
kubectl apply -f k8s/ingress.yaml
```

---

## Step 7: Verify the Full Stack

```bash
# 1. Check all pods are running
kubectl get pods -n production
kubectl get pods -n monitoring

# 2. Port-forward Grafana
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80 &
open http://localhost:3000   # admin / admin

# 3. Send test traffic
kubectl port-forward -n production svc/order-service 8000:80 &

curl -X POST http://localhost:8000/orders/ \
  -H "Content-Type: application/json" \
  -d '{"items": [{"sku": "TEST-1", "quantity": 1, "unit_price": 49.99}]}'

# Generate load
for i in $(seq 1 50); do
  curl -s -X POST http://localhost:8000/orders/ \
    -H "Content-Type: application/json" \
    -d "{\"items\": [{\"sku\": \"SKU-$i\", \"quantity\": 1, \"unit_price\": 9.99}]}" &
done
wait

# 4. Check metrics in Prometheus
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090 &
# Open: http://localhost:9090
# Query: rate(http_requests_total{job="order-service"}[1m])

# 5. View traces in Tempo (via Grafana Explore)
# Grafana → Explore → select "Tempo" datasource → Search for service: order-service
```

---

## Step 8: Import obskit Grafana Dashboards

```bash
# Port-forward Grafana API
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80 &

# Import dashboard via API
curl -X POST http://admin:admin@localhost:3000/api/dashboards/import \
  -H "Content-Type: application/json" \
  -d @dashboards/obskit-red-metrics.json

curl -X POST http://admin:admin@localhost:3000/api/dashboards/import \
  -H "Content-Type: application/json" \
  -d @dashboards/obskit-slo.json
```

Or via the ConfigMap approach (automatic provisioning):

```yaml
# k8s/grafana-dashboard-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: obskit-dashboards
  namespace: monitoring
  labels:
    grafana_dashboard: "1"   # Grafana sidecar picks this up automatically
data:
  obskit-red.json: |
    { ... dashboard JSON ... }
```

---

## Observability Stack in 15 Minutes — Summary

| Minute | Action |
|---|---|
| 0–2 | `helm install kube-prometheus-stack` |
| 2–5 | `helm install tempo` and `helm install loki-stack` |
| 5–7 | Apply Grafana datasource ConfigMap (Prometheus + Tempo + Loki with trace correlation) |
| 7–9 | `docker build` + `docker push` (or `kind load`) |
| 9–11 | `kubectl apply -f k8s/all-in-one.yaml` |
| 11–12 | `kubectl apply -f k8s/servicemonitor.yaml` |
| 12–13 | Port-forward and send test traffic |
| 13–14 | Verify targets in Prometheus |
| 14–15 | Import dashboards and view first traces in Grafana |

---

## Troubleshooting Kubernetes Deployment

```bash
# Pod not starting
kubectl describe pod -l app=order-service -n production

# Check application logs
kubectl logs -l app=order-service -n production --tail=50

# Check if metrics endpoint is reachable inside the cluster
kubectl exec -n production deployment/order-service -- \
  wget -qO- http://localhost:9090/metrics | head -10

# Check ServiceMonitor is picked up by Prometheus
kubectl get servicemonitor -n monitoring
kubectl get prometheusrule -n monitoring

# Check Tempo is receiving spans
kubectl logs -n monitoring deployment/tempo --tail=20 | grep "received"

# Confirm OTLP endpoint resolves from the app pod
kubectl exec -n production deployment/order-service -- \
  wget -qO/dev/null --timeout=3 \
  http://tempo.monitoring.svc.cluster.local:4317 2>&1
```

---

!!! tip "Recommended Helm values for production Tempo"
    Switch from single-node to distributed Tempo when ingesting > 10 GB/day of traces:

    ```bash
    helm install tempo grafana/tempo-distributed \
      --namespace monitoring \
      --set storage.trace.backend=s3 \
      --set storage.trace.s3.bucket=acme-tempo-traces \
      --set storage.trace.s3.region=us-east-1 \
      --wait
    ```

!!! warning "Kind / minikube storage limits"
    Local Kubernetes clusters have limited disk. Use the `local` backend for Tempo and set a short retention:

    ```yaml
    # tempo-values.yaml for local dev
    tempo:
      storage:
        trace:
          backend: local
          local:
            path: /var/tempo
      retention: 24h   # keep only 24 hours of traces
    ```

!!! info "Promtail log parsing"
    Promtail ships all container logs to Loki. obskit writes JSON logs, which Promtail can parse with a pipeline stage to extract `trace_id` as a label for fast filtering:

    ```yaml
    # promtail pipeline stage (add to promtail configmap)
    pipelineStages:
      - json:
          expressions:
            trace_id: trace_id
            level:    level
            service:  service
      - labels:
          trace_id:
          level:
          service:
    ```

=== "Verify metrics scraping"

    ```bash
    # Check Prometheus target is UP
    kubectl port-forward -n monitoring \
      svc/kube-prometheus-stack-prometheus 9090:9090 &
    curl -s http://localhost:9090/api/v1/targets | \
      python3 -c "
    import sys, json
    data = json.load(sys.stdin)
    for t in data['data']['activeTargets']:
        if 'order-service' in t['labels'].get('job', ''):
            print('job:', t['labels']['job'])
            print('state:', t['health'])
            print('lastScrape:', t['lastScrape'])
    "
    ```

=== "Verify traces in Tempo"

    ```bash
    # Query Tempo for recent traces from order-service
    kubectl port-forward -n monitoring svc/tempo 3200:3200 &
    curl -s "http://localhost:3200/api/search?service.name=order-service&limit=5" | \
      python3 -m json.tool | head -40
    ```

=== "Verify logs in Loki"

    ```bash
    # Query Loki for recent order-service logs
    kubectl port-forward -n monitoring svc/loki 3100:3100 &
    ENCODED="%7Bapp%3D%22order-service%22%7D"
    curl -s "http://localhost:3100/loki/api/v1/query_range?query=$ENCODED&limit=10" | \
      python3 -c "
    import sys, json
    data = json.load(sys.stdin)
    for stream in data.get('data', {}).get('result', []):
        for ts, line in stream.get('values', []):
            try:
                print(json.loads(line)['event'])
            except: print(line)
    "
    ```
