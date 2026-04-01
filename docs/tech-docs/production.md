# Production Readiness Checklist

Use this checklist before every production deployment of a service instrumented with obskit v1.0.0. Each section maps to a specific obskit package and the decisions you must make before going live.

---

## 1. Configuration

- [ ] `OBSKIT_SERVICE_NAME` set to a meaningful, unique name (not `"unknown"`)
- [ ] `OBSKIT_ENVIRONMENT=production` set explicitly
- [ ] `OBSKIT_VERSION` injected from CI/CD (git tag or image tag)
- [ ] `configure_observability()` (v1.0.0+) or `configure()` called **before** any other obskit import
- [ ] Configuration validated at startup; fails fast if invalid
- [ ] No secrets in ConfigMaps — all sensitive values in Kubernetes Secrets or Vault
- [ ] `.env` file excluded from Docker image (`COPY` excludes it or `.dockerignore` entry)

```python
# main.py — configuration at the top, before other obskit imports
import os
from obskit import configure_observability

# v1.0.0+: single call configures logging, tracing, and metrics
obs = configure_observability(
    service_name=os.environ["SERVICE_NAME"],
    environment=os.environ["DEPLOY_ENV"],
    version=os.environ["APP_VERSION"],
)

# Legacy approach (still supported):
# from obskit import configure
# from obskit.config import validate_config
# configure(service_name=..., environment=..., version=...)
# is_valid, errors = validate_config()
```

---

## 2. Logging

- [ ] `OBSKIT_LOG_FORMAT=json` — structured JSON for all production deployments
- [ ] `OBSKIT_LOG_LEVEL=INFO` — avoid `DEBUG` in production (high volume, potential PII leakage)
- [ ] `OBSKIT_LOG_INCLUDE_TIMESTAMP=true` unless your log aggregator adds its own
- [x] PII scrubbing — **automatic** — the default `get_logger()` pipeline includes `make_redaction_processor()` which redacts `password`, `token`, `secret`, `api_key`, `authorization`, `card_number`, and 15+ other sensitive field names before any output is written. No setup required.
- [ ] Log sampling rate set (`OBSKIT_LOG_SAMPLE_RATE`) for high-frequency paths
- [ ] Log aggregator (Loki, Elasticsearch) confirmed to parse the JSON format
- [ ] Correlation fields (`trace_id`, `span_id`) appear in log events from traced requests

```python
from obskit import configure_observability

obs = configure_observability(service_name="my-service", log_format="json")

# Verify trace injection works
log = obs.logger
log.info("startup complete", phase="init")
# JSON output should include: trace_id, span_id, service, environment, version
```

!!! warning "OTLP log export"
    Use `configure_otlp_logging()` for sending structured logs to an OTLP collector. The `OTLPLogHandler` class is a Python `logging.Handler` adapter that also exports via the same OTel pipeline when added to `logging.getLogger()`.

---

## 3. Metrics

- [ ] `OBSKIT_METRICS_ENABLED=true`
- [ ] `OBSKIT_METRICS_PORT=9090` accessible to Prometheus (NetworkPolicy allows scraping)
- [ ] `OBSKIT_METRICS_METHOD=red` (or `golden` / `all` based on team agreement)
- [ ] Histogram buckets reviewed — default covers 1 ms – 10 s; widen if your p99 exceeds 10 s
- [ ] Cardinality guard installed with bounded label values
- [ ] No user IDs, emails, or high-cardinality values in metric labels
- [ ] `OBSKIT_METRICS_AUTH_ENABLED=true` with token stored in Secret
- [ ] Prometheus ServiceMonitor or scrape_config validated (`targets` shows UP)
- [ ] Self-metrics enabled (`OBSKIT_ENABLE_SELF_METRICS=true`) to monitor obskit queue depth

```python
from obskit.metrics.cardinality import CardinalityGuard

CardinalityGuard(
    max_series=10_000,
    label_bounds={
        "http_method":   {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"},
        "http_status":   {"200", "201", "204", "400", "401", "403", "404",
                          "422", "429", "500", "502", "503", "504"},
        "environment":   {"production", "staging", "development"},
    },
).install()
```

