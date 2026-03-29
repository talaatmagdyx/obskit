# Changelog

All notable changes to obskit are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
obskit adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

No unreleased changes at this time.

---

## [3.3.0] — 2026-03-29

### Added

- **`tracing.tracer.get_span_drop_count()`** — returns the cumulative number of spans dropped by the `BatchSpanProcessor`; enables alerting when span data is silently lost under high load (queue full).

### Fixed

- **`resilience.circuit_breaker`** — replaced `time.time()` with `time.monotonic()` for all elapsed-time comparisons; prevents circuit breaker getting permanently stuck open when NTP adjusts the system clock backward.
- **`resilience.rate_limiter`** — replaced `time.time()` with `time.monotonic()` in sliding-window and token-bucket implementations; eliminates false allow/deny decisions under NTP clock skew.
- **`metrics.registry`** — added `thread.join(timeout=5.0)` after `server.shutdown()` in `stop_http_server()`; prevents process hang under Kubernetes `terminationGracePeriodSeconds` when the metrics server thread doesn't exit promptly.
- **`metrics.red`** — fixed dead-code bug in operation label validation: changed character-check regex from `{1,128}` to `+` so the hash-truncation branch for labels >128 chars is actually reachable; two-tier protection now correctly separates character validation from length enforcement.
- **`config.ObskitSettings`** — overrode `model_dump()` to replace `metrics_auth_token` with `[REDACTED]`; prevents credential leakage when settings objects are serialised into log records or error reports.
- **`tracing.tracer`** — fixed W3C baggage validation to use byte length (`len(value.encode("ascii"))`) instead of character length; correctly rejects multi-byte characters that would exceed the 4096-byte HTTP header limit.
- **`metrics.multiprocess.child_exit`** — added worker `.db` file deletion loop after `mark_process_dead()`; prevents unbounded file accumulation in `PROMETHEUS_MULTIPROC_DIR` across repeated gunicorn `SIGHUP` reloads.
- **`middleware.fastapi`** — 404 responses with no matched route now use `unmatched_route` as the operation label; prevents Prometheus cardinality explosion from bots/attackers probing random paths.
- **docs** — fixed `mkdocs build --strict` failure: `pymdownx.highlight anchor_linenums: true` passed `filename=None` to pygments `HtmlFormatter` (pygments ≥ 2.18 calls `html.escape()` on it); changed to `anchor_linenums: false`.

---

## [3.2.0] — 2026-03-29

### Added

- **`obskit.logging.redaction`** — new module providing structured-log sensitive-field redaction as a structlog processor.
  - `make_redaction_processor(fields, placeholder)` — factory that returns a processor redacting any log field whose name contains a sensitive substring (case-insensitive). Supports recursive dict traversal up to 10 levels deep, circular-reference detection, and custom field sets / placeholders.
  - `redact_sensitive_fields` — zero-config singleton with the default 11-field set (`password`, `passwd`, `secret`, `token`, `api_key`, `apikey`, `auth`, `credential`, `private_key`, `access_key`, `bearer`).
  - `DEFAULT_SENSITIVE_FIELDS` — the frozenset of default patterns; importable for extension.

- **`obskit.metrics.multiprocess`** — new module with Prometheus multiprocess-mode helpers for Gunicorn/uWSGI deployments.
  - `is_multiprocess_mode()` — returns `True` when `PROMETHEUS_MULTIPROC_DIR` or `prometheus_multiproc_dir` env vars are set and non-empty.
  - `setup_multiprocess_registry()` — returns a `CollectorRegistry` configured for multiprocess scraping; creates the directory if needed, raises `RuntimeError` on permission errors.
  - `make_multiprocess_app(registry)` — wraps the registry in a WSGI app suitable for mounting at `/metrics`.

### Fixed

- **`resilience/retry`** — unreachable `except AttributeError` branches in `_is_permanent_http_failure` marked `# pragma: no cover` (3-arg `getattr` never raises `AttributeError`).
- **`tracing/tracer`** — `set_baggage()` now correctly raises `ValueError` for non-ASCII characters, control characters, and keys/values exceeding `_BAGGAGE_MAX_KEY_LEN` / `_BAGGAGE_MAX_VALUE_LEN`.
- **`tracing/tracer`** — `extract_trace_context()` safely truncates oversized `tracestate` headers (>512 bytes); lazy regex reset correctly re-compiles `_W3C_TRACEPARENT_RE` when the global is set to `None`.
- **`tracing/auto`** — `get_failed_instrumentors()` returns a snapshot copy; instrumentors that previously failed can be retried when explicitly re-requested.
- **`middleware/fastapi`** — corrected Starlette type-ignore comments: `Scope` and `Message` require `[misc,assignment]`; `ASGIApp`, `Receive`, `Send` need only `[misc]`.
- **`logging/redaction`** — fixed mypy `no-any-return` type-ignore annotation on `_redact_value` return.
- **`metrics/red`, `config`, `logging/logger`, `metrics/registry`** — all inner double-check locking branches marked `# pragma: no cover`.

### Tests

- **100% test coverage** — 4,075 tests, 0 missed statements, 0 missed branches.
- New: `tests/unit/logging/test_redaction.py` — full coverage of the redaction module.
- New: `tests/unit/metrics/test_multiprocess.py` — full coverage of multiprocess helpers.
- Extended: retry, tracing/auto, tracing/tracer, middleware/fastapi, health/router, metrics/red, metrics/auth, resilience/rate_limiter, config tests.

### CI

- All workflows pass: `ruff check`, `ruff format --check`, `mypy` (140 source files, no issues), `pytest --cov-fail-under=100`.

---

## [2.0.0] — 2025 Q1

This is the **monorepo release** of obskit.  The single `obskit` wheel has been
split into 16 focused namespace packages that share the `obskit.*` Python namespace.
Existing code using `pip install "obskit[all]"` is drop-in compatible.

See the full [Migration Guide](migration/from-v1.md) for step-by-step instructions.

### Added

#### Single package with optional extras

| Package | What it provides | Install |
|---|---|---|
| `obskit` | Core package | `pip install obskit` |
| `obskit[prometheus]` | Prometheus metrics | `pip install "obskit[prometheus]"` |
| `obskit[otlp]` | OpenTelemetry tracing | `pip install "obskit[otlp]"` |
| `obskit[fastapi]` | FastAPI middleware | `pip install "obskit[fastapi]"` |
| `obskit[flask]` | Flask middleware | `pip install "obskit[flask]"` |
| `obskit[django]` | Django middleware | `pip install "obskit[django]"` |
| `obskit[sqlalchemy]` | SQLAlchemy instrumentation | `pip install "obskit[sqlalchemy]"` |
| `obskit[kafka]` | Kafka instrumentation | `pip install "obskit[kafka]"` |
| `obskit[rabbitmq]` | RabbitMQ instrumentation | `pip install "obskit[rabbitmq]"` |
| `obskit[redis]` | Redis instrumentation | `pip install "obskit[redis]"` |
| `obskit[httpx]` | httpx instrumentation | `pip install "obskit[httpx]"` |
| `obskit[loguru]` | Loguru adapter | `pip install "obskit[loguru]"` |
| `obskit[all]` | Everything above | `pip install "obskit[all]"` |

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
+pip install "obskit[prometheus]"==2.0.0
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
  See [obskit slo module](packages/slo.md).

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
- gRPC server and client interceptors (obskit grpc middleware module).

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
