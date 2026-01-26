"""
obskit - Production-Ready Observability Kit for Python Microservices
=====================================================================

obskit is a comprehensive observability toolkit that implements industry-standard
monitoring methodologies for Python microservices. It provides a unified interface
for metrics, logging, tracing, health checks, and resilience patterns.

Key Features
------------
- **Metrics**: RED Method, Four Golden Signals, USE Method (Prometheus)
- **Logging**: Structured logging with correlation IDs (structlog)
- **Tracing**: Distributed tracing (OpenTelemetry)
- **Health Checks**: Kubernetes-style endpoints (/health, /ready, /live)
- **Resilience**: Circuit breaker, retry with backoff, rate limiting
- **SLO Tracking**: Service Level Objectives with error budget calculation

Installation
------------
.. code-block:: bash

    # Core package (logging only)
    pip install obskit

    # With Prometheus metrics support
    pip install obskit[metrics]

    # With OpenTelemetry tracing support
    pip install obskit[tracing]

    # Full installation (all features)
    pip install obskit[all]

Quick Start
-----------
.. code-block:: python

    from obskit import configure, with_observability, get_logger

    # Step 1: Configure obskit at application startup
    configure(
        service_name="order-service",
        environment="production",
        log_level="INFO",
        log_format="json",
    )

    # Step 2: Get a logger instance
    logger = get_logger(__name__)

    # Step 3: Use the observability decorator
    @with_observability(component="OrderProcessor", threshold_ms=500.0)
    async def create_order(order_data: dict) -> Order:
        '''
        Create a new order.

        The @with_observability decorator automatically:
        - Logs operation start/completion/failure
        - Records RED metrics (Rate, Errors, Duration)
        - Tracks performance against threshold
        - Propagates correlation IDs
        '''
        logger.info("creating_order", order_id=order_data["id"])
        order = await Order.create(**order_data)
        return order

Metrics Methodologies
---------------------
obskit implements three industry-standard metrics methodologies:

**RED Method** (for services - measures user happiness):
    - **R**ate: Number of requests per second
    - **E**rrors: Number of failed requests
    - **D**uration: Time taken to serve requests

**Four Golden Signals** (extends RED with saturation):
    - Latency: Time to serve requests
    - Traffic: Demand on the system
    - Errors: Rate of failed requests
    - Saturation: How "full" the service is

**USE Method** (for infrastructure - measures machine happiness):
    - **U**tilization: Percentage of time resource is busy
    - **S**aturation: Amount of work resource has queued
    - **E**rrors: Count of error events

Example - Using All Three Methods
---------------------------------
.. code-block:: python

    from obskit.metrics import REDMetrics, GoldenSignals, USEMetrics

    # RED Method for service endpoints
    red = REDMetrics("order_service")
    red.observe_request(
        operation="create_order",
        duration_seconds=0.045,
        status="success",
    )

    # Four Golden Signals for comprehensive monitoring
    golden = GoldenSignals("order_service")
    golden.observe_request("create_order", duration_seconds=0.045)
    golden.set_saturation("cpu", 0.75)  # 75% CPU usage
    golden.set_queue_depth("order_queue", 42)

    # USE Method for infrastructure
    cpu_metrics = USEMetrics("server_cpu")
    cpu_metrics.set_utilization("cpu", 0.65)  # 65% busy
    cpu_metrics.set_saturation("cpu", 3)       # 3 processes waiting
    cpu_metrics.inc_error("cpu", "thermal")    # Thermal throttling event

Resilience Patterns
-------------------
.. code-block:: python

    from obskit.resilience import CircuitBreaker, retry, RateLimiter

    # Circuit Breaker - prevents cascading failures
    breaker = CircuitBreaker(
        name="external_api",
        failure_threshold=5,      # Open after 5 failures
        recovery_timeout=30.0,    # Try recovery after 30 seconds
    )

    async with breaker:
        response = await external_api.call()

    # Retry with exponential backoff
    @retry(max_attempts=3, base_delay=1.0, jitter=True)
    async def fetch_data():
        return await api.get("/data")

    # Rate limiting (100 requests per minute)
    limiter = RateLimiter(requests=100, window_seconds=60)
    if limiter.acquire():
        process_request()

Health Checks
-------------
.. code-block:: python

    from obskit.health import HealthChecker

    checker = HealthChecker()

    # Register readiness checks (is service ready for traffic?)
    @checker.add_readiness_check("database")
    async def check_database():
        return await db.ping()

    @checker.add_readiness_check("cache")
    async def check_cache():
        return await redis.ping()

    # Check health status
    result = await checker.check_health()
    print(f"Status: {result.status}")  # "healthy" or "unhealthy"

Configuration
-------------
Configure via environment variables (prefix: OBSKIT_):

.. code-block:: bash

    export OBSKIT_SERVICE_NAME=order-service
    export OBSKIT_ENVIRONMENT=production
    export OBSKIT_LOG_LEVEL=INFO
    export OBSKIT_LOG_FORMAT=json
    export OBSKIT_METRICS_ENABLED=true
    export OBSKIT_TRACING_ENABLED=true
    export OBSKIT_OTLP_ENDPOINT=http://jaeger:4317

Or programmatically:

.. code-block:: python

    from obskit import configure

    configure(
        service_name="order-service",
        environment="production",
        log_level="INFO",
        log_format="json",
        metrics_enabled=True,
        tracing_enabled=True,
        otlp_endpoint="http://jaeger:4317",
    )

References
----------
- RED Method: https://grafana.com/blog/the-red-method-how-to-instrument-your-services/
- USE Method: https://www.brendangregg.com/usemethod.html
- Four Golden Signals: https://sre.google/sre-book/monitoring-distributed-systems/
- Prometheus Best Practices: https://prometheus.io/docs/practices/naming/

License
-------
MIT License - see LICENSE file for details.

Module Contents
---------------
"""

from typing import Any

# =============================================================================
# Version Information
# =============================================================================
from obskit._version import __version__, __version_info__