---

## 4. Tracing

- [ ] `OBSKIT_TRACING_ENABLED=true`
- [ ] `OBSKIT_OTLP_ENDPOINT` points to a reachable collector (Tempo, Jaeger, Collector)
- [ ] `OBSKIT_OTLP_INSECURE=false` — TLS enforced in production
- [ ] Sample rate configured for traffic volume (see sampling strategy below)
- [ ] `configure_observability()` (or legacy `setup_tracing()`) called before any request handler runs
- [ ] W3C `traceparent` header propagated through all HTTP calls (verify with curl)
- [ ] Span attributes do not contain PII (db.statement sanitised, request body excluded)
- [ ] Tempo / Jaeger UI shows complete traces end-to-end

---

## 5. Health Checks

- [ ] `/health/live` — liveness probe returns 200 (simple alive check)
- [ ] `/health/ready` — readiness probe checks all critical dependencies
- [ ] `/health/startup` — startup probe used with `failureThreshold=30`, `periodSeconds=3`
- [ ] All critical dependencies (DB, Redis, external APIs) registered as health checks
- [ ] `OBSKIT_HEALTH_CHECK_TIMEOUT` set lower than Kubernetes probe `timeoutSeconds`
- [ ] Readiness returns 503 when any critical check is unhealthy
- [ ] Non-critical checks (e.g., analytics service) marked as `warning` not `critical`

```python
from obskit.health import HealthChecker
from obskit.health.checks import DatabaseCheck, RedisCheck, HTTPCheck

checker = HealthChecker()
checker.add_check(DatabaseCheck("postgres", db_url, timeout=3.0, critical=True))
checker.add_check(RedisCheck("redis", redis_url, timeout=2.0, critical=True))
checker.add_check(HTTPCheck("payment-api", "https://api.payments.com/health",
                             timeout=5.0, critical=False))  # non-critical
```

---

## 6. External Calls

- [ ] Timeout set on every HTTP client call (never use default unlimited timeout)
- [ ] Retry logic implemented for idempotent operations
- [ ] Fallback responses defined for dependency failures

```python
import httpx
from obskit.logging import get_logger

log = get_logger(__name__)

async def charge_card(amount: float) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post("https://payments.acme.com/charge", json={"amount": amount})
        resp.raise_for_status()
        return resp.json()
```

---

## 7. SLO Definitions

Define SLOs before going live so you have a baseline from day one:

- [ ] Error rate SLO defined (e.g., 99.9 % of requests succeed)
- [ ] Latency SLO defined (e.g., p99 < 500 ms)
- [ ] SLO burn rate alerts configured in Alertmanager
- [ ] Error budget dashboard available in Grafana

```python
from obskit.slo import SLOTracker

slo = SLOTracker(
    name="order-service-availability",
    target=0.999,   # 99.9 %
    window_days=30,
)
```

---

## Sampling Strategy for High-Traffic Services

Choosing the right sample rate avoids two failure modes:

- **Too high** (1.0 in production): overwhelms the collector and storage; drives up cost
- **Too low** (0.001): you miss tail-latency issues and rare errors

### Recommended rates by request volume

| Requests / second | Recommended `OBSKIT_TRACE_SAMPLE_RATE` | Effective traces / hour |
|---|---|---|
| < 10 | `1.0` (100 %) | up to 36 000 |
| 10 – 100 | `0.1` (10 %) | up to 36 000 |
| 100 – 1 000 | `0.01` (1 %) | up to 36 000 |
| > 1 000 | `0.001` – `0.01` | calibrate to storage budget |

### Tail-based sampling

For critical services where you want 100 % of errors captured regardless of rate, use tail-based sampling in the OpenTelemetry Collector:

