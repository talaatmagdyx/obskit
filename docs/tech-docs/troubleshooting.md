# Troubleshooting Guide

Use this guide to diagnose and fix the most common obskit issues in development and production.

---

## Quick Symptom → Fix Table

| Symptom | Most Likely Cause | Quick Fix |
|---|---|---|
| No traces in Grafana Tempo | Wrong OTLP endpoint or port | Verify `OBSKIT_OTLP_ENDPOINT` and network connectivity |
| Metrics not scraped by Prometheus | Wrong port or path | Confirm `OBSKIT_METRICS_PORT=9090` and Prometheus `targets` |
| Health check always unhealthy | Dependency check timeout | Increase `OBSKIT_HEALTH_CHECK_TIMEOUT` or fix the failing dependency |
| No `trace_id` in log events | Tracing not initialised before logging | Call `setup_tracing()` before creating any logger |
| `ImportError: obskit.tracing` | Package not installed | `pip install "obskit[otlp]"` |
| High memory from metrics | Cardinality explosion | Bound label values; see cardinality section |
| Circuit breaker opens immediately | Failure threshold too low or external service down | Raise threshold or fix the downstream service |
| Spans missing in production | Sample rate too low | Increase `OBSKIT_TRACE_SAMPLE_RATE` temporarily |
| `configure()` call ignored | Called after first `get_settings()` | Call `configure()` before any obskit import |
| Logs in JSON but timestamps wrong | Log aggregator double-stamping | Set `OBSKIT_LOG_INCLUDE_TIMESTAMP=false` |

---

## Issue: No Traces Appearing in Grafana Tempo

### Diagnosis steps

```bash
# 1. Verify OTLP endpoint resolves and port is open
python - <<'EOF'
import socket
host, port = "tempo", 4317
try:
    socket.setdefaulttimeout(3)
    socket.socket().connect((host, port))
    print(f"OK: {host}:{port} is reachable")
except Exception as e:
    print(f"FAIL: {e}")
EOF

# 2. Check obskit diagnostic output
python -m obskit.core.diagnose

# 3. Enable debug mode to print spans to stdout
```

```python
from obskit.tracing import setup_tracing

setup_tracing(
    service_name="order-service",
    debug=True,   # prints every span to stdout — never use in production
)
```

Sample debug output:

```
[obskit] Span: POST /orders
  trace_id = 4bf92f3577b34da6a3ce929d0e0e4736
  span_id  = 00f067aa0ba902b7
  duration = 42.3 ms
  status   = OK
  attributes:
    http.method = POST
    http.route  = /orders
    http.status_code = 201
```

### Common causes and fixes

=== "Wrong OTLP endpoint"

    ```bash
    # Wrong
    OBSKIT_OTLP_ENDPOINT=http://tempo:3200   # 3200 is Tempo HTTP API, not OTLP
    OBSKIT_OTLP_ENDPOINT=http://tempo:9411   # 9411 is Zipkin format

    # Correct
    OBSKIT_OTLP_ENDPOINT=http://tempo:4317   # OTLP gRPC port
    ```

=== "TLS mismatch"

    ```bash
    # If Tempo uses TLS but insecure flag is set
    OBSKIT_OTLP_INSECURE=true   # WRONG for TLS endpoint
    OBSKIT_OTLP_INSECURE=false  # correct for https/TLS endpoint
    ```

=== "Sampling drops all traces"

    ```bash
    # Check your sample rate
    OBSKIT_TRACE_SAMPLE_RATE=0.0  # drops 100% — nothing goes through
    OBSKIT_TRACE_SAMPLE_RATE=1.0  # sample everything (dev/debug)
    ```

=== "setup_tracing() not called"

    ```python
    # WRONG — tracing is never initialised
    from obskit.logging import get_logger
    logger = get_logger(__name__)

    # CORRECT — call setup_tracing() at application startup
    from obskit.tracing import setup_tracing
    setup_tracing(service_name="order-service")  # must be before any logging

    from obskit.logging import get_logger
    logger = get_logger(__name__)
    ```

