# Kubernetes Deployment Guide

Complete guide to deploying obskit-instrumented services on Kubernetes.

---

## Complete Deployment Manifest

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: my-service
---
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: obskit-secrets
  namespace: my-service
type: Opaque
stringData:
  metrics-token: "YOUR_SECURE_TOKEN_HERE"
---
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: obskit-config
  namespace: my-service
data:
  OBSKIT_SERVICE_NAME: "my-service"
  OBSKIT_ENVIRONMENT: "production"
  OBSKIT_LOG_LEVEL: "INFO"
  OBSKIT_LOG_FORMAT: "json"
  OBSKIT_METRICS_ENABLED: "true"
  OBSKIT_METRICS_PORT: "9090"
  OBSKIT_METRICS_AUTH_ENABLED: "true"
  OBSKIT_METRICS_RATE_LIMIT_ENABLED: "true"
  OBSKIT_TRACING_ENABLED: "true"
  OBSKIT_OTLP_ENDPOINT: "http://jaeger-collector.monitoring:4317"
  OBSKIT_OTLP_INSECURE: "false"
  OBSKIT_METRICS_SAMPLE_RATE: "0.1"
  OBSKIT_LOG_SAMPLE_RATE: "0.1"
  OBSKIT_TRACE_SAMPLE_RATE: "0.1"
  OBSKIT_ENABLE_SELF_METRICS: "true"
---
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
  namespace: my-service
  labels:
    app: my-service
    version: v1.0.0
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-service
  template:
    metadata:
      labels:
        app: my-service
        version: v1.0.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: my-service
      containers:
      - name: my-service
        image: my-registry/my-service:1.0.0
        imagePullPolicy: Always
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        - name: metrics
          containerPort: 9090
          protocol: TCP
        
        # Environment from ConfigMap
        envFrom:
        - configMapRef:
            name: obskit-config
        
        # Secrets
        env:
        - name: OBSKIT_VERSION
          value: "1.0.0"
        - name: OBSKIT_METRICS_AUTH_TOKEN
          valueFrom:
            secretKeyRef:
              name: obskit-secrets
              key: metrics-token
        
        # Health probes
        livenessProbe:
          httpGet:
            path: /live
            port: http
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
          
        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
          
        startupProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 0
          periodSeconds: 5
          timeoutSeconds: 5
          failureThreshold: 30
        
        # Resources
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        
        # Security context
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          readOnlyRootFilesystem: true
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - ALL
      
      # Pod security
      securityContext:
        fsGroup: 1000
---
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
  namespace: my-service
  labels:
    app: my-service
spec:
  type: ClusterIP
  ports:
  - name: http
    port: 80
    targetPort: http
    protocol: TCP
  - name: metrics
    port: 9090
    targetPort: metrics
    protocol: TCP
  selector:
    app: my-service
---
# hpa.yaml (Horizontal Pod Autoscaler)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-service
  namespace: my-service
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
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
---
# pdb.yaml (Pod Disruption Budget)
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: my-service
  namespace: my-service
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: my-service
---
# serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-service
  namespace: my-service
```

---

## Prometheus ServiceMonitor

For Prometheus Operator:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: my-service
  namespace: my-service
  labels:
    app: my-service
spec:
  selector:
    matchLabels:
      app: my-service
  namespaceSelector:
    matchNames:
    - my-service
  endpoints:
  - port: metrics
    path: /metrics
    interval: 30s
    scrapeTimeout: 10s
    bearerTokenSecret:
      name: obskit-secrets
      key: metrics-token
```

---

## Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: my-service-network-policy
  namespace: my-service
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
    - protocol: TCP
      port: 8080
  # Allow Prometheus to scrape metrics
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
      podSelector:
        matchLabels:
          app.kubernetes.io/name: prometheus
    ports:
    - protocol: TCP
      port: 9090
  egress:
  # Allow DNS
  - to:
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
  # Allow OTLP to Jaeger
  - to:
    - namespaceSelector:
        matchLabels:
          name: monitoring
      podSelector:
        matchLabels:
          app: jaeger
    ports:
    - protocol: TCP
      port: 4317
```

---

## Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-service
  namespace: my-service
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - my-service.example.com
    secretName: my-service-tls
  rules:
  - host: my-service.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-service
            port:
              number: 80
```

---

## Helm Chart Values

For the included Helm chart:

