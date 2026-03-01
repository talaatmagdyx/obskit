# How to Trace Health Checks

When an OpenTelemetry span is active during a health check request,
`HealthResult.to_dict()` automatically includes `trace_id` and `span_id` in the
response payload.  This creates a direct link between a failing health check and the
exact trace in Grafana Tempo — so you can see *why* the check failed, not just *that*
it failed.

---

## What is health check tracing?

A health check is typically a lightweight HTTP endpoint (`/health` or `/healthz`) that
aggregates the status of several sub-checks (database connectivity, downstream service
reachability, SLO compliance, etc.).  When a check fails in production, you usually only
see a binary `degraded` / `unhealthy` status.

With health check tracing:

- Each call to `HealthChecker.check_health()` runs inside an OTel span.
- The span carries the full check execution as child spans.
- `HealthResult.to_dict()` embeds the `trace_id` of that span in the JSON response.
- Alertmanager or your on-call tooling can follow the `trace_id` link directly to the
  Tempo trace, showing exactly which sub-check failed, how long it took, and what error
  was raised.

---

## Requirements

| Package | Minimum version | Role |
|---------|-----------------|------|
| `obskit` | 2.2.0 | `HealthChecker`, `HealthResult`, built-in checks |
| `obskit[otlp]` | 2.2.0 | OTel span context injection |
| `opentelemetry-sdk` | 1.20.0 | Active span context |

---

## Installation

```bash
pip install "obskit[otlp]"
```

---

## Basic example: with and without tracing

=== "Without tracing"

    ```python
    import asyncio
    from obskit.health import HealthChecker

    checker = HealthChecker(service_name="order-service", version="2.0.0")
    result = asyncio.run(checker.check_health())
    print(result.to_dict())
    ```

    **Output**

    ```json
    {
      "status": "healthy",
      "healthy": true,
      "service": "order-service",
      "version": "2.0.0",
      "timestamp": "2026-02-28T10:00:00.000000+00:00",
      "checks": {}
    }
    ```

=== "With tracing"

    ```python
    import asyncio
    from obskit.health import HealthChecker
    from obskit.tracing import setup_tracing
    from opentelemetry import trace

    setup_tracing(service_name="order-service", exporter_endpoint="http://localhost:4317")
    tracer = trace.get_tracer("order_service")

    checker = HealthChecker(service_name="order-service", version="2.0.0")

    async def run():
        with tracer.start_as_current_span("health_check"):
            result = await checker.check_health()
            return result.to_dict()

    print(asyncio.run(run()))
    ```

    **Output**

    ```json
    {
      "status": "healthy",
      "healthy": true,
      "service": "order-service",
      "version": "2.0.0",
      "timestamp": "2026-02-28T10:00:00.000000+00:00",
      "checks": {},
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "span_id": "00f067aa0ba902b7"
    }
    ```

The `trace_id` field is only present when a valid OTel span is active.  When tracing is
not configured, the field is omitted silently — no errors, no warnings.

---

## FastAPI /health endpoint with trace context

The most common pattern is a FastAPI route that wraps the health check in a span so that
the `trace_id` is always included in the response:

```python
from fastapi import FastAPI
from obskit.health import HealthChecker, create_http_check
from obskit.middleware.fastapi import ObservabilityMiddleware
from obskit.tracing import setup_tracing
from opentelemetry import trace

setup_tracing(service_name="order-service", exporter_endpoint="http://localhost:4317")

app = FastAPI()
app.add_middleware(ObservabilityMiddleware, service_name="order-service")

tracer = trace.get_tracer("order_service")
checker = HealthChecker(service_name="order-service", version="2.0.0")

# Register checks
checker.add_check(
    "payments-api",
    create_http_check("https://payments.internal/health", timeout=2.0),
)


@app.get("/health")
async def health():
    # The ObservabilityMiddleware already started a span for this HTTP request,
    # so HealthResult.to_dict() will include trace_id automatically.
    result = await checker.check_health()
    status_code = 200 if result.healthy else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(content=result.to_dict(), status_code=status_code)
```

**Example healthy response:**

```json
{
  "status": "healthy",
  "healthy": true,
  "service": "order-service",
  "version": "2.0.0",
  "timestamp": "2026-02-28T10:00:00.000000+00:00",
  "checks": {
    "payments-api": {"status": "healthy", "latency_ms": 12}
  },
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

**Example degraded response (HTTP 503):**

```json
{
  "status": "degraded",
  "healthy": false,
  "service": "order-service",
  "version": "2.0.0",
  "timestamp": "2026-02-28T10:00:00.000000+00:00",
  "checks": {
    "payments-api": {
      "status": "unhealthy",
      "error": "Connection refused",
      "latency_ms": 2003
    }
  },
  "trace_id": "9a3fc1d2e4b50a17c83e2f9600b1d8e5",
  "span_id": "b3f8a1c200e40912"
}
```

The `trace_id` in the 503 response points directly to the Tempo trace that shows the
`payments-api` check timing out.

---

## SLO-based health check

You can add an SLO compliance check that marks the service as degraded when the error
budget is nearly exhausted:

```python
from obskit.health import HealthChecker
from obskit.health.slo_check import create_slo_health_check
from obskit.slo import SLOTracker

tracker = SLOTracker(
    name="order-success-rate",
    target=0.999,
    window_seconds=3600,
)

