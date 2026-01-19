# Security Guide

Complete guide to securing obskit in production.

---

## Security Checklist

| Feature | Required | Status |
|---------|----------|--------|
| Metrics Authentication | ✅ Yes | Enable in production |
| Rate Limiting | ✅ Yes | Prevent DoS |
| TLS for OTLP | ✅ Yes | Encrypt traces |
| PII Redaction | ⚠️ If needed | Compliance |
| Secret Management | ✅ Yes | Secure tokens |

---

## Metrics Authentication

### Enable Authentication

```python
from obskit import configure
import os

configure(
    metrics_auth_enabled=True,
    metrics_auth_token=os.getenv("METRICS_AUTH_TOKEN"),
)
```

### Generate Secure Token

```bash
# OpenSSL
openssl rand -base64 32

# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Output: kJ9xWz3mNp7qRs2vTu5yAb4cDe6fGh8i
```

### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'my-service'
    bearer_token: "kJ9xWz3mNp7qRs2vTu5yAb4cDe6fGh8i"
    static_configs:
      - targets: ['my-service:9090']
```

Or with token file:

```yaml
scrape_configs:
  - job_name: 'my-service'
    bearer_token_file: /etc/prometheus/tokens/my-service.token
    static_configs:
      - targets: ['my-service:9090']
```

### Test Authentication

```bash
# Without token - should fail
curl http://localhost:9090/metrics
# Response: 401 Unauthorized

# With token - should succeed
curl -H "Authorization: Bearer $METRICS_AUTH_TOKEN" http://localhost:9090/metrics
# Response: 200 OK with metrics
```

---

## Rate Limiting

### Enable Rate Limiting

```python
configure(
    metrics_rate_limit_enabled=True,
    metrics_rate_limit_requests=60,  # 60 requests per minute
)
```

### Rate Limit Response

When rate limited:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
Content-Type: text/plain

Too Many Requests: Rate limit exceeded
```

### Custom Rate Limit

```python
configure(
    metrics_rate_limit_requests=100,  # 100 per minute
)
```

---

## TLS Configuration

### OTLP with TLS

```python
configure(
    otlp_endpoint="https://jaeger.example.com:4317",
    otlp_insecure=False,  # Use TLS
)
```

### Kubernetes with TLS

```yaml
env:
- name: OBSKIT_OTLP_ENDPOINT
  value: "https://jaeger-collector:4317"
- name: OBSKIT_OTLP_INSECURE
  value: "false"
```

---

## Secret Management

### Environment Variables

```bash
# Set in shell
export METRICS_AUTH_TOKEN="your-secure-token"

# In systemd
[Service]
Environment="METRICS_AUTH_TOKEN=your-secure-token"
```

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: obskit-secrets
type: Opaque
stringData:
  metrics-token: "your-secure-token"
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: METRICS_AUTH_TOKEN
          valueFrom:
            secretKeyRef:
              name: obskit-secrets
              key: metrics-token
```

### AWS Secrets Manager

```python
import boto3
import json

def get_secrets():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='obskit/production')
    secrets = json.loads(response['SecretString'])
    return secrets

secrets = get_secrets()
configure(
    metrics_auth_token=secrets['metrics_token'],
)
```

### HashiCorp Vault

```python
import hvac
import os

def get_secrets():
    client = hvac.Client(url=os.getenv('VAULT_URL'))
    client.token = os.getenv('VAULT_TOKEN')
    secret = client.secrets.kv.v2.read_secret_version(path='obskit/production')
    return secret['data']['data']

secrets = get_secrets()
configure(
    metrics_auth_token=secrets['metrics_token'],
)
```

### Kubernetes External Secrets

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: obskit-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: obskit-secrets
  data:
  - secretKey: metrics-token
    remoteRef:
      key: obskit/production
      property: metrics_token
```

---

## PII Redaction

### Basic Redaction

