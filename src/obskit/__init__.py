"""obskit — production-ready observability toolkit for Python microservices."""

from obskit._version import __version__, __version_info__

# ── Configuration ──────────────────────────────────────────────────────────
from obskit.config import ObskitSettings, configure, get_settings

# ── Health ─────────────────────────────────────────────────────────────────
from obskit.health.checker import HealthCheck, HealthChecker

# ── Logging ────────────────────────────────────────────────────────────────
from obskit.logging import get_logger
from obskit.logging.logger import configure_logging, reset_logging
from obskit.logging.redaction import make_redaction_processor, redact_sensitive_fields
from obskit.metrics.multiprocess import (
    child_exit,
    is_multiprocess_mode,
    make_multiprocess_app,
    setup_multiprocess_registry,
)

# ── Metrics ────────────────────────────────────────────────────────────────
from obskit.metrics.red import REDMetrics, get_red_metrics
from obskit.metrics.registry import (
    generate_latest,
    get_registry,
    start_http_server,
    stop_http_server,
)
from obskit.resilience.rate_limiter import RateLimiter

# ── Resilience ─────────────────────────────────────────────────────────────
from obskit.resilience.retry import retry, retry_sync

# ── Tracing ────────────────────────────────────────────────────────────────
from obskit.tracing.tracer import (
    async_trace_span,
    configure_tracing,
    get_tracer,
    inject_trace_context,
    setup_signal_handlers,
    shutdown_tracing,
    trace_operation,
    trace_span,
    tracing_lifespan,
)


# build_health_router requires FastAPI — import lazily so obskit works without it.
def __getattr__(name: str) -> object:
    if name == "build_health_router":
        from obskit.health.router import build_health_router  # noqa: PLC0415

        globals()["build_health_router"] = build_health_router  # cache it
        return build_health_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── Context ────────────────────────────────────────────────────────────────
from obskit.core.context import (
    async_correlation_context,
    correlation_context,
    get_correlation_id,
    set_correlation_id,
)

__all__ = [
    # Version
    "__version__",
    "__version_info__",
    # Configuration
    "ObskitSettings",
    "configure",
    "get_settings",
    # Logging
    "get_logger",
    "configure_logging",
    "reset_logging",
    "make_redaction_processor",
    "redact_sensitive_fields",
    # Tracing
    "configure_tracing",
    "shutdown_tracing",
    "setup_signal_handlers",
    "tracing_lifespan",
    "get_tracer",
    "trace_span",
    "async_trace_span",
    "trace_operation",
    "inject_trace_context",
    # Metrics
    "REDMetrics",
    "get_red_metrics",
    "get_registry",
    "generate_latest",
    "start_http_server",
    "stop_http_server",
    "setup_multiprocess_registry",
    "make_multiprocess_app",
    "is_multiprocess_mode",
    "child_exit",
    # Resilience
    "retry",
    "retry_sync",
    "RateLimiter",
    # Health
    "HealthCheck",
    "HealthChecker",
    "build_health_router",
    # Context
    "get_correlation_id",
    "set_correlation_id",
    "correlation_context",
    "async_correlation_context",
]