---

## Issue: Metrics Not Scraped by Prometheus

### Diagnosis steps

```bash
# 1. Confirm the metrics endpoint is up
curl -s http://localhost:9090/metrics | head -10

# 2. Check Prometheus targets page
open http://localhost:9091/targets   # substitute your Prometheus URL

# 3. Verify Prometheus config
cat prometheus.yml | grep -A 5 "order-service"
```

### Common causes and fixes

=== "Port mismatch"

    ```yaml
    # prometheus.yml — wrong port
    scrape_configs:
      - job_name: order-service
        static_configs:
          - targets: ["order-service:8000"]   # API port, not metrics

    # Correct — use the metrics port
    scrape_configs:
      - job_name: order-service
        static_configs:
          - targets: ["order-service:9090"]   # OBSKIT_METRICS_PORT
    ```

=== "Metrics server not started"

    If you use FastAPI with `ObservabilityMiddleware`, the metrics server on port 9090 starts automatically. For standalone scripts, you must start it manually:

    ```python
    from obskit.metrics import start_metrics_server
    from obskit.config import configure

    configure(service_name="my-service", metrics_port=9090)
    start_metrics_server()   # opens port 9090 in background thread
    ```

=== "Auth token not sent by Prometheus"

    ```yaml
    # prometheus.yml — add bearer_token when OBSKIT_METRICS_AUTH_ENABLED=true
    scrape_configs:
      - job_name: order-service
        bearer_token: "your-secret-token"
        static_configs:
          - targets: ["order-service:9090"]
    ```

=== "ServiceMonitor label mismatch"

    ```bash
    # Check that ServiceMonitor label matches Prometheus operator selector
    kubectl get prometheus -n monitoring -o yaml | grep serviceMonitorSelector -A 5
    # The label on your ServiceMonitor must match this selector
    ```

---

## Issue: Health Check Always Returns Unhealthy

### Diagnosis steps

```bash
# 1. Call health endpoint directly
curl -s http://localhost:8001/health/ready | python -m json.tool

# 2. Look at which specific check is failing
curl -s http://localhost:8001/health/ready | python -c "
import sys, json
data = json.load(sys.stdin)
for check, result in data.get('checks', {}).items():
    status = result.get('status', '?')
    msg    = result.get('message', '')
    print(f'  {status:10} {check}: {msg}')
"
```

### Common causes and fixes

=== "Database unreachable"

    ```python
    from obskit.health import HealthChecker
    from obskit.health.checks import DatabaseCheck

    checker = HealthChecker()
    checker.add_check(DatabaseCheck(
        name="postgres",
        connection_string="postgresql://user:pass@localhost:5432/mydb",
        timeout=5.0,   # increase if DB is slow to respond
    ))
    ```

    Check your connection string and that the DB container is in the same Docker network.

=== "Timeout too short"

    ```bash
    # Increase health check timeout
    OBSKIT_HEALTH_CHECK_TIMEOUT=10.0   # default is 5.0 seconds
    ```

=== "Redis check fails intermittently"

    ```python
    from obskit.health.checks import RedisCheck

    checker.add_check(RedisCheck(
        name="redis",
        url="redis://redis:6379",
        timeout=3.0,
        # Allow one retry before marking unhealthy
        retry_count=1,
    ))
    ```

=== "Custom check raises unhandled exception"

    ```python
    # Wrap custom checks defensively
    from obskit.health import HealthCheck, CheckResult, CheckStatus

    class MyCheck(HealthCheck):
        async def check(self) -> CheckResult:
            try:
                await self._do_check()
                return CheckResult(status=CheckStatus.HEALTHY)
            except Exception as exc:
                return CheckResult(
                    status=CheckStatus.UNHEALTHY,
                    message=f"Check failed: {exc}",
                )
    ```

---

## Issue: Log Correlation Not Working (No `trace_id`)

