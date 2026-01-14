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
# Alerting Rules
# =============================================================================
from obskit.alerts.config import AlertConfig, generate_prometheus_rules

# =============================================================================
# Compliance & PII Redaction
# =============================================================================
from obskit.compliance.pii import redact_pii

# =============================================================================
# Configuration
# =============================================================================
from obskit.config import configure, get_settings, validate_config

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
# Database Instrumentation
# =============================================================================
from obskit.db import DatabaseTracker, instrument_sqlalchemy, track_query

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
from obskit.metrics.tenant import (
    TenantREDMetrics,
    get_tenant_id,
    set_tenant_id,
    tenant_metrics_context,
)

# =============================================================================
# Queue Instrumentation
# =============================================================================
from obskit.queue import QueueTracker, track_message_processing

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
)

# =============================================================================
# Distributed Circuit Breaker
# =============================================================================
from obskit.resilience.distributed import DistributedCircuitBreaker

# =============================================================================
# Shutdown Management
# =============================================================================
from obskit.shutdown import register_shutdown_hook, shutdown

# =============================================================================
# SLO Alertmanager Integration
# =============================================================================
from obskit.slo.alertmanager import AlertmanagerWebhook, SyncAlertmanagerWebhook

# =============================================================================
# SLO Prometheus Integration
# =============================================================================
from obskit.slo.prometheus import expose_slo_metrics, update_slo_metrics

# =============================================================================
# Tracing (enhanced exports)
# =============================================================================
from obskit.tracing.tracer import (
    extract_trace_context,
    inject_trace_context,
    trace_context,
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
