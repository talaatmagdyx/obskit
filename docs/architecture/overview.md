# Architecture Overview

This document describes the internal architecture of obskit v3.0.0 — the
single-package layout, optional extras design, dependency graph, and key data flows.

---

## Package Structure

```
obskit/                          # Git repository root
├── src/
│   └── obskit/                  # Single Python package
│       ├── __init__.py
│       ├── _version.py
│       ├── config.py            # ObskitSettings (pydantic-settings)
│       ├── config_file.py       # YAML config file loader
│       ├── correlation.py       # Correlation/request/session ID management
│       ├── errors/              # Structured exception hierarchy
│       ├── interfaces/          # Abstract base classes (protocols)
│       ├── core/                # Context propagation, diagnose, deprecation
│       ├── logging/             # Structured logging, adapters, OTLP export
│       ├── metrics/             # RED/Golden/USE, exemplars, cardinality guard
│       ├── tracing/             # OpenTelemetry setup, trace_span, auto-instrumentation
│       ├── health/              # Health check framework, HTTP server
│       ├── resilience/          # Circuit breaker, retry, rate limiter
│       ├── slo/                 # SLO/SLA tracking, alerting, error budgets
│       ├── alerts/              # Alert rules and deduplication
│       ├── decorators/          # @with_observability, @trace cross-cutting decorators
│       ├── db/                  # SQLAlchemy instrumentation, query analyzer
│       ├── queue/               # Kafka/RabbitMQ tracing, consumer-lag, DLQ
│       ├── dashboards/          # Grafana dashboard generators
│       ├── middleware/          # Framework middlewares (fastapi, flask, django, grpc)
│       └── testing/             # Test helpers, mocks, ObskitTestCase
├── tests/
│   └── unit/                    # All unit tests (flat structure)
├── benchmarks/                  # pytest-benchmark + macro_runner
├── docs/                        # MkDocs source (this site)
├── mkdocs.yml
└── pyproject.toml               # Package metadata + tool config
```

---

## Optional Extras Design

All functionality is in a single `obskit` package. Heavy optional dependencies are
gated behind **extras** — users only install what they need:

```mermaid
graph TD
    core["obskit (core)\nstructlog · PyYAML · pydantic-settings\nlogging · health · resilience · slo · decorators"]

    prom["obskit[prometheus]\nprometheus-client"]
    otlp["obskit[otlp]\nopentelemetry-api/sdk/exporter"]
    loguru["obskit[loguru]\nloguru"]
    fastapi["obskit[fastapi]\nfastapi · starlette"]
    flask["obskit[flask]\nflask · werkzeug"]
    django["obskit[django]\ndjango"]
    sqlalchemy["obskit[sqlalchemy]\nsqlalchemy 2.0"]
    kafka["obskit[kafka]\nkafka-python"]
    rabbitmq["obskit[rabbitmq]\npika"]
    redis["obskit[redis]\nredis"]
    httpx["obskit[httpx]\nhttpx"]

    core --> prom
    core --> otlp
    core --> loguru
    core --> fastapi
    core --> flask
    core --> django
    core --> sqlalchemy
    core --> kafka
    core --> rabbitmq
    core --> redis
    core --> httpx
```

**Key properties:**

- Any combination of extras can be installed independently.
- Optional dependencies that are not installed gracefully no-op (`is_tracing_available()` returns
  `False`) rather than raising `ImportError`.
- All imports (`from obskit.logging import get_logger`) work regardless of which extras are installed.

---

## Module Dependency Graph

```mermaid
graph TD
    config[obskit.config]
    core[obskit.core]
    logging[obskit.logging]
    metrics[obskit.metrics]
    tracing[obskit.tracing]
    health[obskit.health]
    resilience[obskit.resilience]
    slo[obskit.slo]
    decorators[obskit.decorators]
    db[obskit.db]
    queue[obskit.queue]
    dashboards[obskit.dashboards]
    mw[obskit.middleware]

    logging --> config & core
    metrics --> config & core
    tracing --> config & core
    health --> config & core & metrics
    resilience --> config & core & logging & metrics
    slo --> config & core & logging & metrics
    decorators --> logging & metrics & resilience & slo
    db --> tracing & metrics
    queue --> tracing & metrics
    mw --> logging & metrics & tracing
```

**Rules:**
- `obskit.config` and `obskit.core` have no internal obskit dependencies.
- Optional extras (prometheus-client, opentelemetry, etc.) are guarded with runtime availability checks.
- No circular dependencies.

---

## Zero-Overhead Design

All optional integrations are guarded with runtime availability checks.  If an
optional dependency is not installed, the feature degrades gracefully to a no-op.

```python
# Inside obskit/metrics/exemplar.py
def _otel_available() -> bool:
    try:
        from opentelemetry import trace  # noqa: F401
        return True
    except ImportError:
        return False

def observe_with_exemplar(metric, value: float) -> None:
    if not _otel_available():
        metric.observe(value)   # no exemplar — no overhead
        return
    exemplar = get_trace_exemplar()
    metric.observe(value, exemplar=exemplar)
```

This pattern is used throughout:

| Feature | Guard | When not installed |
|---|---|---|
| Trace-log correlation | `is_trace_correlation_available()` | Logs emitted without `trace_id` |
| Exemplars | `is_exemplar_available()` | Observations without exemplar dict |
| OTLP log export | `obskit.logging.otlp` | Logs written to stdout only |
| structlog backend | `OBSKIT_LOGGING_BACKEND=auto` | Falls back to stdlib `logging` |
| Loguru adapter | `is_loguru_available()` | No-op |