# =============================================================================
# Adaptive Sampling (NEW v1.3)
# =============================================================================
from obskit.adaptive_sampling import (
    AdaptiveSampler,
    SamplingConfig,
    SamplingStats,
    get_adaptive_sampler,
)
from obskit.adaptive_sampling import (
    SamplingConfig as AdaptiveSamplingConfig,
)

# =============================================================================
# Alert Deduplication (NEW v1.2)
# =============================================================================
from obskit.alert_dedup import (
    AlertDeduplicator,
    AlertRecord,
    DeduplicationConfig,
    get_alert_deduplicator,
    should_alert,
)

# =============================================================================
# Alerting Rules
# =============================================================================
from obskit.alerts.config import AlertConfig, generate_prometheus_rules

# =============================================================================
# Prometheus Rules Generator
# =============================================================================
from obskit.alerts.rules_generator import (
    generate_alert_rules,
    generate_all_rules,
    generate_recording_rules,
    generate_slo_recording_rules,
    save_rules,
)

# =============================================================================
# Slow Operation Alerting
# =============================================================================
from obskit.alerts.slow_operation import SlowOperationDetector, check_slow_operation

# =============================================================================
# Grafana Annotations
# =============================================================================
from obskit.annotations import (
    Annotation,
    AnnotationSeverity,
    GrafanaAnnotator,
    configure_annotator,
    get_annotator,
)
from obskit.annotations import (
    AnnotationType as GrafanaAnnotationType,
)

# =============================================================================
# Audit Trail (NEW v1.3)
# =============================================================================
from obskit.audit import (
    AuditAction,
    AuditEntry,
    AuditResult,
    AuditTrail,
    get_audit_trail,
)
from obskit.audit import (
    AuditResult as AuditResultType,
)

# =============================================================================
# Auto-Scaling Metrics (NEW v1.3)
# =============================================================================
from obskit.autoscaling import (
    AutoScalingMetrics,
    ScalingConfig,
    ScalingRecommendation,
    get_autoscaling_metrics,
)

# =============================================================================
# Batch Operation Tracking
# =============================================================================
from obskit.batch import (
    BatchContext,
    BatchResult,
    BatchTracker,
    track_batch,
)

# =============================================================================
# Latency Breakdown (NEW v1.2)
# =============================================================================
from obskit.breakdown import (
    BreakdownSummary,
    LatencyBreakdown,
    PhaseRecord,
    track_breakdown,
)

# =============================================================================
# Performance Budgets
# =============================================================================
from obskit.budgets import (
    BudgetManager,
    BudgetStatus,
    PerformanceBudget,
    budget,
    get_budget_manager,
)

# =============================================================================
# Business Metrics
# =============================================================================
from obskit.business import (
    BusinessEvent,
    BusinessMetrics,
    FunnelTracker,
)

# =============================================================================
# Cache Instrumentation
# =============================================================================
from obskit.cache import (
    CacheTracker,
    RedisCacheTracker,
    cached,
)

# =============================================================================
# Capacity Planner (NEW v1.3)
# =============================================================================
from obskit.capacity import (
    CapacityPlan,
    CapacityPlanner,
    CapacityProjection,
    Resource,
    get_capacity_planner,
)
from obskit.capacity import (
    Resource as CapacityResource,
)

# =============================================================================
# Chaos Engineering (NEW v1.3)
# =============================================================================
from obskit.chaos import (
    ChaosEngine,
    ChaosExperiment,
    InjectionType,
    chaos_injection,
    disable_chaos,
    enable_chaos,
    get_chaos_engine,
)

# =============================================================================
# Circuit Breaker Dashboard (NEW v1.2)
# =============================================================================
from obskit.circuit_dashboard import (
    CircuitBreakerDashboard,
    CircuitBreakerStatus,
    CircuitState,
    DashboardData,
    get_all_circuit_states,
    get_circuit_dashboard,
    register_circuit_breaker,
)

# =============================================================================
# Compliance & PII Redaction
# =============================================================================
from obskit.compliance.pii import redact_pii

# =============================================================================
# Compliance Reporter (NEW v1.3)
# =============================================================================
from obskit.compliance_reporter import (
    ComplianceCheck,
    ComplianceFramework,
    ComplianceReport,
    ComplianceReporter,
    get_compliance_reporter,
)

# =============================================================================
# Configuration
# =============================================================================
from obskit.config import configure, get_settings, validate_config
from obskit.config_file import configure_from_file

# =============================================================================
# Consumer Lag Tracking (NEW v1.2)
# =============================================================================
from obskit.consumer_lag import (
    ConsumerLagStats,
    ConsumerLagTracker,
    QueueType,
    get_all_consumer_lag_stats,
    get_consumer_lag_tracker,
)

# Note: These modules use lazy loading to avoid circular imports
# They are loaded on first access via __getattr__
# =============================================================================
# Context Propagation
# =============================================================================
from obskit.core import (
    correlation_context,
    get_correlation_id,
    set_correlation_id,
)

# =============================================================================
# Batch Context Propagation
# =============================================================================
from obskit.core.batch_context import (
    batch_job_context,
    capture_context,
    create_task_with_context,
    get_batch_job_context,
    propagate_to_executor,
    propagate_to_task,
    restore_context,
)

# =============================================================================
# Deprecation Utilities
# =============================================================================
from obskit.core.deprecation import (
    ObskitDeprecationWarning,
    deprecated,
    deprecated_class,
    deprecated_parameter,
    warn_deprecated,
)

# =============================================================================
# Structured Errors
# =============================================================================
from obskit.core.errors import (
    CircuitBreakerError,
    CircuitOpenError,
    ConfigFileNotFoundError,
    ConfigurationError,
    ConfigValidationError,
    HealthCheckError,
    MetricsError,
    ObskitError,
    RateLimitError,
    RateLimitExceeded,
    RetryError,
    SLOError,
    TracingError,
)

# =============================================================================
# Correlation ID Manager
# =============================================================================
from obskit.correlation import (
    CorrelatedTask,
    CorrelationManager,
    create_correlated_task,
    generate_correlation_id,
    with_correlation,
)