obskit injects `trace_id` and `span_id` into every log event **only when an active span exists** in the current context.

### Diagnosis steps

```python
from obskit.logging import get_logger
from obskit.tracing import setup_tracing

# Step 1: confirm tracing is initialised
setup_tracing(service_name="test", debug=True)

# Step 2: log inside a span
from opentelemetry import trace

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("my-operation"):
    logger.info("inside span")   # should include trace_id and span_id

logger.info("outside span")      # will NOT have trace_id — this is correct
```

### Common causes and fixes

=== "setup_tracing() called after get_logger()"

    ```python
    # WRONG — logger captures context before tracing is active
    from obskit.logging import get_logger
    logger = get_logger(__name__)
    from obskit.tracing import setup_tracing
    setup_tracing(...)

    # CORRECT — tracing first
    from obskit.tracing import setup_tracing
    setup_tracing(service_name="order-service")
    from obskit.logging import get_logger
    logger = get_logger(__name__)
    ```

=== "Logging outside a span context"

    Logs emitted outside a span will not have `trace_id`. This is the expected behaviour. Use the middleware or `@with_span` decorator to ensure spans wrap your request handlers.

=== "structlog not using obskit processor"

    If you configured structlog manually without obskit's processor chain, the injection does not occur. Use obskit's factory:

    ```python
    from obskit.logging.factory import configure_logging
    configure_logging()   # sets up the full processor chain including OTel injection
    ```

---

## Issue: obskit Tracing Not Installed But Getting Import Errors

```
ModuleNotFoundError: No module named 'obskit.tracing'
```

### Fix

```bash
# obskit tracing requires the otlp extra
pip install "obskit[otlp]"

# Or install the meta-package which includes everything
pip install obskit[all]

# Verify installation
python -c "from obskit.tracing import setup_tracing; print('OK')"
```

### Conditional import pattern

If tracing is optional in your codebase:

```python
try:
    from obskit.tracing import setup_tracing
    _TRACING_AVAILABLE = True
except ImportError:
    _TRACING_AVAILABLE = False

if _TRACING_AVAILABLE:
    setup_tracing(service_name="order-service")
```

---

## Issue: High Memory Usage from Metrics Cardinality

Prometheus cardinality explosions are one of the most common production problems. Each unique combination of label values creates a new time series in memory.

### Diagnosis

```bash
# Check cardinality of all metrics
curl -s http://localhost:9090/metrics | python -c "
import sys, collections
series = collections.Counter()
for line in sys.stdin:
    if line.startswith('#') or not line.strip():
        continue
    metric = line.split('{')[0].strip()
    series[metric] += 1
for metric, count in series.most_common(10):
    print(f'{count:6} {metric}')
"
```

### Common causes and fixes

=== "Unbounded URL paths as labels"

    ```python
    # WRONG — unique IDs in labels create cardinality explosion
    # e.g. http_requests_total{path="/orders/uuid-1"}, {path="/orders/uuid-2"}, ...
    metrics.request_count.labels(path=request.url.path)

    # CORRECT — use route template, not concrete URL
    metrics.request_count.labels(path="/orders/{order_id}")
    ```

=== "User IDs or email in labels"

    ```python
    # NEVER do this — one series per user = millions of series
    metrics.api_calls.labels(user_id=current_user.id)

    # Use aggregated dimensions instead
    metrics.api_calls.labels(plan="premium")
    ```

=== "obskit cardinality protection"

    Enable the built-in cardinality guard:

    ```python
    from obskit.metrics.cardinality import CardinalityGuard

    guard = CardinalityGuard(
        max_series=10_000,    # alert if any metric exceeds this
        label_bounds={
            "status_code": {"200", "201", "400", "404", "429", "500", "503"},
            "method":      {"GET", "POST", "PUT", "PATCH", "DELETE"},
            "environment": {"production", "staging", "development"},
        },
    )
    guard.install()   # patches the default Prometheus registry
    ```

    Any label value not in the allowed set is replaced with `"__other__"`.

