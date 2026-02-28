# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-02-27

### Breaking Changes

- **Monorepo split** — obskit is now a collection of focused packages. Each can be installed
  independently, and `pip install obskit` still installs everything as before.

  | Package | Contains |
  |---------|----------|
  | `obskit-core` | config, errors, interfaces, middleware base |
  | `obskit-logging` | structured logging, sampling, debug replay |
  | `obskit-metrics` | RED/Golden/USE metrics, Prometheus, fingerprint |
  | `obskit-tracing` | OpenTelemetry distributed tracing |
  | `obskit-health` | health-check framework |
  | `obskit-resilience` | circuit breaker, load shedding, failover |
  | `obskit-slo` | SLO tracking, alerting rules, error budgets |
  | `obskit-middleware-fastapi` | FastAPI ASGI middleware |
  | `obskit-middleware-flask` | Flask WSGI middleware |
  | `obskit-middleware-django` | Django middleware |
  | `obskit-middleware-grpc` | gRPC server/client interceptors |
  | `obskit` | meta-package (installs all of the above) |

  All existing `from obskit.X import Y` imports continue to work **unchanged** — namespace
  packages are used so Python merges all sub-packages into one `obskit.*` namespace.

- **13 out-of-scope modules removed** — the following modules have been permanently
  deleted because they belong in separate tools, not an observability toolkit:

  | Removed module | Domain |
  |---------------|--------|
  | `obskit.chaos` | Chaos engineering |
  | `obskit.capacity` | Capacity planning |
  | `obskit.compliance_reporter` | Compliance governance |
  | `obskit.compliance.pii` | PII / compliance tooling |
  | `obskit.runbook` | Incident runbooks |
  | `obskit.incident_timeline` | Incident management |
  | `obskit.secrets_detector` | Security scanning |
  | `obskit.feature_flags` | Platform engineering |
  | `obskit.deployment` | Platform engineering |
  | `obskit.resource_predictor` | AIOps / ML |
  | `obskit.root_cause` | AIOps / ML |
  | `obskit.self_healing` | AIOps / ML |
  | `obskit.flamegraph` | Profiling |

- **Build system changed** — sub-packages use `setuptools` (with `namespaces = true`)
  instead of hatchling. No end-user impact; only relevant if building from source.

### Added

- `packages/` directory with 12 independently installable packages.
- `pkgutil.extend_path` in `obskit/__init__.py` and `obskit/middleware/__init__.py`
  to enable namespace-package merging across sub-packages.

### Fixed

- **`ConsumerLagTracker` deadlock** (`packages/obskit-queue/src/obskit/consumer_lag.py`)
  - `get_stats()` held `self._lock` (non-reentrant `threading.Lock`) while calling
    `_calculate_growth_rate()` and `_calculate_velocity()`, which also attempted to
    acquire `self._lock` — causing a permanent deadlock on any `get_stats()` or
    `is_healthy()` call. All 51 consumer-lag tests hung indefinitely before this fix.
  - Fixed by changing `threading.Lock()` to `threading.RLock()` (reentrant lock).

### Migration Guide

```bash
# Before (monolith)
pip install obskit

# After (same — meta-package installs everything)
pip install obskit

# After (focused — only what you need)
pip install obskit-metrics obskit-logging
pip install obskit-middleware-fastapi
```

No import changes required. All `from obskit.X import Y` statements continue to work.

---

## [1.6.1] - 2026-02-27

### Security

- **MD5 — explicit non-security intent** (`alert_dedup.py`, `cache.py`, `fingerprint.py`, `logging/sampling.py`, `query_analyzer.py`)
  - Added `usedforsecurity=False` to all `hashlib.md5()` calls used for fingerprinting/cache-key generation
  - Silences bandit B324 (CWE-327); documents clearly these hashes are not used for cryptographic purposes

- **Health server: default bind address** (`health/server.py`)
  - `start_health_server()` now defaults to `host="127.0.0.1"` instead of `"0.0.0.0"`
  - Prevents `/health`, `/metrics`, and custom handler endpoints from being inadvertently exposed externally
  - Callers who need external binding must now opt-in explicitly

- **Timing-safe token comparison** (`metrics/auth.py`)
  - Replaced `token != self.auth_token` with `hmac.compare_digest()` to prevent timing-based token oracle attacks on the metrics endpoint