```yaml
# values.yaml
replicaCount: 3

image:
  repository: my-registry/my-service
  tag: "1.0.0"
  pullPolicy: Always

service:
  type: ClusterIP
  port: 80
  metricsPort: 9090

obskit:
  serviceName: my-service
  environment: production
  logLevel: INFO
  logFormat: json
  metricsEnabled: true
  metricsAuthEnabled: true
  metricsRateLimitEnabled: true
  tracingEnabled: true
  otlpEndpoint: http://jaeger-collector:4317
  sampleRate: 0.1

secrets:
  metricsToken: ""  # Set via --set or external secrets

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 256Mi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

podDisruptionBudget:
  enabled: true
  minAvailable: 2

serviceMonitor:
  enabled: true
  interval: 30s
```

Install with Helm:

```bash
helm install my-service ./helm/obskit \
  --namespace my-service \
  --create-namespace \
  --set secrets.metricsToken="$METRICS_TOKEN" \
  -f values.yaml
```

---

## Prometheus Alerting Rules

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: my-service-alerts
  namespace: monitoring
spec:
  groups:
  - name: my-service.rules
    rules:
    # High error rate
    - alert: MyServiceHighErrorRate
      expr: |
        sum(rate(red_requests_total{service="my-service", status="error"}[5m]))
        / sum(rate(red_requests_total{service="my-service"}[5m])) > 0.05
      for: 5m
      labels:
        severity: critical
        service: my-service
      annotations:
        summary: "High error rate for my-service"
        description: "Error rate is {{ $value | humanizePercentage }}"
    
    # High latency
    - alert: MyServiceHighLatency
      expr: |
        histogram_quantile(0.99, 
          sum(rate(red_request_duration_seconds_bucket{service="my-service"}[5m])) by (le)
        ) > 0.5
      for: 5m
      labels:
        severity: warning
        service: my-service
      annotations:
        summary: "High P99 latency for my-service"
        description: "P99 latency is {{ $value }}s"
    
    # Pod restarts
    - alert: MyServicePodRestarts
      expr: |
        increase(kube_pod_container_status_restarts_total{
          namespace="my-service",
          container="my-service"
        }[1h]) > 3
      for: 5m
      labels:
        severity: warning
        service: my-service
      annotations:
        summary: "my-service pod restarts"
        description: "Pod {{ $labels.pod }} has restarted {{ $value }} times"
    
    # Memory usage
    - alert: MyServiceHighMemory
      expr: |
        container_memory_usage_bytes{
          namespace="my-service",
          container="my-service"
        } / container_spec_memory_limit_bytes > 0.9
      for: 5m
      labels:
        severity: warning
        service: my-service
      annotations:
        summary: "High memory usage for my-service"
```

---

## Grafana Dashboard ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-service-dashboard
  namespace: monitoring
  labels:
    grafana_dashboard: "1"
data:
  my-service.json: |
    {
      "title": "My Service Dashboard",
      "panels": [
        {
          "title": "Request Rate",
          "targets": [
            {
              "expr": "sum(rate(red_requests_total{service=\"my-service\"}[5m]))"
            }
          ]
        },
        {
          "title": "Error Rate",
          "targets": [
            {
              "expr": "sum(rate(red_requests_total{service=\"my-service\",status=\"error\"}[5m])) / sum(rate(red_requests_total{service=\"my-service\"}[5m]))"
            }
          ]
        }
      ]
    }
```

---

## Deployment Commands

```bash
# Apply all manifests
kubectl apply -f namespace.yaml
kubectl apply -f secrets.yaml
kubectl apply -f configmap.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f servicemonitor.yaml

# Or with kustomize
kubectl apply -k ./

# Check deployment
kubectl -n my-service get pods
kubectl -n my-service get svc
kubectl -n my-service logs -l app=my-service

# Check metrics
kubectl -n my-service port-forward svc/my-service 9090:9090
curl -H "Authorization: Bearer $TOKEN" http://localhost:9090/metrics

# Check health
kubectl -n my-service port-forward svc/my-service 8080:80
curl http://localhost:8080/health
curl http://localhost:8080/ready
curl http://localhost:8080/live
```

---

## Troubleshooting

### Pod Not Starting

```bash
# Check events
kubectl -n my-service describe pod <pod-name>

# Check logs
kubectl -n my-service logs <pod-name> --previous
```

### Health Check Failing

```bash
# Exec into pod
kubectl -n my-service exec -it <pod-name> -- /bin/sh

# Test health endpoint
curl http://localhost:8080/health
```

### Metrics Not Appearing

```bash
# Check metrics endpoint
kubectl -n my-service port-forward svc/my-service 9090:9090
curl -H "Authorization: Bearer $TOKEN" http://localhost:9090/metrics

# Check ServiceMonitor
kubectl -n my-service get servicemonitor
kubectl -n monitoring logs -l app.kubernetes.io/name=prometheus
```
