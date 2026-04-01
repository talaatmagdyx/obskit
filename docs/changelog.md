# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0](https://github.com/talaatmagdyx/obskit/releases/tag/v1.0.0) (2026-03-30)

Initial production release of obskit — a single-package observability toolkit for Python microservices.

### Features

* **Unified setup**: `configure_observability()` sets up tracing, metrics, and logging in one call, returning an `Observability` facade with `.tracer`, `.metrics`, `.logger`, `.config`, and `.shutdown()`
* **Framework instrumentation**: `instrument_fastapi(app)`, `instrument_flask(app)`, `instrument_django()` — one-line middleware setup
* **Structured config**: `ObservabilityConfig` frozen dataclasses grouping settings into `ServiceConfig`, `TracingConfig`, `MetricsConfig`, `LoggingConfig`, `ResilienceConfig`, `HealthConfig`, `InternalConfig`
* **Structured logging**: JSON-first logging via structlog with automatic trace-log correlation, PII redaction, adaptive sampling, and loguru adapter support
* **RED / Golden / USE metrics**: Prometheus-based metrics with exemplar support, cardinality protection, multiprocess (Gunicorn) support, and OpenMetrics exposition
* **Distributed tracing**: OpenTelemetry SDK with W3C propagation, adaptive sampling, baggage support, and auto-instrumentation for popular frameworks
* **Health checks**: Kubernetes-style liveness/readiness/startup probes with dependency aggregation, SLO-based health, and FastAPI router integration
* **Resilience patterns**: Circuit breaker, rate limiter (sliding window + token bucket), retry with exponential backoff and jitter, adaptive retry, combined resilience, and distributed circuit breaker (Redis)
* **SLO tracking**: Error budget calculation, burn-rate alerting, Prometheus metrics export, and Alertmanager integration
* **Alert builder**: Fluent `AlertRule` / `AlertGroup` API with YAML export for Prometheus alerting rules
* **Middleware**: Raw ASGI (FastAPI), Flask hooks, Django middleware protocol, and gRPC interceptors — all with correlation ID propagation, metrics, logging, and tracing
* **Shared middleware core**: `MiddlewareCore` protocol-agnostic request instrumentation (path exclusion, correlation IDs, metrics recording, response headers)
* **Database instrumentation**: SQLAlchemy query tracking with slow query detection
* **Queue instrumentation**: Kafka and RabbitMQ message tracing with OpenTelemetry context propagation
* **Module tiers**: `_experimental/` and `_internal/` namespace packages for clear API stability boundaries
* **Lazy imports**: Optional dependencies (SQLAlchemy, OpenTelemetry, etc.) are lazy-loaded to avoid ImportError when not installed
* **Self-monitoring**: obskit's own internal metrics (queue depth, errors, exporter health)
* **Diagnostics**: `python -m obskit.core.diagnose` CLI for environment health checks
* **Testing utilities**: Mock helpers and test fixtures for obskit-instrumented code
* **100% test coverage**: 4,168 tests with branch coverage enforced in CI
* **PEP 561 typed**: Full mypy strict mode support