- **Thread safety: in-memory cache decorator** (`cache.py`)
  - Added `threading.Lock()` protecting all reads, writes, and deletes on the shared `_cache` dict
  - Eliminates TOCTOU race conditions (check-then-use) in multi-threaded deployments

- **Thread safety: custom health handler registry** (`health/server.py`)
  - `_custom_handlers` is now snapshot under `_server_lock` before dispatch, eliminating the check-then-call race condition

- **PII decorator: silent no-op removed** (`compliance/pii.py`)
  - `@redact_pii_decorator` now emits `UserWarning` at decoration time so callers know it performs no redaction
  - Prevents false confidence in automatic PII masking

- **`FileStorage` hardcoded `/tmp` removed** (`debug/replay.py`)
  - Default path changed from `/tmp/obskit_captures` to `Path(tempfile.gettempdir()) / "obskit_captures"`
  - Cross-platform; avoids world-readable directories on shared Linux systems

### Added

- **`.pre-commit-config.yaml` — bandit severity gate aligned with CI**
  - Bandit pre-commit hook now runs with `-ll` (MEDIUM+ only), matching the CI security job
  - Prevents false failures from the 34 intentional LOW findings (non-crypto `random.random()` for sampling)

- **CI: `security` job** (`.github/workflows/ci.yml`)
  - `bandit -r src/obskit -ll` — SAST gate on every push / PR
  - `pip-audit --desc` — CVE scan of the full dependency tree
  - `pip-licenses --fail-on="GPL-2.0;GPL-3.0;AGPL-3.0"` — copyleft license gate
  - `build` job now requires `security` to pass before packaging

- **Release pipeline: SBOM + Sigstore** (`.github/workflows/release.yml`)
  - `sbom` job generates CycloneDX JSON SBOM via `cyclonedx-py` and attaches it to the GitHub release
  - `publish-pypi` signs `dist/*.whl` and `dist/*.tar.gz` with Sigstore after upload; `.sigstore.json` files are attached to the release
  - `build` job now requires SBOM generation before packaging

- **Dependabot hardened** (`.github/dependabot.yml`)
  - Pip schedule changed from `weekly` to `daily` for faster security-patch delivery
  - Dev/test tooling batched into a single `dev-tooling` group to reduce noise
  - Production core dependencies (`structlog`, `pydantic-settings`, `PyYAML`, `opentelemetry-*`) left ungrouped so each advisory appears as a distinct PR

- **Dev dependencies** (`pyproject.toml`)
  - `pip-licenses>=5.0.0,<7.0.0` — license scanning
  - `cyclonedx-bom>=4.0.0,<6.0.0` — SBOM generation
  - `sigstore>=3.0.0,<4.0.0` — release artifact signing

---

## [1.6.0] - 2026-02-27

### Added

- **`observe` / `observe_sync` context managers** (`obskit.decorators.context_managers`)
  - `observe(...)` — async context manager that also works as an `@observe(...)` decorator on async functions
  - `observe_sync(...)` — sync context manager that also works as an `@observe_sync(...)` decorator on sync functions
  - Both support all standard parameters: `component`, `operation`, `threshold_ms`, `track_metrics`, `log_start`, `sample_rate`, `high_throughput`, plus arbitrary `**context` kwargs
  - Standard path mirrors `with_observability` (correlation context, RED metrics, structured logging)
  - High-throughput path routes through the `_HTPipeline` singleton for ~100 ns overhead
  - When `sample_rate < 1.0`, applies probabilistic sampling gate before pipeline entry

- **`_HTPipeline.configure()` — optional integrations for the HT pipeline** (`obskit.decorators.ht_runtime`)
  - `configure(statsd=..., slo_tracker=...)` — must be called before the first `high_throughput=True` invocation
  - Issues a `RuntimeWarning` if called after the pipeline has already started
  - **StatsD integration**: aggregated request counts and timings are emitted via `emit_counter` / `emit_timing` on every flush cycle (~1 s)
  - **SLO tracker integration**: every `record()` call posts a lock-free measurement to the attached `HighThroughputSLOTracker` (~100 ns overhead)

- **`configure_ht_pipeline()` module-level convenience function** (`obskit.decorators.ht_runtime`)
  - Wraps `_ht_pipeline.configure()` for ergonomic use without importing internal module paths

### Exports

