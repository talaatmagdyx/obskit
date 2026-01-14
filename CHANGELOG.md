# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0 (2026-01-14)


### Bug Fixes

* resolve CI issues and add security policy ([4ebf623](https://github.com/talaatmagdyx/obskit/commit/4ebf6232ee27d15b7dd8b684458dea1908d22bbe))


### Dependencies

* update pre-commit requirement ([f45b521](https://github.com/talaatmagdyx/obskit/commit/f45b521409fe63bb85b6083a1c3a9044bdf404d7))
* update pytest requirement from &lt;9.0.0,&gt;=8.0.0 to >=8.0.0,<10.0.0 ([59fcd1d](https://github.com/talaatmagdyx/obskit/commit/59fcd1d4222933beb6712c6d73c9695f7b924a06))
* update pytest-benchmark requirement ([ffabef0](https://github.com/talaatmagdyx/obskit/commit/ffabef0003b9216360937742398b8371a1e96cec))
* update pytest-cov requirement ([a36bfcb](https://github.com/talaatmagdyx/obskit/commit/a36bfcb643781424a7cc8dbe6684e58a9d450b7f))
* update redis requirement from &lt;6.0.0,&gt;=5.0.0 to >=5.0.0,<8.0.0 ([34984b3](https://github.com/talaatmagdyx/obskit/commit/34984b39a98b08f02d7a6bee232b475e689faaab))


### Documentation

* improve documentation and prepare for PyPI publishing ([08ef729](https://github.com/talaatmagdyx/obskit/commit/08ef72925abefb01f17e10b16d414e60db86f09f))

## [1.0.0] - 2026-01-13

### 🎉 Production Stable Release

This release marks obskit as **fully production-ready** with all components stable.

### Stability Upgrades

- **Distributed Circuit Breaker** → ✅ **STABLE**
  - Full support for sync and async Redis clients
  - State persistence with configurable TTL
  - Graceful degradation on Redis failures
  - Multi-instance synchronization

- **SLO Tracking** → ✅ **STABLE**
  - Availability, Error Rate, Latency, Throughput SLOs
  - Error budget tracking with burn rate calculation
  - Alertmanager webhook integration
  - Prometheus metrics export

- **Self-Metrics** → ✅ **STABLE**
  - `obskit_async_queue_depth` gauge
  - `obskit_async_queue_capacity` gauge
  - `obskit_metrics_dropped_total` counter
  - `obskit_errors_total` counter
  - `obskit_info` version information

### Added

- **Built-in Health Checks**
  - `create_redis_check()` - Redis/Redis Cluster health
  - `create_memory_check()` - Memory utilization monitoring
  - `create_disk_check()` - Disk utilization monitoring
  - `create_http_check()` - External HTTP dependency checks

- **Rate Limiting for Metrics Endpoint**
  - `metrics_rate_limit_enabled` configuration
  - `metrics_rate_limit_requests` per minute limit
  - HTTP 429 response with Retry-After header

- **Configurable Async Queue**
  - `async_metric_queue_size` configuration
  - Self-monitoring of queue depth
  - Dropped metric tracking

- **Security Enhancements**
  - Complete security documentation
  - AWS Secrets Manager integration guide
  - HashiCorp Vault integration guide
  - Kubernetes External Secrets examples

- **Comprehensive Documentation**
  - `docs/PRODUCTION_GUIDE.md` - Complete production usage guide
  - `docs/API_STABILITY.md` - API stability guarantees
  - `docs/PERFORMANCE.md` - Performance tuning guide
  - `PRODUCTION_READINESS_REVIEW.md` - Production readiness review

### Changed

- Version bumped to 1.0.0 (production stable)
- Development Status classifier → "5 - Production/Stable"
- All dependencies now have upper bounds for predictability
- Improved thread safety in all singleton patterns

### Security

- All dependencies bounded to prevent unexpected breaking changes
- Security scanning tools available via `obskit[security]`
- Comprehensive PII redaction documentation

### Documentation

- Complete production deployment checklist (all items ✅)
- Kubernetes manifests with security best practices
- Prometheus alerting rules for obskit self-metrics
- Grafana dashboard examples

---

## [0.1.0] - 2024-01-15

### Added

- Initial release
- **Metrics**
  - RED Method (Rate, Errors, Duration)
  - Golden Signals (Latency, Traffic, Errors, Saturation)
  - USE Method (Utilization, Saturation, Errors)
  - Async metric recording
  - Tenant-aware metrics
  - Metrics sampling
- **Logging**
  - Structured logging with structlog
  - JSON and console formats
  - Correlation ID propagation
  - PII redaction
  - Dynamic log level adjustment
- **Tracing**
  - OpenTelemetry integration
  - OTLP export
  - W3C Trace Context propagation
  - Trace sampling
- **Health Checks**
  - Liveness probes
  - Readiness probes
  - Kubernetes-compatible endpoints
- **Resilience**
  - Circuit breaker pattern
  - Distributed circuit breaker (Redis) - Beta
  - Retry with exponential backoff
  - Rate limiting (token bucket, sliding window)
- **SLO**
  - SLO tracking - Beta
  - Error budget calculation
  - Prometheus alerting rules generation
- **Middleware**
  - FastAPI integration
  - Flask integration
  - Django integration
  - Automatic request tracking
- **Security**
  - Metrics endpoint authentication
  - PII redaction

### Fixed

- Thread safety in global singletons
- Metrics HTTP server lifecycle management
- Trace context propagation in async code

### Security

- PII redaction support
- Metrics endpoint authentication option
- Sensitive data filtering in traces
