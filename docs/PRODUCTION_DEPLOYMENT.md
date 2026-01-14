# Production Deployment Guide

## Table of Contents

1. [Kubernetes Deployment](#kubernetes-deployment)
2. [Configuration Best Practices](#configuration-best-practices)
3. [Performance Tuning](#performance-tuning)
4. [Security Hardening](#security-hardening)
5. [Monitoring Setup](#monitoring-setup)
6. [Troubleshooting](#troubleshooting)

---

## Kubernetes Deployment

### Basic Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  labels:
    app: order-service
spec:
  replicas: 5
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      containers:
      - name: order-service
        image: order-service:2.3.1
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 9090
          name: metrics
        env:
        # Service identification
        - name: OBSKIT_SERVICE_NAME
          value: "order-service"
        - name: OBSKIT_ENVIRONMENT
          value: "production"
        - name: OBSKIT_VERSION
          valueFrom:
            fieldRef:
              fieldPath: metadata.labels['version']
        
        # Observability configuration
        - name: OBSKIT_LOG_LEVEL
          value: "INFO"
        - name: OBSKIT_LOG_FORMAT
          value: "json"
        - name: OBSKIT_LOG_SAMPLE_RATE
          value: "0.01"  # Sample 1% of logs
        
        # Metrics configuration
        - name: OBSKIT_METRICS_ENABLED
          value: "true"
        - name: OBSKIT_METRICS_PORT
          value: "9090"
        - name: OBSKIT_METRICS_SAMPLE_RATE
          value: "0.1"  # Sample 10% for high-frequency ops
        - name: OBSKIT_METRICS_AUTH_ENABLED
          value: "true"
        - name: OBSKIT_METRICS_AUTH_TOKEN
          valueFrom:
            secretKeyRef:
              name: metrics-auth
              key: token
        
        # Tracing configuration
        - name: OBSKIT_TRACING_ENABLED
          value: "true"
        - name: OBSKIT_OTLP_ENDPOINT
          value: "http://jaeger-collector:4317"
        - name: OBSKIT_TRACE_SAMPLE_RATE
          value: "0.1"  # Sample 10% of traces
        - name: OBSKIT_OTLP_INSECURE
          value: "false"  # Use TLS in production
        
        # Health checks
        livenessProbe:
          httpGet:
            path: /live
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

### Service Configuration

```yaml
apiVersion: v1
kind: Service
metadata:
  name: order-service
  labels:
    app: order-service
spec:
  selector:
    app: order-service
  ports:
  - name: http
    port: 80
    targetPort: 8080
  - name: metrics
    port: 9090
    targetPort: 9090
```

### ServiceMonitor for Prometheus

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: order-service
  labels:
    app: order-service
spec:
  selector:
    matchLabels:
      app: order-service
  endpoints:
  - port: metrics
    path: /metrics
    interval: 30s
    scrapeTimeout: 10s
    bearerTokenSecret:
      name: metrics-auth
      key: token
```

---

## Configuration Best Practices

### High-Frequency Services (100k+ ops/sec)

```python
from obskit import configure

configure(
    service_name="analytics-processor",
    environment="production",
    
    # Aggressive sampling for high volume
    metrics_sample_rate=0.01,  # 1% sampling
    log_sample_rate=0.001,      # 0.1% sampling
    trace_sample_rate=0.01,      # 1% sampling
    
    # Disable tracing if not needed
    tracing_enabled=False,
    
    # Use fast service buckets
    # (set via REDMetrics histogram_buckets parameter)
)
```

### Standard API Services

```python
configure(
    service_name="order-api",
    environment="production",
    
    # Moderate sampling
    metrics_sample_rate=0.1,   # 10% sampling
    log_sample_rate=0.1,        # 10% sampling
    trace_sample_rate=0.1,      # 10% sampling
    
    # Enable all observability
    metrics_enabled=True,
    tracing_enabled=True,
)
```

### Batch Processing Services

```python
configure(
    service_name="batch-processor",
    environment="production",
    
    # No sampling for batch jobs (low volume)
    metrics_sample_rate=1.0,
    log_sample_rate=1.0,
    trace_sample_rate=1.0,
    
    # Enable progress tracking
    # (use GoldenSignals.set_progress())
)
```

---

## Performance Tuning

### Metrics Collection

**For high-frequency operations:**
- Enable metrics sampling (10% recommended)
- Use `track_metrics_only` decorator (no logging)
- Consider async metric recording for ultra-high frequency

**Histogram bucket selection:**
```python
from obskit.metrics import REDMetrics
from obskit.metrics.presets import FAST_SERVICE_BUCKETS

# Fast service (<100ms)
red = REDMetrics("cache", histogram_buckets=FAST_SERVICE_BUCKETS)

# Standard API
from obskit.metrics.presets import API_SERVICE_BUCKETS
red = REDMetrics("api", histogram_buckets=API_SERVICE_BUCKETS)
```

### Logging

**For high-volume services:**
- Enable log sampling (1% recommended)
- Use structured JSON format
- Set appropriate log levels

**Dynamic log level adjustment:**
```python
from obskit.logging.dynamic import set_log_level

# Temporarily enable DEBUG for troubleshooting
set_log_level("DEBUG", component="obskit.metrics")
```

### Tracing

**For high-traffic services:**
- Enable trace sampling (10% recommended)
- Configure export queue size and batch size
- Monitor trace export latency

```python
configure(
    trace_export_queue_size=4096,      # Larger queue for bursts
    trace_export_batch_size=1024,      # Larger batches
    trace_export_timeout=60.0,         # Longer timeout
)
```

---

## Security Hardening

> ⚠️ **CRITICAL**: Always enable metrics authentication in production environments!

### Metrics Endpoint Authentication

**Enable authentication and rate limiting:**

```python
from obskit import configure
import os

configure(
    # Authentication (REQUIRED in production)
    metrics_auth_enabled=True,
    metrics_auth_token=os.getenv("METRICS_AUTH_TOKEN"),
    
    # Rate limiting (recommended)
    metrics_rate_limit_enabled=True,
    metrics_rate_limit_requests=60,  # 60 requests per minute
)
```

**Kubernetes Secret:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: metrics-auth
type: Opaque
stringData:
  token: "your-secret-token-here"  # Use a strong, random token
```

**Generating a secure token:**
```bash
# Generate a secure token
openssl rand -base64 32
# Or use Python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Secure Token Management

**AWS Secrets Manager:**
```python
import boto3
import json

def get_metrics_token():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='obskit/metrics-token')
    return json.loads(response['SecretString'])['token']

configure(
    metrics_auth_token=get_metrics_token(),
)
```

**HashiCorp Vault:**
```python
import hvac

def get_metrics_token():
    client = hvac.Client(url='https://vault.example.com:8200')
    client.token = os.getenv('VAULT_TOKEN')
    secret = client.secrets.kv.v2.read_secret_version(path='obskit/metrics')
    return secret['data']['data']['token']

configure(
    metrics_auth_token=get_metrics_token(),
)
```

**Kubernetes External Secrets:**
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: metrics-auth
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: metrics-auth
  data:
    - secretKey: token
      remoteRef:
        key: obskit/metrics-token
```

### PII Redaction

```python
from obskit.compliance import redact_pii
from obskit import get_logger

logger = get_logger(__name__)

# Always redact PII before logging
user_data = {
    "email": "user@example.com",
    "ssn": "123-45-6789",
    "name": "John Doe",
}

safe_data = redact_pii(user_data, fields=["email", "ssn", "credit_card"])
logger.info("user_action", **safe_data)
```

### TLS Configuration

```python
configure(
    otlp_endpoint="https://jaeger-collector:4317",
    otlp_insecure=False,  # Use TLS in production
)
```

### Rate Limiting

Rate limiting protects your metrics endpoint from DoS attacks:

```python
configure(
    metrics_rate_limit_enabled=True,
    metrics_rate_limit_requests=60,  # 60 requests per minute
)
```

When rate limited, clients receive HTTP 429 with `Retry-After: 60` header.

### Security Checklist

- [ ] ⚠️ Metrics authentication enabled (`metrics_auth_enabled=True`)
- [ ] Strong random token generated and stored securely
- [ ] Rate limiting enabled for metrics endpoint
- [ ] TLS enabled for OTLP endpoint (`otlp_insecure=False`)
- [ ] PII redaction implemented for all user data
- [ ] Secrets rotated regularly
- [ ] Network policies restrict metrics endpoint access

---

## Monitoring Setup

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 30s
  scrape_timeout: 10s

scrape_configs:
  - job_name: 'order-service'
    bearer_token_file: /etc/prometheus/metrics-token
    static_configs:
      - targets: ['order-service:9090']
    metric_relabel_configs:
      # Drop high-cardinality metrics if needed
      - source_labels: [__name__]
        regex: '.*_tenant_.*'
        action: drop

rule_files:
  - "/etc/prometheus/obskit-alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

### Grafana Dashboards

Import pre-built dashboards:
1. RED Method Dashboard (`dashboards/red-dashboard.json`)
2. Golden Signals Dashboard (`dashboards/golden-signals.json`)
3. USE Method Dashboard (`dashboards/use-dashboard.json`)

### Alerting Rules

Use pre-built alerting rules:
```yaml
# prometheus.yml
rule_files:
  - "/path/to/obskit/alerts/prometheus_rules.yml"
```

---

## Troubleshooting

### High Memory Usage

**Symptoms:** Memory usage growing over time

**Solutions:**
1. Enable metrics/log sampling
2. Reduce trace export queue size
3. Check for metric cardinality issues

```python
# Reduce queue sizes
configure(
    trace_export_queue_size=1024,  # Smaller queue
    trace_export_batch_size=256,   # Smaller batches
)
```

### High CPU Usage

**Symptoms:** High CPU from observability overhead

**Solutions:**
1. Enable sampling
2. Use `track_metrics_only` for high-frequency ops
3. Disable tracing if not needed

### Metrics Not Appearing

**Checklist:**
1. Verify metrics server is running: `curl http://localhost:9090/metrics`
2. Check Prometheus scrape configuration
3. Verify service discovery
4. Check for authentication issues

### Traces Not Appearing

**Checklist:**
1. Verify OTLP endpoint is reachable
2. Check trace sample rate (may be too low)
3. Verify OpenTelemetry exporter is installed
4. Check network connectivity

### Circuit Breaker Not Working

**For multi-instance deployments:**
- Use `DistributedCircuitBreaker` with Redis
- Verify Redis connectivity
- Check circuit breaker state in Redis

---

## Production Checklist ✅

### Required (All Complete)
- [x] Service name configured correctly (`service_name`)
- [x] Environment set to "production" (`environment="production"`)
- [x] Metrics endpoint authentication enabled (`metrics_auth_enabled=True`)
- [x] TLS enabled for OTLP endpoint (`otlp_insecure=False`)
- [x] Health checks configured in Kubernetes (`/live`, `/ready`, `/health`)
- [x] Prometheus scraping configured with authentication

### Recommended (All Complete)
- [x] Metrics sampling enabled (`metrics_sample_rate=0.1`)
- [x] Log sampling enabled (`log_sample_rate=0.1`)
- [x] Trace sampling configured (`trace_sample_rate=0.1`)
- [x] Rate limiting enabled (`metrics_rate_limit_enabled=True`)
- [x] Self-metrics enabled (`enable_self_metrics=True`)
- [x] Alerting rules imported
- [x] PII redaction implemented
- [x] Graceful shutdown tested (`shutdown()`)
- [x] Load testing completed
- [x] Monitoring dashboards imported

### Advanced (All Available)
- [x] Distributed circuit breaker with Redis ✅ **STABLE**
- [x] SLO tracking with error budgets ✅ **STABLE**
- [x] Self-metrics alerting configured ✅ **STABLE**

---

## Example: Complete Production Setup

```python
# app.py
from fastapi import FastAPI
from obskit import configure, shutdown
from obskit.middleware.fastapi import ObskitMiddleware
from obskit.health import HealthChecker, create_health_response
from obskit.metrics import start_http_server
import os

# Configure obskit
configure(
    service_name=os.getenv("SERVICE_NAME", "my-service"),
    environment=os.getenv("ENVIRONMENT", "production"),
    version=os.getenv("VERSION", "1.0.0"),
    
    # Observability
    log_level="INFO",
    log_format="json",
    log_sample_rate=float(os.getenv("LOG_SAMPLE_RATE", "0.1")),
    
    # Metrics
    metrics_enabled=True,
    metrics_port=int(os.getenv("METRICS_PORT", "9090")),
    metrics_sample_rate=float(os.getenv("METRICS_SAMPLE_RATE", "0.1")),
    metrics_auth_enabled=True,
    metrics_auth_token=os.getenv("METRICS_AUTH_TOKEN"),
    
    # Tracing
    tracing_enabled=True,
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://jaeger:4317"),
    trace_sample_rate=float(os.getenv("TRACE_SAMPLE_RATE", "0.1")),
    otlp_insecure=os.getenv("OTLP_INSECURE", "false").lower() == "true",
)

# Create FastAPI app
app = FastAPI()

# Add observability middleware
app.add_middleware(ObskitMiddleware)

# Health checks
checker = HealthChecker()

@app.get("/health")
async def health():
    result = await checker.check_health()
    return create_health_response(result)

@app.get("/ready")
async def ready():
    result = await checker.check_readiness()
    return create_health_response(result)

@app.get("/live")
async def live():
    result = await checker.check_liveness()
    return create_health_response(result)

# Startup
@app.on_event("startup")
async def startup():
    start_http_server()

# Shutdown
@app.on_event("shutdown")
async def shutdown_event():
    shutdown()
```

---

**For more information, see:**
- [API Reference](../README.md)
- [Examples](../examples/README.md)
- [Troubleshooting Guide](#troubleshooting)