- Added `observe`, `observe_sync`, `with_observability_sync` to top-level `obskit` package
- Added full HT pipeline API to top-level `obskit` package — no internal imports needed:
  - `configure_ht_pipeline` — attach StatsD / SLO tracker before first decorated call
  - `get_ht_pipeline` — access the singleton (e.g. to inspect state in tests)
  - `reset_ht_pipeline` — stop and replace the singleton (test teardown)
  - `StatsDEmitter` — parameter type for `configure_ht_pipeline(statsd=...)`
  - `HighThroughputSLOTracker` — parameter type for `configure_ht_pipeline(slo_tracker=...)`

---

## [1.5.0] - 2026-01-26

### Added

- **SLO Tracking Decorators** (`obskit.slo.tracker`)
  - `with_slo_tracking()` - Flexible decorator for SLO tracking with auto-detection of sync/async
  - `with_slo_tracking_sync()` - Synchronous decorator for SLO tracking
  - `with_slo_tracking_async()` - Asynchronous decorator for SLO tracking
  - Automatically records latency, availability, and error rate measurements
  - Lazy SLO registration on first use

### Exports

- Added `with_slo_tracking`, `with_slo_tracking_sync`, `with_slo_tracking_async` to `obskit.slo` module

---

## [1.4.0] - 2026-01-26

### Added

- **Cardinality Protection** (`obskit.metrics.cardinality`)
  - `CardinalityProtector` class to prevent high-cardinality label explosion
  - `CardinalityConfig` for customizable limits and TTL
  - `LRUCache` thread-safe cache for tracking unique values
  - `get_cardinality_protector()` singleton accessor
  - `protect_label()` and `protect_id()` convenience functions
  - Prometheus metrics: `obskit_cardinality_rejections_total`, `obskit_cardinality_current`, `obskit_cardinality_limit`

- **Sync Circuit Breaker Support** (`obskit.resilience.circuit_breaker`)
  - `with_circuit_breaker_sync()` decorator for sync functions
  - `CircuitBreaker.__enter__` / `__exit__` sync context manager
  - `CircuitBreaker.call_sync()` method for one-off protected calls
  - Internal sync methods: `_should_allow_request_sync()`, `_record_success_sync()`, `_record_failure_sync()`

- **Enhanced Queue Tracking** (`obskit.queue.tracker`)
  - `MessageContext` dataclass for rich business context (message_id, correlation_id, tenant_id, redelivered, etc.)
  - `QueueTracker.track_message()` context manager with mutable context
  - `QueueTracker.track_message_received()` for message receipt tracking
  - `QueueTracker.track_message_acked()` for acknowledgment tracking
  - `QueueTracker.track_message_nacked()` for negative acknowledgment tracking
  - Prometheus metrics: `obskit_queue_messages_received_total`, `obskit_queue_messages_acked_total`, `obskit_queue_messages_nacked_total`

### Fixed

- **Business Metrics `event` Parameter Conflict**
  - Fixed `TypeError: got multiple values for argument 'event'` in `BusinessMetrics.track_event()`
  - Changed log event name from `"business_event"` to `"business_event_tracked"`
  - Renamed log parameter from `event=event` to `event_type=event` to avoid structlog conflict

### Documentation

- Added `docs/source/features/cardinality-protection.md`
- Added `docs/source/features/sync-circuit-breaker.md`
- Added `docs/source/features/queue-tracking.md`

## [1.3.3] - 2026-01-20

### Fixed

- **Critical: Circular Import Bug in obskit.resilience**
  - Fixed circular import that prevented `from obskit.resilience import ...` from working
  - Root cause: `combined.py` and `factory.py` imported from `obskit.resilience` package instead of specific modules
  - Fix: Changed to direct imports from `obskit.resilience.circuit_breaker` and `obskit.resilience.rate_limiter`

- **Critical: ObskitSettings Class Indentation Bug**
  - Fixed class body being defined at module level instead of inside the class
  - This caused `model_fields` to be empty and all settings to fail validation
  - Fix: Corrected indentation of entire class body (lines 234-683)

- **Circular Import Handling in Logging**
  - Added defensive `try/except` for settings access during circular imports
  - Affected: `configure_logging()`, `add_service_info()`, `sample_log()` processors
  - Uses sensible defaults when settings attributes unavailable during import

- **MetricsMethod Import Cycle**
  - Moved `MetricsMethod` enum definition directly into `config.py`
  - Prevents import cycle: `config.py` → `obskit.core.types` → `obskit/__init__.py` → `config.py`