---

## Issue: Circuit Breaker Opens Immediately

### Diagnosis steps

```python
from obskit.resilience import CircuitBreaker

cb = CircuitBreaker(name="payment-api", failure_threshold=5)

# Print current state
print(f"State           : {cb.state}")
print(f"Failure count   : {cb.failure_count}")
print(f"Last failure    : {cb.last_failure_time}")
```

### Common causes and fixes

=== "Threshold too low"

    ```bash
    # Default is 5; for bursty dependencies, raise it
    OBSKIT_CIRCUIT_BREAKER_FAILURE_THRESHOLD=10
    ```

=== "External service is genuinely down"

    The circuit breaker is working correctly. Fix the downstream service or increase the recovery timeout:

    ```bash
    OBSKIT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60.0   # wait 60 s before probing
    ```

=== "Transient errors counted as failures"

    Exclude expected exceptions from the failure counter:

    ```python
    cb = CircuitBreaker(
        name="payment-api",
        failure_threshold=5,
        # Only count server errors (5xx), not client errors (4xx)
        exclude_exceptions=(ValueError, KeyError),
    )
    ```

=== "Recovery timeout too short"

    If the downstream service needs more than 30 s to restart, the circuit oscillates between half-open and open:

    ```python
    cb = CircuitBreaker(
        name="payment-api",
        recovery_timeout=120.0,   # 2 minutes
        half_open_requests=1,     # probe with a single request
    )
    ```

---

## Debug Mode: Printing Spans

Use `debug=True` in `setup_tracing()` to print every span to stdout. This is invaluable when you cannot access Grafana:

```python
from obskit.tracing import setup_tracing

setup_tracing(
    service_name="order-service",
    debug=True,   # ConsoleSpanExporter — human-readable stdout
)
```

!!! danger "Never use `debug=True` in production"
    It bypasses the OTLP exporter and writes unstructured text to stdout, destroying log parsability and flooding your log aggregator.

---

## python -m obskit.core.diagnose

Run the built-in diagnostic tool to get a complete picture of the effective configuration and connectivity:

```bash
python -m obskit.core.diagnose
```

### Interpreting the output

```
obskit v2.0.0 — Diagnostic Report (2026-02-28T10:30:00Z)
==========================================================

Service
  name        : order-service          ✓
  environment : production             ✓
  version     : 2.1.0                  ✓

Tracing
  enabled     : True
  endpoint    : http://tempo:4317
  reachable   : True                   ✓
  sample_rate : 0.1
  insecure    : False                  ✓

Metrics
  enabled     : True
  port        : 9090
  listening   : True                   ✓
  path        : /metrics

Logging
  level       : INFO
  format      : json
  backend     : structlog              ✓

Health
  timeout     : 5.0 s

Packages installed
  obskit               2.2.0          ✓
  prometheus           ✓
  otlp                 ✓
  fastapi              ✓

Validation   : PASS
```

### Warning indicators

| Symbol | Meaning |
|---|---|
| `✓` | Check passed |
| `!` | Warning — non-fatal issue |
| `✗` | Error — action required |

---

## Log Output Format Debugging

If your log aggregator (Loki, Elasticsearch, Splunk) cannot parse obskit JSON logs:

```bash
# Test log output format
python - <<'EOF'
import os
os.environ["OBSKIT_LOG_FORMAT"] = "json"
os.environ["OBSKIT_LOG_LEVEL"] = "DEBUG"

from obskit.logging import get_logger
logger = get_logger("debug-test")
logger.info("test event", key="value", number=42)
EOF
```

Expected JSON output:

```json
{
  "timestamp": "2026-02-28T10:30:00.123456Z",
  "level": "info",
  "logger": "debug-test",
  "event": "test event",
  "key": "value",
  "number": 42,
  "service": "unknown",
  "environment": "development",
  "version": "0.0.0"
}
```

If you see `console` format instead, check:

