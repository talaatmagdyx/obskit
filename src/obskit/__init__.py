"""obskit — production-ready observability toolkit for Python microservices."""

from obskit._version import __version__, __version_info__
from obskit.core.context import (
    async_correlation_context,
    correlation_context,
    get_correlation_id,
    set_correlation_id,
)

# ── Always-available: logging + context (only structlog + stdlib) ───────────
from obskit.logging import get_logger

# Lazy imports — loaded only on first access, never at import time.
#
# Rule: anything that touches pydantic-settings, prometheus-client, or
# opentelemetry lives here so that `import obskit` and
# `from obskit.logging import get_logger` remain lightweight.

# Module path constants — defined once to avoid repeated literal strings.
_MOD_CONFIG = "obskit.config"
_MOD_OBSERVABILITY = "obskit.core.observability"
_MOD_REGISTRY = "obskit.metrics.registry"
_MOD_TRACER = "obskit.tracing.tracer"
_MOD_INSTRUMENT = "obskit.middleware.instrument"
_MOD_MULTIPROCESS = "obskit.metrics.multiprocess"

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # ── Configuration (pydantic-settings) ────────────────────────────────
    "ObskitSettings": (_MOD_CONFIG, "ObskitSettings"),
    "configure": (_MOD_CONFIG, "configure"),
    "configure_observability": (_MOD_CONFIG, "configure_observability"),
    "get_settings": (_MOD_CONFIG, "get_settings"),
    # ── Observability facade ─────────────────────────────────────────────
    "Observability": (_MOD_OBSERVABILITY, "Observability"),
    "get_observability": (_MOD_OBSERVABILITY, "get_observability"),
    "reset_observability": (_MOD_OBSERVABILITY, "reset_observability"),
    "ObservabilityConfig": ("obskit.core.observability_config", "ObservabilityConfig"),
    # ── Logging helpers (structlog — already a hard dep, but deferred to
    #    keep this __init__ minimal) ────────────────────────────────────
    "configure_logging": ("obskit.logging.logger", "configure_logging"),
    "reset_logging": ("obskit.logging.logger", "reset_logging"),
    "make_redaction_processor": ("obskit.logging.redaction", "make_redaction_processor"),
    "redact_sensitive_fields": ("obskit.logging.redaction", "redact_sensitive_fields"),
    # ── Metrics (prometheus-client) ──────────────────────────────────────
    "REDMetrics": ("obskit.metrics.red", "REDMetrics"),
    "get_red_metrics": ("obskit.metrics.red", "get_red_metrics"),
    "generate_latest": (_MOD_REGISTRY, "generate_latest"),
    "get_registry": (_MOD_REGISTRY, "get_registry"),
    "start_http_server": (_MOD_REGISTRY, "start_http_server"),
    "stop_http_server": (_MOD_REGISTRY, "stop_http_server"),
    # ── Tracing (opentelemetry) ──────────────────────────────────────────
    "async_trace_span": (_MOD_TRACER, "async_trace_span"),
    "configure_tracing": (_MOD_TRACER, "configure_tracing"),
    "get_tracer": (_MOD_TRACER, "get_tracer"),
    "inject_trace_context": (_MOD_TRACER, "inject_trace_context"),
    "setup_signal_handlers": (_MOD_TRACER, "setup_signal_handlers"),
    "shutdown_tracing": (_MOD_TRACER, "shutdown_tracing"),
    "trace_operation": (_MOD_TRACER, "trace_operation"),
    "trace_span": (_MOD_TRACER, "trace_span"),
    "tracing_lifespan": (_MOD_TRACER, "tracing_lifespan"),
    # ── Health (optional extra) ──────────────────────────────────────────
    "HealthCheck": ("obskit.health", "HealthCheck"),
    "HealthChecker": ("obskit.health", "HealthChecker"),
    "build_health_router": ("obskit.health.router", "build_health_router"),
    # ── Framework instrumentation ────────────────────────────────────────
    "instrument_fastapi": (_MOD_INSTRUMENT, "instrument_fastapi"),
    "instrument_flask": (_MOD_INSTRUMENT, "instrument_flask"),
    "instrument_django": (_MOD_INSTRUMENT, "instrument_django"),
    # ── Multiprocess metrics ─────────────────────────────────────────────
    "child_exit": (_MOD_MULTIPROCESS, "child_exit"),
    "is_multiprocess_mode": (_MOD_MULTIPROCESS, "is_multiprocess_mode"),
    "make_multiprocess_app": (_MOD_MULTIPROCESS, "make_multiprocess_app"),
    "setup_multiprocess_registry": (_MOD_MULTIPROCESS, "setup_multiprocess_registry"),
    # ── Log context binding ──────────────────────────────────────────────
    "bind_context": ("obskit.logging.context", "bind_context"),
    "unbind_context": ("obskit.logging.context", "unbind_context"),
    "clear_context": ("obskit.logging.context", "clear_context"),
    "get_context": ("obskit.logging.context", "get_context"),
    # ── Circuit breaker instrumentation ─────────────────────────────────
    "CircuitState": ("obskit.resilience.circuit_breaker", "CircuitState"),
    "ObskitCircuitBreakerListener": (
        "obskit.resilience.circuit_breaker",
        "ObskitCircuitBreakerListener",
    ),
    "instrument_circuit_breaker": (
        "obskit.resilience.circuit_breaker",
        "instrument_circuit_breaker",
    ),
    # ── Fleet SLO (Redis-backed) ─────────────────────────────────────────
    "AsyncRedisSLOTracker": ("obskit.slo.redis_tracker", "AsyncRedisSLOTracker"),
    "get_redis_slo_tracker": (_MOD_CONFIG, "get_redis_slo_tracker"),
    "reset_redis_slo_tracker": (_MOD_CONFIG, "reset_redis_slo_tracker"),
    # ── Gunicorn integration ─────────────────────────────────────────────
    "ObskitGunicornConfig": ("obskit.integrations.gunicorn", "ObskitGunicornConfig"),
    # ── Thread context propagation ───────────────────────────────────────
    "patch_threading": ("obskit.threading", "patch_threading"),
    "reset_threading_patch": ("obskit.threading", "reset_threading_patch"),
    # ── Scoped log context ───────────────────────────────────────────────
    "scoped_context": ("obskit.logging.context", "scoped_context"),
    # ── Redis cache instrumentation ──────────────────────────────────────
    "instrument_redis": ("obskit.integrations.cache", "instrument_redis"),
    # ── Retry worker instrumentation ─────────────────────────────────────
    "instrument_retry_worker": (
        "obskit.integrations.queue.retry_worker",
        "instrument_retry_worker",
    ),
    # ── HTTP client instrumentation ──────────────────────────────────────
    "instrument_httpx": ("obskit.integrations.http", "instrument_httpx"),
    # ── Event handler context decorator ─────────────────────────────────
    "with_event_context": ("obskit.logging.event_context", "with_event_context"),
    # ── Repository instrumentation decorator ─────────────────────────────
    "instrument_repo": ("obskit.decorators.repo", "instrument_repo"),
    # ── Multi-app observability setup ────────────────────────────────────
    "configure_app_observability": (
        "obskit.middleware.instrument",
        "configure_app_observability",
    ),
    # ── Trace exemplars ──────────────────────────────────────────────────
    "observe_with_exemplar": ("obskit.metrics.exemplar", "observe_with_exemplar"),
    "get_trace_exemplar": ("obskit.metrics.exemplar", "get_trace_exemplar"),
    # ── Dead Letter Queue tracking ───────────────────────────────────────
    "DLQTracker": ("obskit.integrations.queue.dlq", "DLQTracker"),
    "DLQReason": ("obskit.integrations.queue.dlq", "DLQReason"),
    "get_dlq_tracker": ("obskit.integrations.queue.dlq", "get_dlq_tracker"),
    # ── SLO readiness check ──────────────────────────────────────────────
    "add_slo_readiness_check": ("obskit.health.slo_check", "add_slo_readiness_check"),
    "get_slo_readiness_check": ("obskit.health.slo_check", "get_slo_readiness_check"),
    # ── W3C baggage context managers ─────────────────────────────────────
    "baggage_context": ("obskit.tracing.baggage", "baggage_context"),
    "async_baggage_context": ("obskit.tracing.baggage", "async_baggage_context"),
    # ── Adaptive sampled logger ──────────────────────────────────────────
    "AdaptiveSampledLogger": ("obskit.logging.sampling", "AdaptiveSampledLogger"),
    # ── RabbitMQ trace context ───────────────────────────────────────────
    "inject_trace_context_to_headers": (
        "obskit.integrations.queue.rabbitmq",
        "inject_trace_context_to_headers",
    ),
    "extract_trace_context_from_headers": (
        "obskit.integrations.queue.rabbitmq",
        "extract_trace_context_from_headers",
    ),
    # ── Span context activation ──────────────────────────────────────────
    "use_span_context": (_MOD_TRACER, "use_span_context"),
    # ── pybreaker integration ────────────────────────────────────────────
    "instrument_pybreaker": (
        "obskit.integrations.resilience.pybreaker",
        "instrument_pybreaker",
    ),
    # ── Rate limiter instrumentation ─────────────────────────────────────
    "instrument_rate_limiter": (
        "obskit.integrations.resilience.rate_limiter",
        "instrument_rate_limiter",
    ),
    # ── Tenacity retry instrumentation ───────────────────────────────────
    "instrument_tenacity": (
        "obskit.integrations.resilience.tenacity",
        "instrument_tenacity",
    ),
    # ── Redis client instrumentation ─────────────────────────────────────
    "instrument_redis_client": (
        "obskit.integrations.cache",
        "instrument_redis_client",
    ),
    # ── Event handler tracing decorator ──────────────────────────────────
    "instrument_event_handler": (
        "obskit.decorators.event_handler",
        "instrument_event_handler",
    ),
    # ── Trace sampling ────────────────────────────────────────────────────
    "configure_trace_sampling": (
        "obskit.tracing.sampling",
        "configure_trace_sampling",
    ),
    # ── Worker health server ──────────────────────────────────────────────
    "WorkerHealthServer": ("obskit.health.server", "WorkerHealthServer"),
}