# =============================================================================
# Cost Attribution
# =============================================================================
from obskit.cost import (
    CostTracker,
    ResourceUsage,
    track_cost,
)

# =============================================================================
# Dashboard Generator
# =============================================================================
from obskit.dashboards import (
    DashboardBuilder,
    generate_grafana_dashboard,
    generate_red_dashboard,
    generate_slo_dashboard,
)

# =============================================================================
# Database Instrumentation
# =============================================================================
from obskit.db import DatabaseTracker, instrument_sqlalchemy, track_query

# =============================================================================
# Debug / Request Replay
# =============================================================================
from obskit.debug import (
    CapturedRequest,
    FileStorage,
    MemoryStorage,
    RequestCapture,
)

# =============================================================================
# Observability Decorators
# =============================================================================
from obskit.decorators import (
    track_metrics_only,
    track_operation,
    with_observability,
    with_observability_async,
)

# =============================================================================
# Graceful Degradation (NEW v1.3)
# =============================================================================
from obskit.degradation import (
    DegradationLevel,
    DegradationManager,
    DegradationState,
    Feature,
    get_degradation_manager,
)

# =============================================================================
# Dependency Graph (NEW v1.3)
# =============================================================================
from obskit.dependency_graph import (
    DependencyGraph,
    DependencyNode,
    DependencyType,
    GraphVisualization,
    get_dependency_graph,
)
from obskit.dependency_graph import (
    DependencyType as DepGraphDependencyType,
)

# =============================================================================
# Deployment Tracking (NEW v1.3)
# =============================================================================
from obskit.deployment import (
    Deployment,
    DeploymentStatus,
    DeploymentTracker,
    DeploymentType,
    get_deployment_tracker,
)

# =============================================================================
# Dead Letter Queue Metrics (NEW v1.2)
# =============================================================================
from obskit.dlq import (
    DLQMessage,
    DLQReason,
    DLQStats,
    DLQTracker,
    get_all_dlq_stats,
    get_dlq_tracker,
)

# =============================================================================
# Structured Error Responses
# =============================================================================
from obskit.errors import (
    AuthenticationError,
    AuthorizationError,
    ErrorResponse,
    NotFoundError,
    ObservableError,
    ServiceUnavailableError,
    ValidationError,
    create_error_response,
    format_exception,
)

# =============================================================================
# Thread Pool Executor Metrics (NEW v1.2)
# =============================================================================
from obskit.executor import (
    ExecutorStats,
    ExecutorTracker,
    TrackedExecutor,
    create_tracked_executor,
    get_all_executor_stats,
    get_executor_tracker,
    wrap_executor,
)

# =============================================================================
# External API SLA Tracking (NEW v1.2)
# =============================================================================
from obskit.external import (
    ExternalAPISLATracker,
    SLAComplianceReport,
    SLADefinition,
    get_all_api_compliance,
    get_external_api_tracker,
)

# =============================================================================
# Failover Coordinator (NEW v1.3)
# =============================================================================
from obskit.failover import (
    FailoverCoordinator,
    FailoverEvent,
    FailoverState,
    get_failover_coordinator,
)

# =============================================================================
# Feature Flags (NEW v1.3)
# =============================================================================
from obskit.feature_flags import (
    FeatureFlagTracker,
    FlagMetrics,
    get_feature_flag_tracker,
)

# =============================================================================
# Error Fingerprinting (NEW v1.2)
# =============================================================================
from obskit.fingerprint import (
    ErrorFingerprinter,
    ErrorGroup,
    FingerprintResult,
    get_error_fingerprinter,
    get_error_group,
    get_fingerprint,
)

# =============================================================================
# Flame Graph Profiler (NEW v1.3)
# =============================================================================
from obskit.flamegraph import (
    FlameGraphProfiler,
    ProfileResult,
    get_flamegraph_profiler,
    profile_function,
)

# =============================================================================
# Health Checks
# =============================================================================
from obskit.health import (
    HealthCheck,
    HealthChecker,
    LivenessCheck,
    ReadinessCheck,
    create_health_response,
    get_health_checker,
)

# =============================================================================
# HTTP Health Server
# =============================================================================
from obskit.health.server import (
    get_health_server,
    is_health_server_running,
    register_health_endpoint,
    start_health_server,
    stop_health_server,
)

# =============================================================================
# SLO Health Checks
# =============================================================================
from obskit.health.slo_check import (
    SLOReadinessCheck,
    add_slo_readiness_check,
    get_slo_health_status,
)

# =============================================================================
# Hot Path Detector (NEW v1.3)
# =============================================================================
from obskit.hot_path import (
    HotPath,
    HotPathDetector,
    PathStats,
    get_hot_path_detector,
    track_path,
)

# =============================================================================
# Incident Timeline (NEW v1.3)
# =============================================================================
from obskit.incident_timeline import (
    IncidentManager,
    IncidentStatus,
    IncidentTimeline,
    TimelineEvent,
    get_incident_manager,
)

# =============================================================================
# Interfaces (ABCs)
# =============================================================================
from obskit.interfaces import (
    CircuitBreakerInterface,
    HealthCheckerInterface,
    LoggerInterface,
    MetricsInterface,
    TracerInterface,
)

# =============================================================================
# Distributed Locking (NEW v1.2)
# =============================================================================
from obskit.locking import (
    DistributedLock,
    LeaderElection,
    LockInfo,
    create_distributed_lock,
    create_leader_election,
)

# =============================================================================
# Structured Logging
# =============================================================================
from obskit.logging import (
    configure_logging,
    get_logger,
    log_error,
    log_operation,
    log_performance,
)

# =============================================================================
# Pluggable Logging Adapters
# =============================================================================
from obskit.logging.adapters import LoguruAdapter, StructlogAdapter

# =============================================================================
# Dynamic Logging
# =============================================================================
from obskit.logging.dynamic import get_log_level, set_log_level
from obskit.logging.factory import get_logger_from_factory

# =============================================================================
# Memory/GC Metrics (NEW v1.2)
# =============================================================================
from obskit.memory import (
    GCStats,
    MemoryStats,
    MemoryTracker,
    ObjectStats,
    get_memory_tracker,
    start_memory_tracking,
    stop_memory_tracking,
)