---

## Configuration Flow

```mermaid
sequenceDiagram
    participant Env as Environment Variables
    participant DotEnv as .env File
    participant Configure as configure()
    participant Settings as ObskitSettings
    participant Logging as obskit.logging
    participant Metrics as obskit.metrics
    participant Tracing as obskit.tracing

    Env->>Settings: OBSKIT_* vars (highest priority)
    DotEnv->>Settings: .env file (medium priority)
    Configure->>Settings: configure(**kwargs) (code-level)
    Settings->>Settings: Validate + merge
    Settings->>Logging: log_level, log_format, service_name
    Settings->>Metrics: metrics_enabled, metrics_port
    Settings->>Tracing: otlp_endpoint, trace_sample_rate
```

**Singleton pattern:**
`get_settings()` returns a module-level singleton initialised lazily on first call.
`configure()` sets the singleton from provided kwargs.  Both are thread-safe (guarded
by `threading.Lock`).

---

## Trace-Log Correlation Data Flow

```mermaid
sequenceDiagram
    participant App as Application code
    participant TraceSpan as trace_span()
    participant OTel as OTel SDK
    participant LogCtx as structlog contextvars
    participant Logger as get_logger()
    participant Output as JSON output

    App->>TraceSpan: enter context manager
    TraceSpan->>OTel: create Span, attach to context
    TraceSpan->>LogCtx: bind(trace_id=..., span_id=...)
    App->>Logger: logger.info("event", **kwargs)
    Logger->>LogCtx: merge bound vars
    LogCtx->>Output: {"event": ..., "trace_id": "4bf9...", "span_id": "00f0..."}
    App->>TraceSpan: exit context manager
    TraceSpan->>OTel: end Span
    TraceSpan->>LogCtx: unbind trace_id, span_id
```

The structlog `contextvars` processor (`merge_contextvars`) picks up the
`trace_id`/`span_id` values that `trace_span()` wrote to the current context.
No manual work is required in application code.

---

## Exemplar Data Flow

Exemplars link a Prometheus histogram observation to a specific OTel trace,
enabling one-click navigation from a metric spike to the corresponding trace.

```mermaid
sequenceDiagram
    participant App as Application code
    participant OTel as Active Span (OTel)
    participant Exemplar as observe_with_exemplar()
    participant Prom as Prometheus Histogram
    participant Grafana as Grafana

    App->>OTel: trace_span() creates span with trace_id=T
    App->>Exemplar: observe_with_exemplar(histogram, duration)
    Exemplar->>OTel: get_current_span().get_span_context()
    OTel->>Exemplar: trace_id=T
    Exemplar->>Prom: histogram.observe(duration, exemplar={"trace_id": T})
    Prom->>Grafana: /metrics scrape → observation includes exemplar
    Grafana->>Grafana: "Jump to trace T" link on histogram panel
```

---

## Health Check with Tracing Data Flow

```mermaid
sequenceDiagram
    participant K8s as Kubernetes
    participant Server as Health HTTP Server
    participant Checker as HealthChecker
    participant Check as user-defined check fn
    participant OTel as OTel SDK
    participant Response as HTTP Response

    K8s->>Server: GET /health
    Server->>OTel: start Span "health_check"
    Server->>Checker: run_checks()
    Checker->>Check: check_database()
    Check->>Checker: True / False
    Checker->>OTel: get trace_id
    Checker->>Response: HealthResult(status, trace_id=T, checks={...})
    Server->>K8s: 200 OK {"status": "healthy", "trace_id": "4bf9...", "checks": {...}}
```

The `trace_id` in the health response lets you correlate a failed health check
with the OTel trace that captured what the check function actually did.

---

## Plugin / Extension Points

obskit provides several extension points for advanced use cases:

### Custom health checks

```python
from obskit.health import HealthChecker

checker = HealthChecker()

async def check_ml_model() -> bool:
    return await model.ping()

checker.add_check("ml-model", check_ml_model, critical=False)
# critical=False → failure downgrades to DEGRADED, not UNHEALTHY
```

### Custom structlog processors

```python
from obskit.logging.factory import create_logger

def add_datacenter(logger, method, event_dict):
    event_dict["dc"] = "eu-west-1"
    return event_dict

logger = create_logger(__name__, extra_processors=[add_datacenter])
```

### Custom OTel instrumentors

```python
from obskit.tracing import setup_tracing
from opentelemetry.instrumentation.celery import CeleryInstrumentor

setup_tracing(exporter_endpoint="http://tempo:4317", instrument=[])
CeleryInstrumentor().instrument()  # apply manually with custom config
```

### Custom metrics alongside obskit

```python
from prometheus_client import Counter
from obskit.metrics import REDMetrics

# Your custom counter — registered in the same Prometheus registry
CACHE_HITS = Counter("cache_hits_total", "Cache hits", ["cache_name"])

# obskit REDMetrics also in the same registry
red = REDMetrics("api_service")
```

### ObskitSettings subclass

```python
from obskit.config import ObskitSettings

class MyAppSettings(ObskitSettings):
    my_custom_field: str = "default"

settings = MyAppSettings()
```