```python
from obskit.compliance import redact_pii

user_data = {
    "email": "john@example.com",
    "ssn": "123-45-6789",
    "credit_card": "4111-1111-1111-1111",
    "name": "John Doe",
}

# Redact specific fields
safe_data = redact_pii(user_data, fields=["email", "ssn", "credit_card"])
# {"email": "[REDACTED]", "ssn": "[REDACTED]", "credit_card": "[REDACTED]", "name": "John Doe"}
```

### Auto-Detection

```python
# Auto-detect PII patterns
safe_data = redact_pii(user_data)
# Automatically detects email, SSN, credit card patterns
```

### In Logging

```python
from obskit import get_logger
from obskit.compliance import redact_pii

logger = get_logger(__name__)

def process_user(user_data: dict):
    # Always redact before logging
    safe_data = redact_pii(user_data)
    logger.info("processing_user", **safe_data)
```

### Custom Patterns

```python
# Add custom patterns
from obskit.compliance.pii import PII_PATTERNS

PII_PATTERNS["employee_id"] = r"EMP-\d{6}"

# Now auto-detection includes employee IDs
safe_data = redact_pii({"employee_id": "EMP-123456"})
```

---

## Network Security

### Kubernetes Network Policy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: obskit-metrics-policy
spec:
  podSelector:
    matchLabels:
      app: my-service
  policyTypes:
  - Ingress
  ingress:
  # Allow Prometheus to scrape metrics
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
      podSelector:
        matchLabels:
          app: prometheus
    ports:
    - protocol: TCP
      port: 9090
```

### Service Mesh (Istio)

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: metrics-authz
spec:
  selector:
    matchLabels:
      app: my-service
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/monitoring/sa/prometheus"]
    to:
    - operation:
        ports: ["9090"]
```

---

## Security Headers

obskit automatically adds security headers to metrics endpoint:

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Cache-Control: no-cache, no-store, must-revalidate
```

---

## Audit Logging

Enable logging for security events:

```python
configure(
    log_level="INFO",
    log_format="json",
)

# Security events are logged
# {"event": "metrics_auth_failed", "remote_addr": "10.0.0.1", ...}
# {"event": "rate_limit_exceeded", "remote_addr": "10.0.0.1", ...}
```

---

## Security Scanning

### Run Security Scans

```bash
# Install security tools
pip install obskit[security]

# Vulnerability scanning
safety check

# Dependency audit
pip-audit

# Security linting
bandit -r src/obskit/
```

### CI/CD Integration

```yaml
# .github/workflows/security.yml
name: Security Scan
on: [push, pull_request]
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    - run: pip install obskit[security]
    - run: safety check
    - run: pip-audit
    - run: bandit -r src/obskit/
```

---

## Best Practices

### 1. Always Enable Auth in Production

```python
# ❌ BAD
configure(metrics_auth_enabled=False)

# ✅ GOOD
configure(
    metrics_auth_enabled=True,
    metrics_auth_token=os.getenv("METRICS_AUTH_TOKEN"),
)
```

### 2. Use Strong Tokens

```python
# ❌ BAD
configure(metrics_auth_token="password123")

# ✅ GOOD
configure(metrics_auth_token=secrets.token_urlsafe(32))
```

### 3. Rotate Secrets Regularly

```python
# Use external secret management with rotation
# AWS Secrets Manager, HashiCorp Vault, etc.
```

### 4. Limit Network Access

```yaml
# ❌ BAD - Metrics exposed to internet
kind: Service
spec:
  type: LoadBalancer
  ports:
  - port: 9090

# ✅ GOOD - Internal only
kind: Service
spec:
  type: ClusterIP
  ports:
  - port: 9090
```

### 5. Monitor Security Events

```promql
# Auth failures
rate(obskit_auth_failures_total[5m])

# Rate limit hits
rate(obskit_rate_limit_exceeded_total[5m])
```

---

## Compliance Checklist

| Requirement | obskit Feature |
|-------------|----------------|
| GDPR - Data minimization | PII redaction |
| SOC2 - Access control | Metrics auth |
| HIPAA - Audit logging | Structured logs |
| PCI-DSS - Encryption | TLS support |
| ISO 27001 - Security controls | Rate limiting |