- **Flask Middleware Lazy Initialization**
  - Changed `obskit_flask` singleton to lazy initialization via `get_obskit_flask()`
  - Prevents settings access during module import

## [1.3.2] - 2026-01-20

### Fixed

- **CodeQL Alerts Resolution**
  - Fixed variable redefinition in `root_cause.py` by refactoring to single-assignment pattern
  - Removed unused `_logger` imports in `correlation.py`, `cost.py`, and `errors/responses.py`
  - Removed unused `TYPE_CHECKING` and `CollectorRegistry` imports in `metrics/types.py`
  - Standardized import patterns in test files to avoid import/from-import mixing
  - Fixed Django version check in `test_django.py` to avoid unused variable warnings

- **Import Consistency**
  - `test_self_metrics.py`: Use consistent module import pattern
  - `test_rate_limiter.py`: Use consistent module import pattern
  - `test_logger.py`: Use consistent module import pattern

## [1.3.1] - 2026-01-20

### Fixed

- Minor bug fixes and code quality improvements

## [1.3.0] - 2026-01-19

### 🚀 Major Release - 39 New Features!

This release brings obskit to **52+ total features** for enterprise-grade observability.

### Added - Debugging & Analysis

- **Flame Graph Profiler** (`FlameGraphProfiler`)
  - CPU and memory profiling with visualization
  - SVG and JSON export for flame graphs
  - Integration with py-spy/pyflame

- **Query Plan Analyzer** (`QueryAnalyzer`)
  - SQL query analysis and optimization suggestions
  - Slow query tracking with threshold alerts
  - Query type detection and cost estimation

- **Dependency Graph** (`DependencyGraph`)
  - Service dependency visualization
  - Health status propagation
  - DOT and Mermaid export formats

- **Root Cause Analyzer** (`RootCauseAnalyzer`)
  - Automated incident root cause analysis
  - Anomaly detection with severity levels
  - Contributing factor correlation

- **Error Fingerprinting** (`ErrorFingerprinter`)
  - Automatic error grouping by similarity
  - Stack trace normalization
  - Error occurrence tracking

- **Latency Breakdown** (`LatencyBreakdown`)
  - Phase-by-phase latency analysis
  - Percentage breakdown per phase
  - Automatic performance bottleneck detection

- **Hot Path Detector** (`HotPathDetector`)
  - Identify critical code paths
  - Call frequency and duration tracking
  - Performance optimization suggestions

### Added - Resilience & Reliability

- **Chaos Engineering** (`ChaosEngine`)
  - Latency injection experiments
  - Error injection with probability control
  - Timeout and resource exhaustion simulation
  - Network partition simulation

- **Graceful Degradation** (`DegradationManager`)
  - Feature priority-based degradation
  - Load-based automatic degradation
  - Fallback function support
  - Degradation level metrics

- **Self-Healing** (`SelfHealingEngine`)
  - Automatic remediation triggers
  - Cooldown and rate limiting
  - Execution tracking and metrics
  - Condition-based healing actions

- **Failover Coordinator** (`FailoverCoordinator`)
  - Primary/backup failover management
  - Health check-based automatic failover
  - Manual failover support
  - Failover event tracking

- **Load Shedding** (`LoadShedder`)
  - Priority-based request rejection
  - High/low water mark thresholds
  - Concurrent request tracking
  - Graceful rejection with retry-after

### Added - Performance

- **Adaptive Sampling** (`AdaptiveSampler`)
  - Dynamic trace/log sampling based on load
  - Error rate-based sampling adjustment
  - Configurable sampling strategies

- **Resource Predictor** (`ResourcePredictor`)
  - Predict resource exhaustion
  - Trend analysis and forecasting
  - Capacity planning recommendations

- **Auto-Scaling Metrics** (`AutoScalingMetrics`)
  - Kubernetes HPA metrics provider
  - Custom metric export for scaling
  - Scaling recommendation engine

### Added - Security & Compliance

- **Audit Trail** (`AuditTrail`)
  - Immutable audit logging
  - Chain verification for integrity
  - Query by actor, resource, time range

- **Secrets Detection** (`SecretsDetector`)
  - Detect secrets in logs and data
  - Automatic redaction of API keys, passwords
  - Support for custom secret patterns

- **Compliance Reporter** (`ComplianceReporter`)
  - GDPR compliance checks
  - SOC2 compliance checks
  - HIPAA compliance checks
  - Custom compliance framework support

### Added - Operations