# =============================================================================
# Metrics (RED, Golden Signals, USE)
# =============================================================================
from obskit.metrics import (
    GoldenSignals,
    REDMetrics,
    USEMetrics,
    get_registry,
    start_http_server,
)

# =============================================================================
# Cardinality Protection
# =============================================================================
from obskit.metrics.cardinality import (
    CardinalityConfig,
    CardinalityProtector,
    get_cardinality_protector,
    protect_id,
    protect_label,
    reset_cardinality_protector,
)

# =============================================================================
# Async Metrics
# =============================================================================
from obskit.metrics.async_recording import AsyncREDMetrics

# =============================================================================
# OTLP Metrics Export
# =============================================================================
from obskit.metrics.otlp import OTLPMetricsExporter

# =============================================================================
# Metrics Presets
# =============================================================================
from obskit.metrics.presets import (
    API_SERVICE_BUCKETS,
    BATCH_SERVICE_BUCKETS,
    DATABASE_SERVICE_BUCKETS,
    DEFAULT_BUCKETS,
    FAST_SERVICE_BUCKETS,
)

# =============================================================================
# Prometheus Pushgateway
# =============================================================================
from obskit.metrics.pushgateway import PushgatewayExporter
from obskit.metrics.red import get_red_metrics

# =============================================================================
# Tenant Metrics
# =============================================================================
# =============================================================================
# Enhanced Tenant Context
# =============================================================================
from obskit.metrics.tenant import (
    TenantREDMetrics,
    extract_tenant_from_params,
    get_tenant_id,
    set_tenant_id,
    tenant_context,
    tenant_metrics_context,
    with_tenant,
)

# =============================================================================
# Request Context Middleware
# =============================================================================
from obskit.middleware import (
    ASGIMiddleware,
    BaseMiddleware,
    ObskitMiddleware,
    WSGIMiddleware,
    extract_context_from_headers,
    inject_context_to_headers,
)

# =============================================================================
# Observability Mixin
# =============================================================================
from obskit.mixin import ObservabilityMixin, create_service_mixin

# =============================================================================
# Connection Pool Metrics (NEW v1.2)
# =============================================================================
from obskit.pools import (
    ConnectionPoolTracker,
    PoolStats,
    PoolType,
    check_all_pools_healthy,
    get_all_pool_stats,
    get_pool_tracker,
    wrap_psycopg2_pool,
    wrap_redis_pool,
)

# =============================================================================
# Query Plan Analyzer (NEW v1.3)
# =============================================================================
from obskit.query_analyzer import (
    QueryAnalysis,
    QueryAnalyzer,
    QueryType,
    get_query_analyzer,
)

# =============================================================================
# Queue Instrumentation
# =============================================================================
from obskit.queue import MessageContext, QueueTracker, track_message_processing

# =============================================================================
# Tenant Quota Tracking (NEW v1.2)
# =============================================================================
from obskit.quota import (
    QuotaLimit,
    QuotaPeriod,
    QuotaReport,
    QuotaTracker,
    TenantUsage,
    get_quota_tracker,
)

# =============================================================================
# Resilience Patterns
# =============================================================================
from obskit.resilience import (
    # Circuit Breaker
    CircuitBreaker,
    # Rate Limiting
    RateLimiter,
    # Retry
    RetryConfig,
    SlidingWindowRateLimiter,
    TokenBucketRateLimiter,
    retry,
    retry_async,
    # Sync Circuit Breaker decorator
    with_circuit_breaker_sync,
)

# =============================================================================
# Combined Resilience (Retry + Circuit Breaker)
# =============================================================================
from obskit.resilience.combined import (
    BackoffStrategy,
    ResilientExecutor,
    resilient_call,
    resilient_call_sync,
    with_resilience,
)

# =============================================================================
# Distributed Circuit Breaker
# =============================================================================
from obskit.resilience.distributed import DistributedCircuitBreaker

# =============================================================================
# Resilience Factory
# =============================================================================
from obskit.resilience.factory import (
    CircuitBreakerPreset,
    RateLimiterPreset,
    get_circuit_breaker,
    get_rate_limiter,
)

# =============================================================================
# Resource Predictor (NEW v1.3)
# =============================================================================
from obskit.resource_predictor import (
    Forecast,
    ResourcePredictor,
    TrendAnalysis,
    get_resource_predictor,
)

# =============================================================================
# Root Cause Analyzer (NEW v1.3)
# =============================================================================
from obskit.root_cause import (
    Anomaly,
    AnomalySeverity,
    RootCauseAnalyzer,
    RootCauseResult,
    get_root_cause_analyzer,
)

# =============================================================================
# Runbook Integration (NEW v1.3)
# =============================================================================
from obskit.runbook import (
    Runbook,
    RunbookExecution,
    RunbookManager,
    get_runbook_manager,
)

# =============================================================================
# Secrets Detection (NEW v1.3)
# =============================================================================
from obskit.secrets_detector import (
    DetectionResult,
    SecretsDetector,
    SecretType,
    get_secrets_detector,
    redact_secrets,
    scan_for_secrets,
)

# =============================================================================
# Self-Healing (NEW v1.3)
# =============================================================================
from obskit.self_healing import (
    HealingResult,
    HealingTrigger,
    SelfHealingEngine,
    get_self_healing_engine,
)

# =============================================================================
# Load Shedding (NEW v1.2)
# =============================================================================
from obskit.shedding import (
    LoadShedder,
    Priority,
    SheddingConfig,
    SheddingStats,
    get_load_shedder,
)

# =============================================================================
# Shutdown Management
# =============================================================================
from obskit.shutdown import (
    GracefulShutdown,
    get_graceful_shutdown,
    register_shutdown_hook,
    shutdown,
)

# =============================================================================
# SLA Breach Predictor (NEW v1.3)
# =============================================================================
from obskit.sla_predictor import (
    RiskAssessment,
    SLAPredictor,
    get_sla_predictor,
)

