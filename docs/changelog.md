# Changelog

All notable changes to obskit are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
obskit adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

No unreleased changes at this time.

---

## [2.0.0] — 2025 Q1

This is the **monorepo release** of obskit.  The single `obskit` wheel has been
split into 16 focused namespace packages that share the `obskit.*` Python namespace.
Existing code using `pip install "obskit[all]"` is drop-in compatible.

See the full [Migration Guide](migration/from-v1.md) for step-by-step instructions.

### Added

#### Monorepo split — 16 namespace packages

| Package | Install | What it provides |
|---|---|---|
| `obskit-core` | `pip install obskit-core` | Config, errors, interfaces, correlation, test helpers |
| `obskit-logging` | `pip install obskit-logging` | Structured logging, adaptive sampling, OTLP export |
| `obskit-metrics` | `pip install obskit-metrics` | RED/Golden/USE metrics, exemplars, cardinality guard |
| `obskit-tracing` | `pip install obskit-tracing` | OTel setup, `trace_span`, auto-instrumentation |
| `obskit-health` | `pip install obskit-health` | Health check framework, `/health` HTTP server |
| `obskit-resilience` | `pip install obskit-resilience` | Circuit breaker, retry, rate limiter |
| `obskit-slo` | `pip install obskit-slo` | SLO/SLA tracking, error budgets, alerting |
| `obskit-decorators` | `pip install obskit-decorators` | `@with_observability` cross-cutting decorator |
| `obskit-db` | `pip install obskit-db` | SQLAlchemy instrumentation, query analyzer |
| `obskit-queue` | `pip install obskit-queue` | Kafka/RabbitMQ tracing, consumer-lag, DLQ |
| `obskit-dashboards` | `pip install obskit-dashboards` | Grafana dashboard generators |
| `obskit-middleware-fastapi` | `pip install obskit-middleware-fastapi` | FastAPI ASGI middleware |
| `obskit-middleware-flask` | `pip install obskit-middleware-flask` | Flask WSGI middleware |
| `obskit-middleware-django` | `pip install obskit-middleware-django` | Django middleware |
| `obskit-middleware-grpc` | `pip install obskit-middleware-grpc` | gRPC server/client interceptors |
| `obskit` | `pip install "obskit[all]"` | Meta-package; installs all of the above |

#### New APIs

- **`obskit.tracing.setup_tracing()`** — consolidated tracing setup replacing the
  verbose `configure_tracing()` call.  Auto-detects installed OTel instrumentors.
- **`obskit.metrics.exemplar.observe_with_exemplar()`** — attaches the current OTel
  `trace_id` as a Prometheus exemplar on a Histogram or Summary observation.
- **`obskit.metrics.exemplar.get_trace_exemplar()`** — returns the current OTel
  trace ID formatted as a Prometheus exemplar dict.
- **`obskit.health.HealthResult.trace_id`** — health check HTTP responses now include
  the active OTel `trace_id` so failed checks can be correlated with traces.
- **`obskit.tracing.set_baggage()` / `get_baggage()` / `clear_baggage()`** — clean
  W3C Baggage API replacing the verbose OTel SDK calls.
- **`obskit.slo.with_slo_tracking()`** / **`with_slo_tracking_sync()`** — decorators
  that record an SLO measurement on every function call.
- **`obskit.core.diagnose`** — CLI and programmatic API for environment diagnostics:
  `python -m obskit.core.diagnose`.
- **`obskit.logging.get_trace_context()`** — returns `{"trace_id": ..., "span_id": ...}`
  for inclusion in API responses.
- **`obskit.logging.is_trace_correlation_available()`** — feature detection for OTel.
- **`obskit.tracing.async_trace_span()`** — async context manager for tracing async
  functions without the sync overhead of `trace_span()`.
- **`obskit.tracing.detect_available_instrumentors()`** — lists installed OTel
  instrumentation packages.

#### Documentation

