# Security Guide

obskit handles telemetry data that often flows through production systems containing sensitive information. This guide covers PII protection, credential handling, authenticated endpoints, and supply-chain security practices enforced in the obskit CI pipeline.

---

## 1. PII Redaction in Logs and Traces

Never log raw request bodies or user identifiers without scrubbing them first. obskit provides a structured field-filtering API.

### Log Field Redaction

```python
from obskit.logging import get_logger

logger = get_logger(__name__)

# BAD — logs raw PII
logger.info("user login", email="alice@example.com", password="s3cr3t")

# GOOD — redact before logging
logger.info(
    "user login",
    email="ali***@example.com",   # partial mask
    user_id="usr_abc123",          # opaque identifier only
    # never include: password, card_number, ssn, dob
)
```

### Automatic PII Filtering with structlog Processors

Add a processor to your structlog pipeline that scrubs known sensitive field names before any renderer sees the event:

```python
import re
import structlog

_PII_FIELDS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "credit_card", "card_number", "cvv", "ssn",
    "national_id", "date_of_birth", "dob", "phone", "email",
    "ip_address", "ip",
})
_PII_PATTERN = re.compile(
    r"(\b(?:password|secret|token|card)[=:]\s*)\S+",
    re.IGNORECASE,
)

def redact_pii(logger, method, event_dict):
    """Structlog processor: redact sensitive fields in-place."""
    for key in list(event_dict.keys()):
        if key.lower() in _PII_FIELDS:
            event_dict[key] = "***REDACTED***"
    # Also scrub values that look like secrets in the event string
    if "event" in event_dict:
        event_dict["event"] = _PII_PATTERN.sub(r"\1***", event_dict["event"])
    return event_dict

structlog.configure(
    processors=[
        redact_pii,            # must be early in the chain
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
```

### Trace Attribute Filtering

OpenTelemetry spans can also carry PII via span attributes. Use a `SpanProcessor` to strip them before export:

```python
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

_SENSITIVE_SPAN_ATTRS = frozenset({
    "user.email", "user.phone", "http.request.body",
    "db.statement",   # may contain WHERE email = '...'
    "rpc.request.metadata.authorization",
})

class PIIStrippingSpanExporter(SpanExporter):
    """Wrap another exporter; strip PII attributes before forwarding."""

    def __init__(self, inner: SpanExporter) -> None:
        self._inner = inner

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            for attr in _SENSITIVE_SPAN_ATTRS:
                if attr in span.attributes:
                    # ReadableSpan attributes are immutable; shadow at dict level
                    span.attributes._dict.pop(attr, None)  # type: ignore[attr-defined]
        return self._inner.export(spans)

    def shutdown(self) -> None:
        self._inner.shutdown()
```

!!! tip "Use opaque identifiers"
    Prefer `user_id: "usr_abc123"` over `email: "alice@example.com"` in spans and log events. Opaque IDs are correlation keys that carry no PII.

---

## 2. OTLP Endpoint Authentication

### Bearer Token (HTTP OTLP)

When your collector or managed service (Grafana Cloud, Honeycomb, etc.) requires authentication:

```bash
# Set via environment variable — never hardcode
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer eyJhbGci..."
```

Or in Python at setup time:

```python
from obskit.tracing import setup_tracing

setup_tracing(
    service_name="order-service",
    otlp_endpoint="https://tempo.acme.com:443",
    headers={
        "Authorization": f"Bearer {os.environ['TEMPO_API_KEY']}",
    },
    insecure=False,
)
```

### mTLS (gRPC OTLP)

For full mutual TLS where both client and server present certificates:

```python
import grpc
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

credentials = grpc.ssl_channel_credentials(
    root_certificates=open("/certs/ca.pem", "rb").read(),
    private_key=open("/certs/client.key", "rb").read(),
    certificate_chain=open("/certs/client.crt", "rb").read(),
)

exporter = OTLPSpanExporter(
    endpoint="tempo-distributor.monitoring:4317",
    credentials=credentials,
    insecure=False,
)
```

In Kubernetes, mount the certificate files from a Secret:

```yaml
volumeMounts:
  - name: otlp-tls
    mountPath: /certs
    readOnly: true
volumes:
  - name: otlp-tls
    secret:
      secretName: otlp-client-tls
```