```yaml
# otel-collector-config.yaml
processors:
  tail_sampling:
    decision_wait: 10s
    num_traces: 100_000
    policies:
      # Always sample errors
      - name: error-traces
        type: status_code
        status_code:
          status_codes: [ERROR]
      # Always sample slow requests
      - name: slow-traces
        type: latency
        latency:
          threshold_ms: 1000
      # Sample 1% of everything else
      - name: base-rate
        type: probabilistic
        probabilistic:
          sampling_percentage: 1
```

---

## Cardinality Limits

Prometheus stores one time series per unique label-value combination. Keep cardinality under control:

| Metric type | Max recommended series | Action if exceeded |
|---|---|---|
| Per-endpoint latency | 200 (10 routes × 5 methods × 4 status buckets) | Aggregate similar routes |
| Per-user metrics | Never | Use per-plan / per-tier instead |
| Per-tenant metrics | 1 000 | Use `CardinalityGuard` with allow-list |
| Background job metrics | 50 | One metric per job type, not per instance |

### Cardinality alert rule

```yaml
# prometheus-rules.yaml
groups:
  - name: obskit-cardinality
    rules:
      - alert: MetricsCardinalityHigh
        expr: |
          count by (metric_name) (
            label_replace(
              {__name__=~".*"},
              "metric_name", "$1", "__name__", "(.*)"
            )
          ) > 5000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High cardinality metric: {{ $labels.metric_name }}"
          description: "{{ $value }} series — investigate label values"
```

---

## Circuit Breaker Tuning

| Parameter | Conservative | Balanced | Aggressive |
|---|---|---|---|
| `failure_threshold` | 10 | 5 | 3 |
| `recovery_timeout` | 60 s | 30 s | 10 s |
| `half_open_requests` | 5 | 3 | 1 |

**Conservative**: Use for dependencies that are slow to recover (databases, third-party APIs with rate limits).

**Balanced**: Default; suitable for most internal microservice calls.

**Aggressive**: Use for low-latency dependencies where fast failure detection is critical (caches).

---

## Memory and CPU Considerations

| Component | Memory impact | CPU impact | Mitigation |
|---|---|---|---|
| Prometheus histograms | ~1 KB per series | Negligible | Use cardinality guard |
| Trace export queue | 2048 × ~2 KB = ~4 MB | Low (background goroutine-equivalent) | Tune `OBSKIT_TRACE_EXPORT_QUEUE_SIZE` |
| Async metric queue | 10 000 × ~0.5 KB = ~5 MB | Low | Reduce if memory-constrained |
| structlog JSON renderer | Negligible | ~4 µs per log event | Use log sampling at high volume |

---

## Graceful Shutdown

obskit registers shutdown hooks automatically when you call `configure_observability()` (or the legacy `setup_tracing()` and `start_metrics_server()`). For custom cleanup:

```python
import signal
import asyncio
from obskit.shutdown import ShutdownManager

manager = ShutdownManager()

@manager.on_shutdown
async def flush_traces():
    """Ensure all pending spans are exported before process exits."""
    from opentelemetry import trace
    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush(timeout_millis=5000)

@manager.on_shutdown
async def flush_metrics():
    """Final metrics push."""
    # Prometheus scrape will happen naturally; nothing to flush
    pass

# Register SIGTERM handler (Kubernetes sends SIGTERM before SIGKILL)
def handle_sigterm(signum, frame):
    asyncio.create_task(manager.shutdown())

signal.signal(signal.SIGTERM, handle_sigterm)
```

In Kubernetes, always set `terminationGracePeriodSeconds` to at least 30 seconds so in-flight traces have time to export:

```yaml
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 60
      containers:
        - lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 10"]
```

---

## Rollback Procedure

If a deployment causes metric or tracing anomalies:

```bash
# 1. Rollback the deployment
kubectl rollout undo deployment/order-service -n production

# 2. Verify rollback is complete
kubectl rollout status deployment/order-service -n production

# 3. Check that old version metrics are flowing
curl -s http://localhost:9090/metrics | grep 'service_version'

# 4. Verify health checks recover
kubectl get pods -n production -l app=order-service
# All pods should show 2/2 Running with READY state

# 5. Confirm Grafana dashboards return to baseline
# Check: error rate, p99 latency, SLO burn rate
```