1. `OBSKIT_LOG_FORMAT` environment variable is correctly set
2. No other code is calling `logging.basicConfig()` before obskit initialises
3. The `logging_backend` is `"structlog"` (loguru uses a different renderer)

---

## Performance Profiling with Benchmarks

If you suspect obskit is adding latency to your hot path, run the micro-benchmarks:

```bash
# Install benchmark dependencies
pip install pytest-benchmark memory-profiler

# Run all benchmarks
cd benchmarks/
pytest bench_metrics.py bench_circuit_breaker.py bench_context.py -v

# Profile memory allocation
python bench_memory.py

# Run the macro benchmark (full stack)
python macro_runner.py --duration 60 --concurrency 50
```

Expected baseline numbers on a modern laptop (M2 MacBook Pro):

| Operation | p50 | p99 |
|---|---|---|
| `logger.info()` | 4 µs | 12 µs |
| `counter.inc()` | 0.8 µs | 2 µs |
| `histogram.observe()` | 1.2 µs | 4 µs |
| `CircuitBreaker.__call__` (closed) | 2 µs | 8 µs |
| `setup_tracing()` (startup, once) | 50 ms | — |
| Context propagation per span | 5 µs | 20 µs |

If your numbers are significantly higher, check:

1. **Log format**: `"json"` is slower than `"console"` — normal for production but avoid in tight loops.
2. **Trace sample rate**: `1.0` in production with high throughput creates export back-pressure. Drop to `0.1`.
3. **Async queue depth**: If `async_metric_queue_size` is too small, the queue fills and drops events; too large causes GC pressure.

```bash
# Profile a specific hot path
python -c "
import cProfile, pstats, io
from obskit.logging import get_logger

logger = get_logger('bench')
pr = cProfile.Profile()
pr.enable()
for _ in range(100_000):
    logger.info('event', x=1)
pr.disable()

s = io.StringIO()
pstats.Stats(pr, stream=s).sort_stats('cumulative').print_stats(20)
print(s.getvalue())
"
```

---

## Getting Help

If none of the above resolves your issue:

1. Run `python -m obskit.core.diagnose` and include the output in your bug report.
2. Check the [GitHub Issues](https://github.com/talaatmagdyx/obskit/issues) for similar reports.
3. Open a new issue with: obskit version, Python version, OS, minimal reproduction script, and the diagnose output.

---

!!! info "obskit self-metrics"
    When `OBSKIT_ENABLE_SELF_METRICS=true`, obskit exposes its own internal metrics at the same `/metrics` endpoint:

    ```promql
    # Async metric queue depth (alert if > 80 % full)
    obskit_async_metric_queue_depth / obskit_async_metric_queue_capacity

    # Spans dropped due to full export queue
    rate(obskit_spans_dropped_total[1m])

    # OTLP export errors
    rate(obskit_otlp_export_errors_total[5m])
    ```

    If `obskit_spans_dropped_total` is rising, increase `OBSKIT_TRACE_EXPORT_QUEUE_SIZE` or reduce your sample rate.

!!! tip "Structured log search for common errors"
    Search Loki or Elasticsearch for obskit-emitted error events:

    ```
    # Loki query for circuit breaker transitions
    {app="order-service"} | json | event = "circuit_breaker_state_change"

    # Loki query for slow requests (> 1 s)
    {app="order-service"} | json | duration_ms > 1000

    # Loki query for all ERROR level events
    {app="order-service"} | json | level = "error"
    ```

!!! warning "High `obskit_async_metric_queue_depth`"
    If this metric consistently exceeds 80 % of capacity, your metric recording rate exceeds the export rate. Remedies in order of preference:

    1. Reduce `OBSKIT_METRICS_SAMPLE_RATE` for high-frequency paths
    2. Increase `OBSKIT_ASYNC_METRIC_QUEUE_SIZE` (uses more memory)
    3. Reduce histogram bucket count (fewer buckets = faster processing)