---

## 3. Metrics Endpoint Authentication

By default the `/metrics` endpoint is unauthenticated. In zero-trust environments, enable bearer token auth:

```bash
OBSKIT_METRICS_AUTH_ENABLED=true
OBSKIT_METRICS_AUTH_TOKEN=your-secret-scrape-token   # set via K8s Secret
```

The middleware checks the `Authorization: Bearer <token>` header on every scrape request and returns `401` if the token is absent or wrong.

For Prometheus to authenticate, configure it in `scrape_configs`:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: order-service
    bearer_token: "your-secret-scrape-token"
    static_configs:
      - targets: ["order-service-metrics:9090"]
```

Or in a `ServiceMonitor`:

```yaml
endpoints:
  - port: metrics
    bearerTokenSecret:
      name: order-service-obskit-secrets
      key: OBSKIT_METRICS_AUTH_TOKEN
```

---

## 4. Secret Management — Best Practices

| Practice | Do | Do Not |
|---|---|---|
| Store tokens | Kubernetes Secret, HashiCorp Vault, AWS Secrets Manager | `.env` committed to git, hardcoded in source |
| Rotate credentials | Automate rotation with Vault dynamic secrets | Set-and-forget long-lived tokens |
| Scope access | One secret per service, least-privilege | Shared token for all services |
| Audit access | Enable K8s audit log for Secret reads | Rely only on RBAC |
| Image secrets | Use IRSA / Workload Identity | `imagePullSecrets` with static credentials |

### HashiCorp Vault Integration

```python
import hvac
import os

def load_obskit_secrets_from_vault():
    """Load obskit secrets from Vault at startup."""
    client = hvac.Client(url=os.environ["VAULT_ADDR"])
    client.auth.kubernetes.login(
        role="order-service",
        jwt=open("/var/run/secrets/kubernetes.io/serviceaccount/token").read(),
    )
    secret = client.secrets.kv.v2.read_secret_version(
        path="order-service/obskit",
        mount_point="secret",
    )
    data = secret["data"]["data"]
    os.environ["OBSKIT_METRICS_AUTH_TOKEN"] = data["metrics_auth_token"]
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Bearer {data['tempo_token']}"
```

---

## 5. Dependency CVE Scanning (pip-audit)

obskit's CI runs `pip-audit` on every push and pull request to detect known vulnerabilities in Python dependencies:

```yaml
# .github/workflows/security.yml (excerpt)
- name: Audit dependencies for CVEs
  run: |
    pip install pip-audit
    pip-audit \
      --requirement requirements.txt \
      --format json \
      --output pip-audit-report.json
    pip-audit \
      --requirement requirements.txt \
      --strict        # Fail CI on any finding
```

Run locally before opening a PR:

```bash
pip install pip-audit
pip-audit --requirement requirements.txt
```

Fix vulnerabilities by upgrading the affected package:

```bash
pip-audit --requirement requirements.txt --fix
pip freeze > requirements.txt
```

---

## 6. Bandit Static Analysis

Bandit scans Python source code for common security anti-patterns (use of `exec`, `eval`, hardcoded passwords, `subprocess` with `shell=True`, etc.):

```yaml
# .github/workflows/security.yml (excerpt)
- name: Bandit static analysis
  run: |
    pip install bandit[toml]
    bandit \
      -r packages/ \
      -c pyproject.toml \
      --severity-level medium \
      --confidence-level medium \
      -f json \
      -o bandit-report.json
```

Configure bandit exclusions in `pyproject.toml`:

```toml
[tool.bandit]
exclude_dirs = ["tests", "benchmarks", "docs"]
skips = [
    "B101",   # assert — acceptable in test helpers
    "B311",   # random — we use secrets.token_hex for security, random only in sampling
]
```

Run locally:

```bash
pip install bandit[toml]
bandit -r packages/ -c pyproject.toml
```

---

## 7. SBOM Generation

obskit's release pipeline generates a **Software Bill of Materials** using `cyclonedx-bom`. The SBOM lists every Python dependency and its version, enabling downstream users to audit the supply chain:

```yaml
# .github/workflows/release.yml (excerpt)
- name: Generate SBOM
  run: |
    pip install cyclonedx-bom
    cyclonedx-py environment \
      --output-format json \
      --output-file sbom.json