- **Runbook Integration** (`RunbookManager`)
  - Link alerts to runbooks
  - Execution tracking and notes
  - Resolution documentation

- **Incident Timeline** (`IncidentManager`)
  - Build incident timelines
  - Event tracking with sources
  - Post-mortem generation

- **SLA Breach Predictor** (`SLAPredictor`)
  - Predict SLA violations
  - Time to breach estimation
  - Risk assessment and recommendations

- **Capacity Planner** (`CapacityPlanner`)
  - Resource usage tracking
  - Capacity projections (30/90 days)
  - Exhaustion date prediction

- **Alert Deduplication** (`AlertDeduplicator`)
  - Suppress redundant alerts
  - Configurable dedup windows
  - Group-by label support

- **Grafana Annotations** (`GrafanaAnnotator`)
  - Programmatic annotations
  - Deployment markers
  - Incident annotations

### Added - Infrastructure

- **Connection Pool Metrics** (`ConnectionPoolTracker`)
  - Database pool tracking
  - Redis pool tracking
  - RabbitMQ pool tracking
  - Wait time and utilization metrics

- **Dead Letter Queue Tracking** (`DLQTracker`)
  - DLQ message tracking
  - Reason categorization
  - Payload sampling

- **Consumer Lag Tracking** (`ConsumerLagTracker`)
  - Kafka consumer lag
  - RabbitMQ queue depth
  - SQS message age

- **External API SLA Tracking** (`ExternalAPISLATracker`)
  - External API availability
  - Latency P99 tracking
  - SLA compliance reporting

- **Executor Metrics** (`ExecutorTracker`)
  - ThreadPoolExecutor tracking
  - Active/queued task counts
  - Task duration metrics

- **Memory/GC Metrics** (`MemoryTracker`)
  - Heap usage tracking
  - GC collection metrics
  - Object count by type

- **Circuit Breaker Dashboard** (`CircuitBreakerDashboard`)
  - CB state visualization data
  - Multi-breaker overview
  - State change history

- **Distributed Locking** (`DistributedLock`)
  - Redis-based distributed locks
  - Leader election support
  - Lock timeout and extension

- **Tenant Quota Tracking** (`QuotaTracker`)
  - Per-tenant resource quotas
  - Usage tracking and limits
  - Quota period management

### Added - Deployment & Testing

- **Feature Flag Tracker** (`FeatureFlagTracker`)
  - Track flag usage and impact
  - A/B test metrics correlation
  - Flag change tracking

- **Deployment Tracker** (`DeploymentTracker`)
  - Canary deployment metrics
  - Blue-Green deployment tracking
  - Rollback detection

### Added - Documentation

- **Complete Feature Reference** (`docs/FEATURES.md`)
  - All 52+ features documented
  - Code examples for every feature
  - Best practices and configuration

### Changed

- Version bumped to 1.3.0
- README updated with all new features
- Documentation links now use absolute GitHub URLs for PyPI compatibility
- Tech docs updated with feature status tables

---

## [1.2.0] - 2026-01-15

### Added - Infrastructure Monitoring

- Connection Pool Metrics
- DLQ Tracking
- Consumer Lag Tracking
- External API SLA Tracking
- Executor Metrics
- Memory/GC Metrics
- Circuit Breaker Dashboard
- Distributed Locking
- Tenant Quota Tracking
- Error Fingerprinting
- Latency Breakdown

---

## [1.1.0] - 2026-01-10

### Added

- **Async Message Tracing** - Trace context propagation across RabbitMQ, Kafka, SQS
- **Batch Operation Tracking** - Track batch processing with success/failure rates
- **Cache Instrumentation** - Automatic cache hit/miss tracking
- **Business Metrics** - Easy business KPI tracking (conversions, funnels, revenue)
- **Performance Budgets** - Enforce latency/error rate constraints at code level
- **Correlation ID Manager** - Better correlation across async boundaries
- **Dependency Health Aggregator** - Single view of all dependencies' health
- **Smart Log Sampling** - Reduce log volume while keeping important events
- **Grafana Annotations** - Programmatic annotations for deployments/incidents
- **Cost Attribution** - Track resource usage per tenant for billing
- **Schema Validation Metrics** - Track data validation errors structured
- **Adaptive Retry** - Smarter retries that adapt to system load
- **Request Replay** - Capture and replay failed requests for debugging

---

## [1.0.0] - 2026-01-05

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