# =============================================================================
# SLO Alertmanager Integration
# =============================================================================
from obskit.slo.alertmanager import AlertmanagerWebhook, SyncAlertmanagerWebhook

# =============================================================================
# Observability Annotations (decorators)
# =============================================================================
# Note: These decorators are defined in the decorators module
# The observable, traced, metered, slo, circuit_breaker, rate_limited, observed
# decorators are provided through the @with_observability decorator pattern
# =============================================================================
# SLO Prometheus Integration
# =============================================================================
from obskit.slo.prometheus import expose_slo_metrics, update_slo_metrics

# =============================================================================
# Testing Utilities
# =============================================================================
from obskit.testing import (
    MockCircuitBreaker,
    MockHealthChecker,
    MockMetrics,
    MockSLOTracker,
    MockTracer,
    ObskitTestCase,
    ObskitTestContext,
    disable_observability,
    mock_observability,
)

# =============================================================================
# Tracing (enhanced exports)
# =============================================================================
from obskit.tracing.tracer import (
    extract_trace_context,
    inject_trace_context,
    trace_context,
)
from obskit.validation import (
    ValidationError as SchemaValidationError,
)

# =============================================================================
# Schema Validation
# =============================================================================
from obskit.validation import (
    ValidationException,
    ValidationResult,
    ValidationTracker,
    validate_range,
    validate_required,
    validate_type,
)

# Try to import optional queue instrumentation
_queue_instrumentation: list[str] = []
try:
    from obskit.queue import instrument_kafka, instrument_rabbitmq

    _queue_instrumentation = ["instrument_rabbitmq", "instrument_kafka"]
except ImportError:
    # Queue instrumentation is optional - kafka-python/rabbitmq dependencies not installed
    pass

# Try to import optional Flask middleware
_flask_middleware: list[str] = []
try:
    from obskit.middleware.flask import ObskitFlaskMiddleware

    _flask_middleware = ["ObskitFlaskMiddleware"]
except ImportError:
    # Flask middleware is optional - Flask dependency not installed
    pass

# Try to import optional Django middleware
_django_middleware: list[str] = []
try:
    from obskit.middleware.django import ObskitDjangoMiddleware

    _django_middleware = ["ObskitDjangoMiddleware"]
except ImportError:
    # Django middleware is optional - Django dependency not installed
    pass