- Full MkDocs Material documentation site (this site).
- Migration guides: v1→v2, from prometheus-client, from OpenTelemetry, from structlog,
  from Datadog.
- Architecture overview with Mermaid diagrams.
- Performance guide with benchmark thresholds and tuning tips.
- Architecture Decision Records (ADR-001 through ADR-006).
- Contributing guide with ADR process, release flow, and new-package checklist.

#### Quality

- **100% test coverage** enforced on every package.
- Mutation testing via `mutmut` in weekly CI.
- Security scanning via `pip-audit`, `safety`, and `bandit` in weekly CI.
- SBOM generation via `cyclonedx-bom` on every release.
- Release signing via `sigstore` on every release.
- Benchmark regression gates: any PR that regresses mean latency by >10% is blocked.

### Changed

#### Installation

```diff
-pip install obskit==1.5.0
+pip install "obskit[all]==2.0.0"   # drop-in compatible

# Or per-package (new in v2):
+pip install obskit-metrics==2.0.0
```

#### Preferred import paths

| Old (still works) | New (preferred) |
|---|---|
| `from obskit import configure_logging` | `from obskit.logging import get_logger` |
| `from obskit import get_red_metrics` | `from obskit.metrics.red import REDMetrics` |
| `from obskit import get_health_checker` | `from obskit.health import HealthChecker` |
| `from obskit import configure_tracing` | `from obskit.tracing import setup_tracing` |

#### `setup_tracing()` replaces `configure_tracing()`

`setup_tracing()` accepts the same arguments as `configure_tracing()` plus:

- `instrument` — explicit list of instrumentors, or `None` for auto-detect.
- `resource_attributes` — extra OTel resource key-value pairs.
- `debug` — `True` prints spans to stdout (replaces the old `console_exporter` arg).

#### `REDMetrics.record_request()` replaces `track_request()`

```diff
-metrics.track_request(endpoint, method)
+red.record_request(endpoint, method, status="success", duration=0.045)
```

The new signature requires `status` and `duration` at call time rather than inside
a context manager.

### Breaking Changes

- Removed experimental modules: `obskit.capacity`, `obskit.chaos`,
  `obskit.compliance.pii`, `obskit.compliance_reporter`, `obskit.deployment`,
  `obskit.feature_flags`, `obskit.flamegraph`, `obskit.incident_timeline`,
  `obskit.resource_predictor`, `obskit.root_cause`, `obskit.runbook`,
  `obskit.secrets_detector`, `obskit.self_healing`.
- Python 3.10 is no longer supported (3.11+ required).
- `configure_logging()` now emits `DeprecationWarning`; use `get_logger()`.
- `REDMetrics.track_request()` now emits `DeprecationWarning`; use `record_request()`.
- `configure_tracing()` now emits `DeprecationWarning`; use `setup_tracing()`.

---

## [1.5.0] — 2024 Q4

### Added

- `with_slo_tracking` and `with_slo_tracking_sync` decorators for SLO measurement.
- `SLOTracker.get_window_summary()` for error budget dashboards.
- `CircuitBreaker` synchronous context manager (`with breaker:` in addition to
  `async with breaker:`).