- name: Upload SBOM to release
  uses: softprops/action-gh-release@v1
  with:
    files: sbom.json
```

The `sbom.json` is attached to every GitHub Release. Consumers can verify it with:

```bash
# Verify SBOM integrity using cosign
cosign verify-blob \
  --certificate sbom.json.cert \
  --signature sbom.json.sig \
  sbom.json
```

---

## 8. Sigstore Signing

obskit release artifacts (wheels, SBOMs) are signed using **Sigstore / cosign** via GitHub's OIDC token, providing keyless, verifiable provenance:

```yaml
# .github/workflows/release.yml (excerpt)
- name: Sign release artifact with Sigstore
  uses: sigstore/gh-action-sigstore-python@v2
  with:
    inputs: dist/*.whl dist/*.tar.gz sbom.json
```

Verify a downloaded wheel:

```bash
pip install sigstore
sigstore verify github \
  --cert-identity "https://github.com/talaatmagdyx/obskit/.github/workflows/release.yml@refs/tags/v2.1.0" \
  obskit-2.1.0-py3-none-any.whl
```

---

## 9. Network Policy (Zero-Trust)

Restrict which pods can reach the metrics and OTLP ports:

```yaml
# k8s/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: order-service-allow-scrape
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: order-service
  policyTypes:
    - Ingress
  ingress:
    # Allow Prometheus scraper
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
          podSelector:
            matchLabels:
              app: prometheus
      ports:
        - port: 9090
          protocol: TCP
    # Allow regular API traffic
    - from:
        - namespaceSelector: {}   # any namespace
      ports:
        - port: 8000
          protocol: TCP
```

---

## 10. Security Checklist

Use this checklist before every production deployment:

- [ ] `OBSKIT_OTLP_INSECURE=false` — TLS enabled for trace export
- [ ] `OBSKIT_METRICS_AUTH_ENABLED=true` — metrics endpoint protected
- [ ] `OBSKIT_METRICS_AUTH_TOKEN` sourced from Kubernetes Secret or Vault, not ConfigMap
- [ ] PII processor attached to structlog pipeline
- [ ] Span attribute allow-list configured (strip `db.statement`, `http.request.body`)
- [ ] `pip-audit` passes with no high-severity findings
- [ ] `bandit` passes with no medium-severity findings
- [ ] SBOM generated and attached to release
- [ ] Container image runs as non-root (`runAsNonRoot: true`)
- [ ] `readOnlyRootFilesystem: true` on all containers
- [ ] `allowPrivilegeEscalation: false` on all containers
- [ ] Network Policy restricts scrape access to Prometheus namespace only
- [ ] No secrets in `ConfigMap` — use `Secret` or Vault exclusively

---

!!! info "Audit logging for secret access"
    Enable Kubernetes audit logging to track every time a Secret is read. Pipe audit logs to your SIEM for alerting on unexpected access patterns.

    ```yaml
    # kube-apiserver audit policy (excerpt)
    rules:
      - level: Metadata
        resources:
          - group: ""
            resources: ["secrets"]
        verbs: ["get", "list", "watch"]
    ```

!!! tip "Rotate metrics auth tokens automatically"
    Use HashiCorp Vault's dynamic secrets engine to generate short-lived bearer tokens for Prometheus scraping. Configure Vault Agent to write the token to a Kubernetes Secret and restart Prometheus with a rolling update when the token rotates.

---

## Transport Security Summary

=== "Development"

    ```bash
    OBSKIT_OTLP_INSECURE=true     # no TLS — local collector
    OBSKIT_METRICS_AUTH_ENABLED=false
    ```

=== "Staging"

    ```bash
    OBSKIT_OTLP_INSECURE=false    # TLS required
    OBSKIT_METRICS_AUTH_ENABLED=true
    OBSKIT_METRICS_AUTH_TOKEN=staging-token   # from K8s Secret
    ```

=== "Production"

    ```bash
    OBSKIT_OTLP_INSECURE=false
    OBSKIT_METRICS_AUTH_ENABLED=true
    OBSKIT_METRICS_AUTH_TOKEN=<from-vault-or-k8s-secret>
    # Optionally: OTEL_EXPORTER_OTLP_CERTIFICATE=/certs/ca.pem  (mTLS)
    ```