checker = HealthChecker(service_name="order-service", version="2.0.0")
checker.add_check(
    "slo-compliance",
    create_slo_health_check(tracker, degraded_threshold=0.10),  # 10 % budget remaining
)
```

When the SLO budget drops below 10 %, the health check returns `degraded` — and the
`trace_id` in the response points to the Tempo trace that shows the SLO tracker state
at the moment of the check.

---

## Kubernetes liveness and readiness probes

Health check tracing is especially useful for debugging flapping Kubernetes pods.
When a pod is restarted because the liveness probe returned non-200, you normally lose
the context of what failed.  With `trace_id` in the response, you can query Tempo for
the exact trace before the restart.

```yaml
# kubernetes/deployment.yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

When the probe fails, Kubernetes logs the HTTP response body.  Because the response
includes `trace_id`, you can go directly to:

```
http://localhost:3000/explore?orgId=1&left={"datasource":"Tempo","queries":[{"query":"<trace_id>"}]}
```

---

## Using trace_id in Alertmanager webhooks

Configure an Alertmanager receiver that captures the `trace_id` from the `/health`
response and includes it in the alert annotation:

```yaml
# alertmanager.yml
receivers:
  - name: "health-check-alerts"
    webhook_configs:
      - url: "http://alert-enricher.internal/enrich"
        send_resolved: true
        http_config:
          follow_redirects: true
```

In the `alert-enricher` service, when you receive a `HealthCheck` alert, call your
`/health` endpoint, extract `trace_id` from the JSON, and annotate the alert:

```python
import httpx

async def enrich_health_alert(alert: dict) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get("http://order-service.internal/health")
        body = response.json()
        trace_id = body.get("trace_id", "")

    if trace_id:
        alert["annotations"]["trace_url"] = (
            f"http://grafana.internal/explore?left="
            f'[%22now-1h%22,%22now%22,%22Tempo%22,{{"query":"{trace_id}"}}]'
        )
    return alert
```

The resulting alert in Slack / PagerDuty contains a direct Tempo link for the failing
health check.

---

## Grafana: annotating dashboards with health check events

Use Grafana Annotations to mark health degradation events on your service dashboards
with a link to the trace.

1. Create an **Annotation query** on your dashboard that queries Prometheus:

   ```promql
   changes(obskit_health_status{service="order-service"}[1m]) > 0
   ```

2. In the **Annotation** configuration, set the **Text** template to include the
   trace URL:

   ```
   Health check degraded — trace: http://tempo:3200/trace/${__field.labels.trace_id}
   ```

3. Each annotation marker on the dashboard timeline now carries a clickable trace link.

---

## Async health checks with context propagation

If your health check functions are async and spawn sub-tasks, the OTel context
propagates automatically through `asyncio` coroutines.  Each async check function
will therefore run within a child span of the main health check span:

```python
import asyncio
import httpx
from obskit.health import HealthChecker

async def check_redis(name: str) -> dict:
    """A custom async check that tests Redis connectivity."""
    try:
        import aioredis
        redis = await aioredis.from_url("redis://localhost:6379")
        await redis.ping()
        await redis.close()
        return {"status": "healthy"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


async def check_downstream_api(name: str) -> dict:
    """A custom async check for a downstream HTTP dependency."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get("https://payments.internal/ping")
            resp.raise_for_status()
        return {"status": "healthy"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


checker = HealthChecker(service_name="order-service", version="2.0.0")
checker.add_check("redis", check_redis)
checker.add_check("payments-api", check_downstream_api)

# All async checks run concurrently, each inheriting the OTel span context.
result = asyncio.run(checker.check_health())
```

!!! note "Concurrent checks and trace context"
    `HealthChecker.check_health()` runs all registered checks concurrently with
    `asyncio.gather()`.  Each check coroutine inherits the active OTel span context
    via `contextvars`, so all checks appear as sibling child spans in the Tempo trace
    view.

---

## Troubleshooting

### "trace_id is missing from /health response"

1. **Is `obskit[otlp]` installed?**

   ```bash
   python -m obskit.core.diagnose
   ```

2. **Is a span active during the health check?**

   The `ObservabilityMiddleware` creates a span for every incoming HTTP request,
   including `GET /health`.  If you are not using the middleware, wrap the
   `check_health()` call in a manual span:

   ```python
   with tracer.start_as_current_span("health_check"):
       result = await checker.check_health()
   ```

3. **Is `setup_tracing()` called at application startup?**

   The OTel `TracerProvider` must be initialised before the first request is served.

### "Health check always shows trace_id=000000... (all zeros)"

The OTel SDK is installed but no exporter is configured, so spans use a no-op provider
that generates an invalid (all-zeros) trace context.  Pass a valid `exporter_endpoint`
to `setup_tracing()`.

### "Kubernetes probe response body does not contain trace_id"

Kubernetes does not log the HTTP response body by default for probes.  To capture it,
use a `lifecycle.postStart` or `preStop` hook script that calls the health endpoint,
or configure your application to write health check results to a file that Kubernetes
can retrieve with `kubectl exec`.

---

## Summary

| Step | Action |
|------|--------|
| Install | `pip install "obskit[otlp]"` |
| Initialise | Call `setup_tracing()` at startup |
| Middleware | Add `ObservabilityMiddleware` to wrap requests in spans |
| Endpoint | Return `result.to_dict()` from your `/health` route |
| Verify | `trace_id` appears in the JSON response body |
| Grafana | Follow `trace_id` link to Tempo for degraded checks |