- `CardinalityGuard` — protects Prometheus from high-cardinality label attacks.
  See [Cardinality Protection guide](user-guide/metrics.md#cardinality-management).
- Queue tracking: consumer lag metrics and DLQ monitoring for Kafka and RabbitMQ.
  See [obskit-slo package](packages/slo.md).

### Changed

- `BatchSpanProcessor` queue size default increased from 512 to 2048 to reduce span
  drops under burst traffic.

### Fixed

- Circular import bug in `obskit.resilience` when importing `combined.py` before
  `circuit_breaker.py` (v1.3.3).

---

## [1.4.0] — 2024 Q3

### Added

- Cardinality protection via `CardinalityGuard`.
- Synchronous circuit breaker (allows `with breaker:` in non-async code).
- Enhanced queue tracking: consumer lag metrics, DLQ size, per-partition offsets.
- `AdaptiveSampler` — dynamically adjusts log sample rate based on error rate.
- `TenantMetrics` — per-tenant request tracking with automatic cardinality cap.

### Changed

- `Histogram` buckets updated to OpenMetrics standard
  (`.005`, `.01`, `.025`, `.05`, `.1`, `.25`, `.5`, `1`, `2.5`, `5`, `10`).
- `HealthChecker.run_checks()` now returns `HealthResult` with a `duration_ms` field.

---

## [1.3.3] — 2024 Q3 (patch)

### Fixed

- Critical circular import bug in `obskit.resilience`: importing `combined.py`
  before `circuit_breaker.py` raised `ImportError` in certain import orders.

---

## [1.3.2] — 2024 Q3 (patch)

### Changed

- Version bump to align with internal tagging convention.

---

## [1.3.1] — 2024 Q2

### Added

- `obskit.logging.adapters.loguru_adapter` — bridge for teams using Loguru.
- `obskit.logging.adapters.structlog_adapter` — explicit adapter class for structlog.
- `obskit.logging.async_ring` — lock-free async ring buffer for high-throughput log
  emission.
- `obskit.metrics.statsd_emitter` — DogStatsd-compatible emitter for hybrid setups.
- `obskit.metrics.threadsafe_aggregator` — thread-safe metric aggregation for
  multi-threaded Celery workers.
- `obskit.resilience.distributed` — distributed circuit breaker state via Redis.
- `obskit.resilience.adaptive` — adaptive circuit breaker that tunes thresholds based
  on rolling error rate.

### Changed

- `ObskitSettings` migrated from `pydantic.BaseSettings` to `pydantic-settings`
  (`pydantic_settings.BaseSettings`) — pydantic v2 compatibility.
- `OBSKIT_LOG_FORMAT` now accepts `"console"` in addition to `"text"` (deprecated).

### Fixed

- Unused `TYPE_CHECKING` import removed from `obskit.middleware.django`
  (broke Django < 4.x).
- Django version check logic corrected for Django 5.x.

---

## [1.3.0] — 2024 Q2

### Added

- **SLO tracking**: `SLOTracker`, `SLOType`, `SLOTarget`, error budget calculation.
- **Alertmanager integration**: generate Prometheus alerting rules from SLO targets.
- **SLA predictor**: estimate future SLA compliance based on current error budget
  burn rate.
- `obskit.health.slo_check` — health check that fails when error budget is exhausted.

---

## [1.2.0] — 2024 Q1

### Added

- `GoldenSignals` — Google SRE Four Golden Signals implementation.
- `USEMetrics` — Brendan Gregg's USE Method for infrastructure.
- `obskit.metrics.golden` — pre-built Prometheus recording rules for Golden Signals.
- `obskit.metrics.presets` — opinionated metric presets for common service types.
- gRPC server and client interceptors (`obskit-middleware-grpc`).

---

## [1.1.0] — 2024 Q1

### Added

- `obskit.health.aggregator` — aggregate health across multiple `HealthChecker`
  instances for microservice health dashboards.
- `obskit.db.sqlalchemy` — SQLAlchemy event listener for automatic query tracing.
- `obskit.db.query_analyzer` — slow query detection and logging.

---

## [1.0.0] — 2023 Q4

Initial production release.

### Included

- `REDMetrics` (Rate, Errors, Duration).
- `CircuitBreaker` (async, three-state machine).
- `retry` / `async_retry` decorators with exponential backoff.
- `HealthChecker` with Kubernetes liveness/readiness semantics.
- Structured logging via structlog with JSON and console outputs.
- OpenTelemetry tracing with OTLP export and auto-instrumentation.
- FastAPI, Flask, and Django middleware.
- `ObskitSettings` via pydantic-settings.
- Kafka and RabbitMQ queue instrumentation.
