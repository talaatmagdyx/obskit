# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0](https://github.com/talaatmagdyx/obskit/releases/tag/v1.1.0) (2026-04-01)

### Fixed

* **Critical: PII leakage** — `make_redaction_processor` was not wired into the default structlog processor chain; passwords, tokens, and secrets were logged in plaintext. Redaction now runs before sampling on every log record.
* **Critical: SQLAlchemy global instrumentation** — `instrument_sqlalchemy()` registered event listeners on the `Engine` class (process-global) instead of the engine instance, hijacking all SQLAlchemy engines created by third-party libraries. Listeners now attach to the passed instance only.
* **`OTLPLogHandler` silent log loss** — `_export_batch()` was a placeholder that silently discarded all log records. The handler now sets up a real `LoggerProvider` + `BatchLogRecordProcessor` + `OTLPLogExporter` pipeline in `__init__`, and `emit()` delegates to it for actual OTLP export.
* **Singleton return-inside-lock** — `get_observability()` and `get_settings()` returned inside the `with _lock:` block (double-checked locking anti-pattern). Moved `return` outside the lock.
* **async_ring emit errors silently swallowed** — exceptions in the background flush thread's emit function were caught and discarded. Now printed to `stderr` so operators can detect dropped records.
* **Sampling TOCTOU race** — `SmartSampler.should_log()` acquired `_dedup_lock` twice with a window between (check then update). Merged into a single atomic block.
* **Correlation ID regex over-permissive** — `_CORRELATION_ID_RE` allowed dots and up to 128 characters. Tightened to alphanumeric + hyphen + underscore, max 64 characters, to prevent header injection abuse.
* **SLO measurement buffer silent overflow** — `SLOTracker` silently dropped measurements when the deque reached capacity with no operator warning. Now emits a structured warning at 80% capacity (sampled every 10 000 measurements).
* **`_dropped` counter race in AsyncLogRing** — concurrent `enqueue()` callers could race on the read-modify-write of `_dropped`, producing duplicate 1000-drop warnings. Protected by a dedicated `threading.Lock`.
* **`CardinalityProtector.protect` double-lock** — two separate lock acquisitions (check, then add) created a TOCTOU window where the same new label value could be admitted twice under concurrent load. Replaced with a single `check_and_add()` atomic operation on `LRUCache`.
* **`SLOTracker.get_all_status` dict size change** — iterating `_targets` without snapshotting keys raised `RuntimeError` if `register_slo()` was called concurrently. Keys are now snapshot under the lock before iteration.

### Performance

* **`SLOTracker.get_status` O(n) → O(1)** — AVAILABILITY and ERROR_RATE status reads previously iterated all N measurements via `sum(1 for m in buf if m.success)`. Now maintained via incremental `_success_counts`/`_total_counts` dicts updated on every `record_measurement` append and window-eviction. Measured improvement: ~1000× at 100 k measurements.
* **Redaction processor `any()` → pre-compiled regex** — `_redact_value` called `any(s in key.lower() for s in _fields)` (11 Python generator steps per log field per event). Now uses a single `re.compile(pattern, IGNORECASE)` at processor-creation time; one C-level `re.search()` per field.
* **`MiddlewareCore.should_exclude` rstrip pre-computed** — `excluded.rstrip("/") + "/"` was recomputed on every request × every excluded path. Normalized prefixes are now pre-built in `__init__`, eliminating 400 k string allocations per 100 k requests.
* **`extract_correlation_id` miss: `uuid4` → `secrets.token_hex`** — `str(uuid.uuid4())` cost ~1.65 µs (UUID object construction + `os.urandom` + `__str__`). Replaced with `secrets.token_hex(16)` (~300 ns); 32-char hex string passes `_CORRELATION_ID_RE`.
* **`_HTPipeline.record()` metrics recorded synchronously** — RED metrics were silently dropped when the high-throughput pipeline was active because `observe_request()` was never called. Metrics are now recorded inline before enqueueing the log record.
* **`decorators/combined.py` `get_red_metrics()` cached at decoration time** — the hot `wrapper()` path called `get_red_metrics()` (a dict lookup + lock) on every request. The `REDMetrics` handle is now resolved once when the decorator is applied.

### Changed

* `integrations/` package — gRPC middleware, DB (SQLAlchemy/psycopg2/psycopg3), and queue (Kafka/RabbitMQ) integrations moved to `obskit.integrations` with per-extra import guards. Install via `obskit[grpc]`, `obskit[sqlalchemy]`, `obskit[psycopg2]`, `obskit[psycopg3]`, `obskit[kafka]`, `obskit[rabbitmq]`, or the bundle `obskit[integrations]`.
* Removed deprecated modules: `obskit.alerts`, `obskit.audit`, `obskit.batch`, `obskit.breakdown`, `obskit.budgets`, `obskit.annotations`, `obskit.alert_dedup`. These were experimental and never part of the stable API.

