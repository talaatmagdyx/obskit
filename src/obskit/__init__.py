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
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # ── Configuration (pydantic-settings) ────────────────────────────────
    "ObskitSettings": ("obskit.config", "ObskitSettings"),
    "configure": ("obskit.config", "configure"),
    "configure_observability": ("obskit.config", "configure_observability"),
    "get_settings": ("obskit.config", "get_settings"),
    # ── Observability facade ─────────────────────────────────────────────
    "Observability": ("obskit.core.observability", "Observability"),
    "get_observability": ("obskit.core.observability", "get_observability"),
    "reset_observability": ("obskit.core.observability", "reset_observability"),
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
    "generate_latest": ("obskit.metrics.registry", "generate_latest"),
    "get_registry": ("obskit.metrics.registry", "get_registry"),
    "start_http_server": ("obskit.metrics.registry", "start_http_server"),
    "stop_http_server": ("obskit.metrics.registry", "stop_http_server"),
    # ── Tracing (opentelemetry) ──────────────────────────────────────────
    "async_trace_span": ("obskit.tracing.tracer", "async_trace_span"),
    "configure_tracing": ("obskit.tracing.tracer", "configure_tracing"),
    "get_tracer": ("obskit.tracing.tracer", "get_tracer"),
    "inject_trace_context": ("obskit.tracing.tracer", "inject_trace_context"),
    "setup_signal_handlers": ("obskit.tracing.tracer", "setup_signal_handlers"),
    "shutdown_tracing": ("obskit.tracing.tracer", "shutdown_tracing"),
    "trace_operation": ("obskit.tracing.tracer", "trace_operation"),
    "trace_span": ("obskit.tracing.tracer", "trace_span"),
    "tracing_lifespan": ("obskit.tracing.tracer", "tracing_lifespan"),
    # ── Health (optional extra) ──────────────────────────────────────────
    "HealthCheck": ("obskit.health", "HealthCheck"),
    "HealthChecker": ("obskit.health", "HealthChecker"),
    "build_health_router": ("obskit.health.router", "build_health_router"),
    # ── Framework instrumentation ────────────────────────────────────────
    "instrument_fastapi": ("obskit.middleware.instrument", "instrument_fastapi"),
    "instrument_flask": ("obskit.middleware.instrument", "instrument_flask"),
    "instrument_django": ("obskit.middleware.instrument", "instrument_django"),
    # ── Multiprocess metrics ─────────────────────────────────────────────
    "child_exit": ("obskit.metrics.multiprocess", "child_exit"),
    "is_multiprocess_mode": ("obskit.metrics.multiprocess", "is_multiprocess_mode"),
    "make_multiprocess_app": ("obskit.metrics.multiprocess", "make_multiprocess_app"),
    "setup_multiprocess_registry": ("obskit.metrics.multiprocess", "setup_multiprocess_registry"),
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
]
