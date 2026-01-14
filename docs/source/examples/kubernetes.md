# Kubernetes Deployment

Deploy your obskit-instrumented application to Kubernetes.

## Deployment Manifests

### deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
  labels:
    app: my-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-service
  template:
    metadata:
      labels:
        app: my-service
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      containers:
        - name: app
          image: my-service:latest
          ports:
            - name: http
              containerPort: 8000
            - name: metrics
              containerPort: 9090
          
          env:
            - name: OBSKIT_SERVICE_NAME
              value: "my-service"
            - name: OBSKIT_LOG_LEVEL
              value: "INFO"
            - name: OBSKIT_OTLP_ENDPOINT
              value: "http://jaeger-collector.monitoring:4317"
          
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          
          readinessProbe:
            httpGet:
              path: /ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 3
          
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

### service.yaml

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
  labels:
    app: my-service
spec:
  type: ClusterIP
  ports:
    - name: http
      port: 80
      targetPort: http
    - name: metrics
      port: 9090
      targetPort: metrics
  selector:
    app: my-service
```

### servicemonitor.yaml

For Prometheus Operator:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-service
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: my-service
  endpoints:
    - port: metrics
      interval: 15s
      path: /metrics
```

## ConfigMap for Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-service-config
data:
  OBSKIT_SERVICE_NAME: "my-service"
  OBSKIT_LOG_LEVEL: "INFO"
  OBSKIT_METRICS_SAMPLE_RATE: "1.0"
  OBSKIT_TRACE_SAMPLE_RATE: "0.1"
```

Reference in deployment:

```yaml
envFrom:
  - configMapRef:
      name: my-service-config
```

## Secrets for Sensitive Config

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: my-service-secrets
type: Opaque
stringData:
  OBSKIT_METRICS_AUTH_TOKEN: "your-secret-token"
```

## Prometheus Rules

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: my-service-alerts
  labels:
    release: prometheus
spec:
  groups:
    - name: my-service.rules
      rules:
        - alert: HighErrorRate
          expr: |
            sum(rate(my_service_requests_total{status="error"}[5m]))
            /
            sum(rate(my_service_requests_total[5m]))
            > 0.01
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High error rate for my-service"
            description: "Error rate is {{ $value | humanizePercentage }}"
        
        - alert: HighLatency
          expr: |
            histogram_quantile(0.99,
              sum(rate(my_service_request_duration_seconds_bucket[5m])) by (le)
            ) > 1.0
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High latency for my-service"
            description: "P99 latency is {{ $value | humanizeDuration }}"
```

## Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-service
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-service
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: my_service_requests_per_second
        target:
          type: AverageValue
          averageValue: "1000"
```

## Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: my-service
spec:
  podSelector:
    matchLabels:
      app: my-service
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow traffic from ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - port: 8000
    # Allow Prometheus scraping
    - from:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - port: 9090
  egress:
    # Allow DNS
    - to:
        - namespaceSelector: {}
      ports:
        - port: 53
          protocol: UDP
    # Allow Jaeger
    - to:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - port: 4317
```

## Complete Kustomization

```yaml
# kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: my-service

resources:
  - deployment.yaml
  - service.yaml
  - servicemonitor.yaml
  - prometheusrule.yaml
  - hpa.yaml
  - networkpolicy.yaml

configMapGenerator:
  - name: my-service-config
    literals:
      - OBSKIT_SERVICE_NAME=my-service
      - OBSKIT_LOG_LEVEL=INFO

images:
  - name: my-service
    newTag: v1.0.0
```

## Deployment Commands

```bash
# Apply with kustomize
kubectl apply -k .

# Or apply directly
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml

# Check status
kubectl get pods -l app=my-service
kubectl logs -l app=my-service -f

# View metrics
kubectl port-forward svc/my-service 9090:9090
curl http://localhost:9090/metrics
```

## Next Steps

- **[Helm Chart](helm.md)** - Simplified deployment with Helm
- **[FastAPI Example](fastapi.md)** - Application code
- **[Troubleshooting](../troubleshooting/index.md)** - Common issues