## [1.0.0](https://github.com/talaatmagdyx/obskit/releases/tag/v1.0.0) (2026-03-30)

Initial production release of obskit — a focused, single-wheel observability toolkit for Python
microservices. Install only what you need via pip extras.

### Features

* **Unified setup**: `configure_observability()` sets up tracing, metrics, and logging in one call,
  returning an `Observability` facade with `.tracer`, `.metrics`, `.logger`, `.config`, and `.shutdown()`
* **Framework instrumentation**: `instrument_fastapi(app)`, `instrument_flask(app)`, `instrument_django()` —
  one-line middleware setup with automatic metrics, traces, correlation IDs, and access logs
* **Structured config**: `ObservabilityConfig` frozen dataclasses grouping settings into `ServiceConfig`,
  `TracingConfig`, `MetricsConfig`, `LoggingConfig`, and `HealthConfig`
* **Structured logging**: JSON-first logging via structlog with automatic trace-log correlation,
  PII redaction (`make_redaction_processor`), and adaptive log sampling
* **RED metrics**: Prometheus-based Rate · Errors · Duration metrics with exemplar support,
  cardinality protection (label truncation + `"invalid_operation"` normalisation),
  multiprocess (Gunicorn) support, and OpenMetrics `/metrics` exposition
* **Distributed tracing**: OpenTelemetry SDK with W3C `traceparent` + `baggage` propagation,
  adaptive head-based sampling, and OTLP export
* **Health checks**: Kubernetes-style liveness/readiness probes with `HealthCheck`, `HealthChecker`,
  `build_health_router`, dependency aggregation, and optional SLO-based health (`obskit[health]`)
* **SLO tracking**: Error budget calculation and burn-rate status via `SLOTracker` (`obskit[slo]`);
  optional Prometheus metrics export (`obskit[slo-prometheus]`)
* **Shared middleware core**: `MiddlewareCore` — protocol-agnostic request instrumentation
  (path exclusion, correlation IDs, metrics recording, response headers)
* **Optional extras — granular installs**:
  - `obskit[prometheus]` — Prometheus client + `/metrics` HTTP server
  - `obskit[otlp]` — OpenTelemetry OTLP exporter
  - `obskit[fastapi]`, `obskit[flask]`, `obskit[django]` — framework middleware
  - `obskit[slo]`, `obskit[slo-prometheus]`, `obskit[slo-all]` — SLO tracking tiers
  - `obskit[health]`, `obskit[health-http]`, `obskit[health-all]` — health check tiers
  - `obskit[sqlalchemy]` — SQLAlchemy OTel auto-instrumentation
  - `obskit[psycopg2]` — psycopg2 OTel auto-instrumentation (sync)
  - `obskit[psycopg3]` — psycopg3 OTel auto-instrumentation (sync + async)
  - `obskit[db]` — all three DB drivers
  - `obskit[kafka]` — Kafka consumer tracing
  - `obskit[rabbitmq]` — RabbitMQ consumer tracing
  - `obskit[grpc]` — gRPC server/client interceptors
  - `obskit[integrations]` — db + kafka + rabbitmq + grpc bundle
  - `obskit[all]` — everything
* **`integrations/` namespace**: DB (`sqlalchemy`, `psycopg2`, `psycopg3`), queue (`kafka`, `rabbitmq`),
  and gRPC middleware live under `obskit.integrations.*` — each with import guards that name the
  exact extra required
* **Lazy top-level imports**: `HealthCheck`, `HealthChecker`, `build_health_router`,
  `instrument_fastapi/flask/django`, and multiprocess helpers are lazy-loaded in `__init__.py`
  via `__getattr__` to avoid `ImportError` when optional extras are not installed
* **Diagnostics**: `python -m obskit.core.diagnose` CLI for environment health checks
* **100% test coverage**: branch coverage enforced in CI (`--cov-fail-under=100`)
* **PEP 561 typed**: full mypy strict mode support

### Package structure

```
obskit/
  core/          context, config, observability, diagnostics
  logging/       structlog-based logger, redaction, sampling, trace correlation
  metrics/       RED metrics, exemplars, cardinality, OpenMetrics, multiprocess
  tracing/       OTel tracer, setup, auto-instrumentation helpers
  middleware/    fastapi, flask, django, core (MiddlewareCore), instrument
  health/        checker, checks, router, aggregator, slo_check
  slo/           tracker, types, prometheus export
  integrations/  grpc, db/(sqlalchemy, psycopg2, psycopg3), queue/(kafka, rabbitmq)
  decorators/    combined, context_managers
```
