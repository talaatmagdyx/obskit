# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