def __getattr__(name: str) -> object:
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name]
        import importlib  # noqa: PLC0415

        mod = importlib.import_module(module_path)
        value = getattr(mod, attr)
        globals()[name] = value  # cache for subsequent access
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Version
    "__version__",
    "__version_info__",
    # Configuration — new API (preferred)
    "configure_observability",
    "Observability",
    "ObservabilityConfig",
    "get_observability",
    "reset_observability",
    # Configuration — legacy API
    "ObskitSettings",
    "configure",
    "get_settings",
    # Logging
    "get_logger",
    # Tracing
    "get_tracer",
    # Metrics
    "get_red_metrics",
    # Health
    "HealthCheck",
    "HealthChecker",
    "build_health_router",
    # Context
    "get_correlation_id",
    "set_correlation_id",
    "correlation_context",
    "async_correlation_context",
    # Framework instrumentation (lazy)
    "instrument_fastapi",
    "instrument_flask",
    "instrument_django",
    # Multiprocess metrics (lazy — requires prometheus-client)
    "child_exit",
    "is_multiprocess_mode",
    "make_multiprocess_app",
    "setup_multiprocess_registry",
    # Thread context propagation
    "patch_threading",
    "reset_threading_patch",
    # Scoped log context
    "scoped_context",
    # Redis cache instrumentation
    "instrument_redis",
    # Retry worker instrumentation
    "instrument_retry_worker",
    # Fleet SLO (Redis-backed)
    "get_redis_slo_tracker",
    "reset_redis_slo_tracker",
    # HTTP client instrumentation
    "instrument_httpx",
    # Event handler context decorator
    "with_event_context",
    # Repository instrumentation decorator
    "instrument_repo",
    # Multi-app observability setup
    "configure_app_observability",
    # Trace exemplars
    "observe_with_exemplar",
    "get_trace_exemplar",
    # Dead Letter Queue tracking
    "DLQTracker",
    "DLQReason",
    "get_dlq_tracker",
    # SLO readiness check
    "add_slo_readiness_check",
    "get_slo_readiness_check",
    # Adaptive sampled logger
    "AdaptiveSampledLogger",
    # RabbitMQ trace context injection
    "inject_trace_context_to_headers",
    # W3C baggage context managers
    "baggage_context",
    "async_baggage_context",
    # v1.8.0 additions
    "extract_trace_context_from_headers",
    "use_span_context",
    "instrument_pybreaker",
    "instrument_rate_limiter",
    # v1.9.0 additions
    "instrument_tenacity",
    "instrument_redis_client",
    "instrument_event_handler",
    # v2.0.0 additions
    "configure_trace_sampling",
    "WorkerHealthServer",
]