# =============================================================================
# Public API - All exported symbols
# =============================================================================
__all__ = [
    # -------------------------------------------------------------------------
    # Version
    # -------------------------------------------------------------------------
    "__version__",
    "__version_info__",
    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    "configure",
    "configure_from_file",
    "get_settings",
    "validate_config",
    # -------------------------------------------------------------------------
    # Context Propagation
    # -------------------------------------------------------------------------
    "correlation_context",
    "get_correlation_id",
    "set_correlation_id",
    # -------------------------------------------------------------------------
    # Decorators
    # -------------------------------------------------------------------------
    "with_observability",
    "with_observability_async",
    "track_operation",
    "track_metrics_only",
    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    "get_logger",
    "configure_logging",
    "log_operation",
    "log_performance",
    "log_error",
    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------
    "REDMetrics",
    "GoldenSignals",
    "USEMetrics",
    "get_registry",
    "get_red_metrics",
    "start_http_server",
    # -------------------------------------------------------------------------
    # Cardinality Protection
    # -------------------------------------------------------------------------
    "CardinalityProtector",
    "CardinalityConfig",
    "get_cardinality_protector",
    "reset_cardinality_protector",
    "protect_label",
    "protect_id",
    # -------------------------------------------------------------------------
    # Health Checks
    # -------------------------------------------------------------------------
    "HealthChecker",
    "HealthCheck",
    "ReadinessCheck",
    "LivenessCheck",
    "create_health_response",
    "get_health_checker",
    # -------------------------------------------------------------------------
    # Resilience - Circuit Breaker
    # -------------------------------------------------------------------------
    "CircuitBreaker",
    "with_circuit_breaker_sync",
    # -------------------------------------------------------------------------
    # Resilience - Retry
    # -------------------------------------------------------------------------
    "retry",
    "retry_async",
    "RetryConfig",
    # -------------------------------------------------------------------------
    # Resilience - Rate Limiting
    # -------------------------------------------------------------------------
    "RateLimiter",
    "TokenBucketRateLimiter",
    "SlidingWindowRateLimiter",
    # -------------------------------------------------------------------------
    # Structured Errors (all from core.errors)
    # -------------------------------------------------------------------------
    "ObskitError",
    "ConfigurationError",
    "ConfigFileNotFoundError",
    "ConfigValidationError",
    "CircuitBreakerError",
    "CircuitOpenError",
    "RetryError",
    "RateLimitError",
    "RateLimitExceeded",
    "HealthCheckError",
    "MetricsError",
    "TracingError",
    "SLOError",
    # -------------------------------------------------------------------------
    # Deprecation Utilities
    # -------------------------------------------------------------------------
    "deprecated",
    "deprecated_class",
    "deprecated_parameter",
    "warn_deprecated",
    "ObskitDeprecationWarning",
    # -------------------------------------------------------------------------
    # Batch Context Propagation
    # -------------------------------------------------------------------------
    "capture_context",
    "restore_context",
    "batch_job_context",
    "get_batch_job_context",
    "propagate_to_executor",
    "propagate_to_task",
    "create_task_with_context",
    # -------------------------------------------------------------------------
    # Shutdown Management
    # -------------------------------------------------------------------------
    "shutdown",
    "register_shutdown_hook",
    "GracefulShutdown",
    "get_graceful_shutdown",
    # -------------------------------------------------------------------------
    # Observability Mixin
    # -------------------------------------------------------------------------
    "ObservabilityMixin",
    "create_service_mixin",
    # -------------------------------------------------------------------------
    # Resilience Factory
    # -------------------------------------------------------------------------
    "CircuitBreakerPreset",
    "RateLimiterPreset",
    "get_circuit_breaker",
    "get_rate_limiter",
    # -------------------------------------------------------------------------
    # Slow Operation Alerting
    # -------------------------------------------------------------------------
    "SlowOperationDetector",
    "check_slow_operation",
    # -------------------------------------------------------------------------
    # SLO Health Checks
    # -------------------------------------------------------------------------
    "add_slo_readiness_check",
    "get_slo_health_status",
    "SLOReadinessCheck",
    # -------------------------------------------------------------------------
    # Enhanced Tenant Context
    # -------------------------------------------------------------------------
    "tenant_context",
    "with_tenant",
    "extract_tenant_from_params",
    # -------------------------------------------------------------------------
    # Tracing - Context Propagation
    # -------------------------------------------------------------------------
    "inject_trace_context",
    "extract_trace_context",
    "trace_context",
    # -------------------------------------------------------------------------
    # Compliance
    # -------------------------------------------------------------------------
    "redact_pii",
    # -------------------------------------------------------------------------
    # Metrics Presets
    # -------------------------------------------------------------------------
    "FAST_SERVICE_BUCKETS",
    "API_SERVICE_BUCKETS",
    "DATABASE_SERVICE_BUCKETS",
    "BATCH_SERVICE_BUCKETS",
    "DEFAULT_BUCKETS",
    # -------------------------------------------------------------------------
    # Tenant Metrics
    # -------------------------------------------------------------------------
    "TenantREDMetrics",
    "tenant_metrics_context",
    "get_tenant_id",
    "set_tenant_id",
    # -------------------------------------------------------------------------
    # Async Metrics
    # -------------------------------------------------------------------------
    "AsyncREDMetrics",
    # -------------------------------------------------------------------------
    # Dynamic Logging
    # -------------------------------------------------------------------------
    "set_log_level",
    "get_log_level",
    # -------------------------------------------------------------------------
    # SLO Prometheus
    # -------------------------------------------------------------------------
    "expose_slo_metrics",
    "update_slo_metrics",
    # -------------------------------------------------------------------------
    # Distributed Circuit Breaker
    # -------------------------------------------------------------------------
    "DistributedCircuitBreaker",
    # -------------------------------------------------------------------------
    # Alerting Rules
    # -------------------------------------------------------------------------
    "AlertConfig",
    "generate_prometheus_rules",
    # -------------------------------------------------------------------------
    # Database Instrumentation
    # -------------------------------------------------------------------------
    "DatabaseTracker",
    "instrument_sqlalchemy",
    "track_query",
    # -------------------------------------------------------------------------
    # Queue Instrumentation
    # -------------------------------------------------------------------------
    "QueueTracker",
    "MessageContext",
    "track_message_processing",
    *_queue_instrumentation,
    # -------------------------------------------------------------------------
    # Interfaces (ABCs)
    # -------------------------------------------------------------------------
    "LoggerInterface",
    "MetricsInterface",
    "CircuitBreakerInterface",
    "HealthCheckerInterface",
    "TracerInterface",
    # -------------------------------------------------------------------------
    # Pluggable Logging
    # -------------------------------------------------------------------------
    "get_logger_from_factory",
    "StructlogAdapter",
    "LoguruAdapter",
    # -------------------------------------------------------------------------
    # OTLP Metrics
    # -------------------------------------------------------------------------
    "OTLPMetricsExporter",
    # -------------------------------------------------------------------------
    # Pushgateway
    # -------------------------------------------------------------------------
    "PushgatewayExporter",
    # -------------------------------------------------------------------------
    # Alertmanager
    # -------------------------------------------------------------------------
    "AlertmanagerWebhook",
    "SyncAlertmanagerWebhook",
    # -------------------------------------------------------------------------
    # Framework Middleware (optional)
    # -------------------------------------------------------------------------
    *_flask_middleware,
    *_django_middleware,
    # -------------------------------------------------------------------------
    # HTTP Health Server
    # -------------------------------------------------------------------------
    "start_health_server",
    "stop_health_server",
    "register_health_endpoint",
    "get_health_server",
    "is_health_server_running",
    # -------------------------------------------------------------------------
    # Dashboard Generator
    # -------------------------------------------------------------------------
    "DashboardBuilder",
    "generate_grafana_dashboard",
    "generate_slo_dashboard",
    "generate_red_dashboard",
    # -------------------------------------------------------------------------
    # Prometheus Rules Generator
    # -------------------------------------------------------------------------
    "generate_recording_rules",
    "generate_slo_recording_rules",
    "generate_alert_rules",
    "generate_all_rules",
    "save_rules",
    # -------------------------------------------------------------------------
    # Testing Utilities
    # -------------------------------------------------------------------------
    "MockMetrics",
    "MockTracer",
    "MockSLOTracker",
    "MockHealthChecker",
    "MockCircuitBreaker",
    "disable_observability",
    "mock_observability",
    "ObskitTestContext",
    "ObskitTestCase",
    # -------------------------------------------------------------------------
    # Combined Resilience
    # -------------------------------------------------------------------------
    "ResilientExecutor",
    "resilient_call",
    "resilient_call_sync",
    "with_resilience",
    "BackoffStrategy",
    # -------------------------------------------------------------------------
    # Request Context Middleware
    # -------------------------------------------------------------------------
    "extract_context_from_headers",
    "inject_context_to_headers",
    "BaseMiddleware",
    "ASGIMiddleware",
    "WSGIMiddleware",
    "ObskitMiddleware",
    # -------------------------------------------------------------------------
    # Structured Error Responses
    # -------------------------------------------------------------------------
    "ErrorResponse",
    "ObservableError",
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
    "AuthorizationError",
    "ServiceUnavailableError",
    "create_error_response",
    "format_exception",
    # -------------------------------------------------------------------------
    # Observability Annotations
    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Batch Operation Tracking
    # -------------------------------------------------------------------------
    "BatchTracker",
    "BatchContext",
    "BatchResult",
    "track_batch",
    # -------------------------------------------------------------------------
    # Cache Instrumentation
    # -------------------------------------------------------------------------
    "CacheTracker",
    "RedisCacheTracker",
    "cached",
    # -------------------------------------------------------------------------
    # Business Metrics
    # -------------------------------------------------------------------------
    "BusinessMetrics",
    "BusinessEvent",
    "FunnelTracker",
    # -------------------------------------------------------------------------
    # Performance Budgets
    # -------------------------------------------------------------------------
    "PerformanceBudget",
    "BudgetStatus",
    "BudgetManager",
    "budget",
    "get_budget_manager",
    # -------------------------------------------------------------------------
    # Correlation ID Manager
    # -------------------------------------------------------------------------
    "CorrelationManager",
    "CorrelatedTask",
    "generate_correlation_id",
    "with_correlation",
    "create_correlated_task",
    # -------------------------------------------------------------------------
    # Grafana Annotations
    # -------------------------------------------------------------------------
    "GrafanaAnnotator",
    "Annotation",
    "GrafanaAnnotationType",
    "AnnotationSeverity",
    "configure_annotator",
    "get_annotator",
    # -------------------------------------------------------------------------
    # Cost Attribution
    # -------------------------------------------------------------------------
    "CostTracker",
    "ResourceUsage",
    "track_cost",
    # -------------------------------------------------------------------------
    # Schema Validation
    # -------------------------------------------------------------------------
    "ValidationTracker",
    "ValidationResult",
    "SchemaValidationError",
    "ValidationException",
    "validate_required",
    "validate_type",
    "validate_range",
    # -------------------------------------------------------------------------
    # Debug / Request Replay
    # -------------------------------------------------------------------------
    "RequestCapture",
    "CapturedRequest",
    "FileStorage",
    "MemoryStorage",
    # -------------------------------------------------------------------------
    # Connection Pool Metrics (NEW v1.2)
    # -------------------------------------------------------------------------
    "ConnectionPoolTracker",
    "PoolType",
    "PoolStats",
    "get_pool_tracker",
    "get_all_pool_stats",
    "check_all_pools_healthy",
    "wrap_psycopg2_pool",
    "wrap_redis_pool",
    # -------------------------------------------------------------------------
    # Dead Letter Queue Metrics (NEW v1.2)
    # -------------------------------------------------------------------------
    "DLQTracker",
    "DLQReason",
    "DLQMessage",
    "DLQStats",
    "get_dlq_tracker",
    "get_all_dlq_stats",
    # -------------------------------------------------------------------------
    # External API SLA Tracking (NEW v1.2)
    # -------------------------------------------------------------------------
    "ExternalAPISLATracker",
    "SLADefinition",
    "SLAComplianceReport",
    "get_external_api_tracker",
    "get_all_api_compliance",
    # -------------------------------------------------------------------------
    # Thread Pool Executor Metrics (NEW v1.2)
    # -------------------------------------------------------------------------
    "ExecutorTracker",
    "TrackedExecutor",
    "ExecutorStats",
    "get_executor_tracker",
    "wrap_executor",
    "create_tracked_executor",
    "get_all_executor_stats",
    # -------------------------------------------------------------------------
    # Consumer Lag Tracking (NEW v1.2)
    # -------------------------------------------------------------------------
    "ConsumerLagTracker",
    "QueueType",
    "ConsumerLagStats",
    "get_consumer_lag_tracker",
    "get_all_consumer_lag_stats",
    # -------------------------------------------------------------------------
    # Circuit Breaker Dashboard (NEW v1.2)
    # -------------------------------------------------------------------------
    "CircuitBreakerDashboard",
    "CircuitState",
    "CircuitBreakerStatus",
    "DashboardData",
    "get_circuit_dashboard",
    "register_circuit_breaker",
    "get_all_circuit_states",
    # -------------------------------------------------------------------------
    # Error Fingerprinting (NEW v1.2)
    # -------------------------------------------------------------------------
    "ErrorFingerprinter",
    "ErrorGroup",
    "FingerprintResult",
    "get_error_fingerprinter",
    "get_error_group",
    "get_fingerprint",
    # -------------------------------------------------------------------------
    # Latency Breakdown (NEW v1.2)
    # -------------------------------------------------------------------------
    "LatencyBreakdown",
    "PhaseRecord",
    "BreakdownSummary",
    "track_breakdown",
    # -------------------------------------------------------------------------
    # Distributed Locking (NEW v1.2)
    # -------------------------------------------------------------------------
    "DistributedLock",
    "LeaderElection",
    "LockInfo",
    "create_distributed_lock",
    "create_leader_election",
    # -------------------------------------------------------------------------
    # Memory/GC Metrics (NEW v1.2)
    # -------------------------------------------------------------------------
    "MemoryTracker",
    "MemoryStats",
    "GCStats",
    "ObjectStats",
    "start_memory_tracking",
    "stop_memory_tracking",
    "get_memory_tracker",
    # -------------------------------------------------------------------------
    # Alert Deduplication (NEW v1.2)
    # -------------------------------------------------------------------------
    "AlertDeduplicator",
    "AlertRecord",
    "DeduplicationConfig",
    "get_alert_deduplicator",
    "should_alert",
    # -------------------------------------------------------------------------
    # Load Shedding (NEW v1.2)
    # -------------------------------------------------------------------------
    "LoadShedder",
    "Priority",
    "SheddingConfig",
    "SheddingStats",
    "get_load_shedder",
    # -------------------------------------------------------------------------
    # Tenant Quota Tracking (NEW v1.2)
    # -------------------------------------------------------------------------
    "QuotaTracker",
    "QuotaPeriod",
    "QuotaLimit",
    "TenantUsage",
    "QuotaReport",
    "get_quota_tracker",
    # -------------------------------------------------------------------------
    # Flame Graph Profiler (NEW v1.3)
    # -------------------------------------------------------------------------
    "FlameGraphProfiler",
    "ProfileResult",
    "profile_function",
    "get_flamegraph_profiler",
    # -------------------------------------------------------------------------
    # Query Plan Analyzer (NEW v1.3)
    # -------------------------------------------------------------------------
    "QueryAnalyzer",
    "QueryAnalysis",
    "QueryType",
    "get_query_analyzer",
    # -------------------------------------------------------------------------
    # Dependency Graph (NEW v1.3)
    # -------------------------------------------------------------------------
    "DependencyGraph",
    "DependencyNode",
    "DependencyType",
    "GraphVisualization",
    "get_dependency_graph",
    # -------------------------------------------------------------------------
    # Root Cause Analyzer (NEW v1.3)
    # -------------------------------------------------------------------------
    "RootCauseAnalyzer",
    "RootCauseResult",
    "Anomaly",
    "AnomalySeverity",
    "get_root_cause_analyzer",
    # -------------------------------------------------------------------------
    # Chaos Engineering (NEW v1.3)
    # -------------------------------------------------------------------------
    "ChaosEngine",
    "ChaosExperiment",
    "InjectionType",
    "chaos_injection",
    "get_chaos_engine",
    "enable_chaos",
    "disable_chaos",
    # -------------------------------------------------------------------------
    # Failover Coordinator (NEW v1.3)
    # -------------------------------------------------------------------------
    "FailoverCoordinator",
    "FailoverState",
    "FailoverEvent",
    "get_failover_coordinator",
    # -------------------------------------------------------------------------
    # Graceful Degradation (NEW v1.3)
    # -------------------------------------------------------------------------
    "DegradationManager",
    "DegradationLevel",
    "DegradationState",
    "Feature",
    "get_degradation_manager",
    # -------------------------------------------------------------------------
    # Self-Healing (NEW v1.3)
    # -------------------------------------------------------------------------
    "SelfHealingEngine",
    "HealingTrigger",
    "HealingResult",
    "get_self_healing_engine",
    # -------------------------------------------------------------------------
    # Adaptive Sampling (NEW v1.3)
    # -------------------------------------------------------------------------
    "AdaptiveSampler",
    "SamplingConfig",
    "SamplingStats",
    "get_adaptive_sampler",
    # -------------------------------------------------------------------------
    # Hot Path Detector (NEW v1.3)
    # -------------------------------------------------------------------------
    "HotPathDetector",
    "HotPath",
    "PathStats",
    "track_path",
    "get_hot_path_detector",
    # -------------------------------------------------------------------------
    # Resource Predictor (NEW v1.3)
    # -------------------------------------------------------------------------
    "ResourcePredictor",
    "Forecast",
    "TrendAnalysis",
    "get_resource_predictor",
    # -------------------------------------------------------------------------
    # Auto-Scaling Metrics (NEW v1.3)
    # -------------------------------------------------------------------------
    "AutoScalingMetrics",
    "ScalingRecommendation",
    "ScalingConfig",
    "get_autoscaling_metrics",
    # -------------------------------------------------------------------------
    # Audit Trail (NEW v1.3)
    # -------------------------------------------------------------------------
    "AuditTrail",
    "AuditEntry",
    "AuditAction",
    "AuditResult",
    "get_audit_trail",
    # -------------------------------------------------------------------------
    # Secrets Detection (NEW v1.3)
    # -------------------------------------------------------------------------
    "SecretsDetector",
    "DetectionResult",
    "SecretType",
    "redact_secrets",
    "scan_for_secrets",
    "get_secrets_detector",
    # -------------------------------------------------------------------------
    # Compliance Reporter (NEW v1.3)
    # -------------------------------------------------------------------------
    "ComplianceReporter",
    "ComplianceReport",
    "ComplianceFramework",
    "ComplianceCheck",
    "get_compliance_reporter",
    # -------------------------------------------------------------------------
    # Runbook Integration (NEW v1.3)
    # -------------------------------------------------------------------------
    "RunbookManager",
    "Runbook",
    "RunbookExecution",
    "get_runbook_manager",
    # -------------------------------------------------------------------------
    # Incident Timeline (NEW v1.3)
    # -------------------------------------------------------------------------
    "IncidentTimeline",
    "IncidentManager",
    "IncidentStatus",
    "TimelineEvent",
    "get_incident_manager",
    # -------------------------------------------------------------------------
    # SLA Breach Predictor (NEW v1.3)
    # -------------------------------------------------------------------------
    "SLAPredictor",
    "RiskAssessment",
    "get_sla_predictor",
    # -------------------------------------------------------------------------
    # Capacity Planner (NEW v1.3)
    # -------------------------------------------------------------------------
    "CapacityPlanner",
    "CapacityPlan",
    "CapacityProjection",
    "Resource",
    "get_capacity_planner",
    # -------------------------------------------------------------------------
    # Feature Flags (NEW v1.3)
    # -------------------------------------------------------------------------
    "FeatureFlagTracker",
    "FlagMetrics",
    "get_feature_flag_tracker",
    # -------------------------------------------------------------------------
    # Deployment Tracking (NEW v1.3)
    # -------------------------------------------------------------------------
    "DeploymentTracker",
    "Deployment",
    "DeploymentType",
    "DeploymentStatus",
    "get_deployment_tracker",
]


# =============================================================================
# Lazy Loading for Circular Import Prevention
# =============================================================================


def __getattr__(name: str) -> Any:
    """
    Lazy load modules that might cause circular imports.

    This pattern allows us to export these symbols in __all__ while
    avoiding circular import issues at module load time.
    """
    # Configuration file loading
    if name == "configure_from_file":
        from obskit.config_file import configure_from_file

        return configure_from_file

    # Structured error codes
    error_names = {
        "ObskitError",
        "ConfigurationError",
        "ConfigFileNotFoundError",
        "ConfigValidationError",
        "CircuitBreakerError",
        "CircuitOpenError",
        "RetryError",
        "RateLimitError",
        "RateLimitExceeded",
        "HealthCheckError",
        "MetricsError",
        "TracingError",
        "SLOError",
    }
    if name in error_names:
        from obskit.core import errors

        return getattr(errors, name)

    # Deprecation utilities
    deprecation_names = {
        "deprecated",
        "deprecated_class",
        "deprecated_parameter",
        "warn_deprecated",
        "ObskitDeprecationWarning",
    }
    if name in deprecation_names:
        from obskit.core import deprecation

        return getattr(deprecation, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