---

## Alerting Setup

Minimum alert set before going live:

```yaml
# prometheus-rules.yaml
groups:
  - name: obskit-production
    rules:

      # Service availability — SLO breach
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          /
          sum(rate(http_requests_total[5m])) > 0.01
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Error rate > 1 % for 2 minutes"

      # Latency — p99 SLO breach
      - alert: HighLatencyP99
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
          ) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "p99 latency > 500 ms"

      # Health check failure
      - alert: ServiceUnhealthy
        expr: up{job="order-service"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service health check failing"

      # SLO burn rate high
      - alert: SLOBurnRateHigh
        expr: |
          slo_error_budget_remaining{service="order-service"} < 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "SLO error budget below 10% for {{ $labels.service }}"
```

---

## Dashboard Templates

Import the following obskit Grafana dashboard templates before go-live:

| Dashboard | Purpose | UID |
|---|---|---|
| obskit — RED Metrics | Request rate, error rate, duration per endpoint | `obskit-red` |
| obskit — SLO Burn Rate | Error budget consumption over 30-day window | `obskit-slo` |
| obskit — Circuit Breakers | State transitions, failure counts | `obskit-cb` |
| obskit — Health Overview | All health check statuses across services | `obskit-health` |
| obskit — Self-Metrics | obskit queue depth, export latency | `obskit-self` |

Grafana dashboard JSON files are located in the `dashboards/` directory of the obskit repository.

---

!!! success "You are production-ready when..."
    Every item in sections 1–7 above is checked. Dashboards are imported, alerts are configured, and at least one full end-to-end trace is visible in Grafana Tempo before your first real user request.

!!! warning "Common production anti-patterns"
    - Deploying with `OBSKIT_ENVIRONMENT=development` — alerts may be silenced for non-production environments
    - Setting `OBSKIT_TRACE_SAMPLE_RATE=1.0` with > 100 req/s — this will overwhelm the collector
    - Using `log_format=console` in production — Loki cannot parse human-readable output
    - Hardcoding `OBSKIT_METRICS_AUTH_TOKEN` in the Deployment manifest — it will appear in `kubectl describe`

!!! tip "Automate this checklist"
    Add the configuration validation call to your CI pipeline smoke test:

    ```python
    # tests/smoke/test_production_config.py
    import os, pytest

    @pytest.mark.skipif(
        os.getenv("OBSKIT_ENVIRONMENT") != "production",
        reason="Production config check only"
    )
    def test_production_config_valid():
        from obskit.config import validate_config
        is_valid, errors = validate_config()
        assert is_valid, f"Production config errors: {errors}"
    ```

---

## Environment-specific Configuration Summary

=== "Development"

    ```bash
    OBSKIT_ENVIRONMENT=development
    OBSKIT_LOG_FORMAT=console       # readable in terminal
    OBSKIT_LOG_LEVEL=DEBUG
    OBSKIT_TRACE_SAMPLE_RATE=1.0    # capture everything
    OBSKIT_OTLP_INSECURE=true
    OBSKIT_METRICS_AUTH_ENABLED=false
    ```

=== "Staging"

    ```bash
    OBSKIT_ENVIRONMENT=staging
    OBSKIT_LOG_FORMAT=json
    OBSKIT_LOG_LEVEL=INFO
    OBSKIT_TRACE_SAMPLE_RATE=0.5    # 50 % — find issues before prod
    OBSKIT_OTLP_INSECURE=false
    OBSKIT_METRICS_AUTH_ENABLED=true
    ```

=== "Production"

    ```bash
    OBSKIT_ENVIRONMENT=production
    OBSKIT_LOG_FORMAT=json
    OBSKIT_LOG_LEVEL=INFO
    OBSKIT_TRACE_SAMPLE_RATE=0.1    # tune per traffic volume
    OBSKIT_OTLP_INSECURE=false
    OBSKIT_METRICS_AUTH_ENABLED=true
    OBSKIT_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
    OBSKIT_RETRY_MAX_ATTEMPTS=3
    ```
