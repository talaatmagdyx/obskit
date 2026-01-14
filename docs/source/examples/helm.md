# Helm Chart Deployment

The obskit Helm chart simplifies deploying observable applications to Kubernetes.

## Quick Start

```bash
# Add the repository (when published)
helm repo add obskit https://obskit.github.io/charts
helm repo update

# Install
helm install my-service obskit/obskit \
  --set image.repository=my-registry/my-service \
  --set image.tag=v1.0.0 \
  --set config.serviceName=my-service
```

## Local Installation

```bash
# From the obskit repository
cd helm/obskit
helm install my-service . -f values.yaml
```

## values.yaml Reference

```yaml
# Image configuration
image:
  repository: my-registry/my-service
  tag: latest
  pullPolicy: IfNotPresent

# Replica count
replicaCount: 3

# Service configuration
service:
  type: ClusterIP
  port: 80
  metricsPort: 9090

# obskit configuration
config:
  serviceName: my-service
  logLevel: INFO
  metricsEnabled: true
  tracingEnabled: true
  otlpEndpoint: "http://jaeger-collector:4317"
  
  # Sampling
  metricsSampleRate: "1.0"
  traceSampleRate: "0.1"
  
  # PII redaction
  piiRedaction: true

# Health probes
livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 10
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: http
  initialDelaySeconds: 5
  periodSeconds: 5

# Resources
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi

# Autoscaling
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

# Service Monitor for Prometheus Operator
serviceMonitor:
  enabled: true
  interval: 15s
  labels:
    release: prometheus

# Prometheus alerts
prometheusRules:
  enabled: true
  rules:
    - alert: HighErrorRate
      expr: |
        sum(rate({{ .Values.config.serviceName }}_requests_total{status="error"}[5m]))
        / sum(rate({{ .Values.config.serviceName }}_requests_total[5m]))
        > 0.01
      for: 5m
      labels:
        severity: warning

# Grafana dashboard
grafanaDashboard:
  enabled: true
  labels:
    grafana_dashboard: "1"

# Ingress
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: my-service.example.com
      paths:
        - path: /
          pathType: Prefix

# Pod disruption budget
podDisruptionBudget:
  enabled: true
  minAvailable: 2

# Network policy
networkPolicy:
  enabled: true
  allowPrometheus: true
  allowJaeger: true
```

## Environment-Specific Values

### development.yaml

```yaml
replicaCount: 1

config:
  logLevel: DEBUG
  traceSampleRate: "1.0"  # Sample all traces

autoscaling:
  enabled: false

resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 200m
    memory: 256Mi
```

### production.yaml

```yaml
replicaCount: 5

config:
  logLevel: INFO
  traceSampleRate: "0.01"  # 1% sampling

autoscaling:
  enabled: true
  minReplicas: 5
  maxReplicas: 20

resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 2Gi

podDisruptionBudget:
  enabled: true
  minAvailable: 3
```

## Installation Examples

### Basic Installation

```bash
helm install my-service ./helm/obskit \
  --set image.repository=my-registry/my-service \
  --set image.tag=v1.0.0
```

### With Custom Values

```bash
helm install my-service ./helm/obskit \
  -f values.yaml \
  -f production.yaml \
  --set image.tag=v1.0.0
```

### Dry Run

```bash
helm install my-service ./helm/obskit \
  -f values.yaml \
  --dry-run --debug
```

### Upgrade

```bash
helm upgrade my-service ./helm/obskit \
  --set image.tag=v1.1.0 \
  --reuse-values
```

### Rollback

```bash
helm rollback my-service 1
```

## Monitoring Stack

Deploy with the full monitoring stack:

```bash
# Install Prometheus
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace

# Install Jaeger
helm install jaeger jaegertracing/jaeger \
  -n monitoring \
  --set collector.service.otlp.grpc.enabled=true

# Install your service
helm install my-service ./helm/obskit \
  --set config.otlpEndpoint="http://jaeger-collector.monitoring:4317"
```

## Template Structure

```
helm/obskit/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── hpa.yaml
│   ├── pdb.yaml
│   ├── ingress.yaml
│   ├── networkpolicy.yaml
│   ├── servicemonitor.yaml
│   ├── prometheusrule.yaml
│   └── grafana-dashboard.yaml
└── dashboards/
    └── obskit-red-dashboard.json
```

## Troubleshooting

### Check Release Status

```bash
helm status my-service
helm history my-service
```

### View Generated Manifests

```bash
helm get manifest my-service
```

### Debug Template Rendering

```bash
helm template my-service ./helm/obskit \
  -f values.yaml \
  --debug
```

### Common Issues

1. **Image pull errors**: Check `imagePullSecrets`
2. **Probe failures**: Verify health endpoints
3. **Missing metrics**: Check ServiceMonitor labels

## Next Steps

- **[Kubernetes Deployment](kubernetes.md)** - Manual deployment
- **[Configuration](../config/index.md)** - All obskit options
- **[Troubleshooting](../troubleshooting/index.md)** - Common issues

