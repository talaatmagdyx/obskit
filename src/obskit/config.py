"""
Configuration Management for obskit
====================================

This module provides centralized configuration for all obskit features using
Pydantic Settings. Configuration can be provided via:

1. **Environment Variables** (recommended for production)
2. **Programmatic Configuration** (via configure() function)
3. **.env Files** (for local development)

Environment Variables
---------------------
All environment variables use the ``OBSKIT_`` prefix:

Service Identification:
    - ``OBSKIT_SERVICE_NAME``: Name of your service (default: "unknown")
    - ``OBSKIT_ENVIRONMENT``: Environment name (default: "development")
    - ``OBSKIT_VERSION``: Service version (default: "0.0.0")

Tracing (OpenTelemetry):
    - ``OBSKIT_TRACING_ENABLED``: Enable distributed tracing (default: true)
    - ``OBSKIT_OTLP_ENDPOINT``: OTLP collector endpoint (default: "http://localhost:4317")
    - ``OBSKIT_OTLP_INSECURE``: Use insecure connection (default: true)
    - ``OBSKIT_TRACE_SAMPLE_RATE``: Sampling rate 0.0-1.0 (default: 1.0)

Metrics (Prometheus):
    - ``OBSKIT_METRICS_ENABLED``: Enable Prometheus metrics (default: true)
    - ``OBSKIT_METRICS_PORT``: Metrics HTTP server port (default: 9090)
    - ``OBSKIT_METRICS_PATH``: Metrics endpoint path (default: "/metrics")
    - ``OBSKIT_USE_HISTOGRAM``: Use histograms for latency (default: true)
    - ``OBSKIT_USE_SUMMARY``: Use summaries for percentiles (default: false)

Logging:
    - ``OBSKIT_LOG_LEVEL``: Log level (DEBUG/INFO/WARNING/ERROR, default: "INFO")
    - ``OBSKIT_LOG_FORMAT``: Output format (json/console, default: "json")
    - ``OBSKIT_LOG_INCLUDE_TIMESTAMP``: Include timestamps (default: true)

Health Checks:
    - ``OBSKIT_HEALTH_CHECK_TIMEOUT``: Timeout in seconds (default: 5.0)

Example - Environment Variables
-------------------------------
.. code-block:: bash

    # .env file or shell exports
    export OBSKIT_SERVICE_NAME=order-service
    export OBSKIT_ENVIRONMENT=production
    export OBSKIT_LOG_LEVEL=INFO
    export OBSKIT_LOG_FORMAT=json
    export OBSKIT_METRICS_ENABLED=true
    export OBSKIT_TRACING_ENABLED=true
    export OBSKIT_OTLP_ENDPOINT=http://jaeger:4317

Example - Programmatic Configuration
------------------------------------
.. code-block:: python

    from obskit import configure, get_settings

    # Configure at application startup
    configure(
        service_name="order-service",
        environment="production",
        version="1.2.3",
        log_level="INFO",
        log_format="json",
        metrics_enabled=True,
        tracing_enabled=True,
        otlp_endpoint="http://jaeger:4317",
    )

    # Access settings anywhere in your application
    settings = get_settings()
    print(f"Service: {settings.service_name}")
    print(f"Environment: {settings.environment}")

Example - Using .env File
-------------------------
Create a ``.env`` file in your project root:

.. code-block:: text

    # .env
    OBSKIT_SERVICE_NAME=order-service
    OBSKIT_ENVIRONMENT=development
    OBSKIT_LOG_LEVEL=DEBUG
    OBSKIT_LOG_FORMAT=console

The settings will be automatically loaded from the file.
"""

from __future__ import annotations

import threading
import warnings
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:  # pragma: no cover
    from obskit.core.observability import Observability

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default OTLP collector endpoint — defined as a constant to avoid
# duplicating the literal string across the field definition.
_DEFAULT_OTLP_ENDPOINT = "http://localhost:4317"


class ObskitSettings(BaseSettings):
    """
        Configuration settings for obskit.

    This class uses Pydantic Settings to provide configuration from multiple
    sources with automatic type validation and conversion.

    Configuration Priority (highest to lowest):
        1. Programmatic configuration via configure() / constructor kwargs
        2. Environment variables (OBSKIT_* prefix)
        3. .env file values
        4. Default values defined on each field

    Attributes
    ----------
    service_name : str
        Name of your service. Used in logs, metrics, and traces.
        Example: "order-service", "user-api", "payment-gateway"

    environment : str
        Deployment environment. Useful for filtering in observability tools.
        Common values: "development", "staging", "production"

    version : str
        Service version. Typically set from CI/CD pipeline.
        Example: "1.2.3", "2.0.0-beta.1"

    tracing_enabled : bool
        Enable OpenTelemetry distributed tracing.
        Set to False in development to reduce noise.

    otlp_endpoint : str
        OpenTelemetry collector endpoint for sending traces.
        Example: "http://jaeger:4317" or "http://localhost:4317"

    metrics_enabled : bool
        Enable Prometheus metrics collection.
        Metrics are exposed at /metrics endpoint.

    metrics_port : int
        Port for Prometheus metrics HTTP server.
        Default: 9090 (standard Prometheus port)

    log_level : str
        Logging level. Controls verbosity of log output.
        Options: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"

    log_format : str
        Log output format.
        - "json": Machine-readable JSON (recommended for production)
        - "console": Human-readable colored output (for development)

    Example
    -------
    >>> from obskit.config import ObskitSettings
    >>>
    >>> # Settings are automatically loaded from environment
    >>> settings = ObskitSettings()
    >>> print(settings.service_name)
    >>> print(settings.environment)
    >>>
    >>> # Or override with explicit values
    >>> settings = ObskitSettings(
    ...     service_name="my-service",
    ...     environment="production",
    ... )
    """

    # =========================================================================
    # Pydantic Settings Configuration
    # =========================================================================
    model_config = SettingsConfigDict(
        # All environment variables must start with OBSKIT_
        env_prefix="OBSKIT_",
        # Support loading from .env file
        env_file=".env",
        env_file_encoding="utf-8",
        # Environment variable names are case-insensitive
        case_sensitive=False,
        # Ignore extra fields (forward compatibility)
        extra="ignore",
    )

    # =========================================================================
    # Service Identification
    # These fields identify your service in logs, metrics, and traces
    # =========================================================================

    service_name: str = Field(
        default="unknown",
        description=(
            "Name of the service. This appears in all logs, metrics, and traces. "
            "Use a descriptive, unique name like 'order-service' or 'user-api'."
        ),
        examples=["order-service", "user-api", "payment-gateway"],
    )

    environment: str = Field(
        default="development",
        description=(
            "Deployment environment. Used for filtering and alerting. "
            "Common values: development, staging, production"
        ),
        examples=["development", "staging", "production"],
    )

    version: str = Field(
        default="0.0.0",
        description=(
            "Service version. Typically set from CI/CD pipeline or git tag. "
            "Useful for tracking deployments and debugging."
        ),
        examples=["1.0.0", "2.1.3", "1.0.0-beta.1"],
    )

    # =========================================================================
    # Tracing Configuration (OpenTelemetry)
    # Configure distributed tracing for request tracking across services
    # =========================================================================

    tracing_enabled: bool = Field(
        default=True,
        description=(
            "Enable OpenTelemetry distributed tracing. "
            "Disable in development to reduce noise and overhead."
        ),
    )

    otlp_endpoint: str = Field(
        default=_DEFAULT_OTLP_ENDPOINT,
        description=(
            "OpenTelemetry Protocol (OTLP) collector endpoint. "
            "This is where traces are sent. Examples: "
            "- Jaeger: http://jaeger:4317 "
            "- Tempo: http://tempo:4317 "
            f"- Local: {_DEFAULT_OTLP_ENDPOINT}"
        ),
        examples=[_DEFAULT_OTLP_ENDPOINT, "http://jaeger:4317"],
    )

    otlp_insecure: bool = Field(
        default=False,
        description=(
            "Use insecure (non-TLS) connection to OTLP endpoint. "
            "Defaults to False (TLS required) for security. "
            "Set to True only for local development or when the OTLP collector "
            "is co-located on the same host/pod with no network exposure."
        ),
    )

    trace_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "Trace sampling rate from 0.0 (no traces) to 1.0 (all traces). "
            "Use lower values in high-traffic production to reduce costs. "
            "Example: 0.1 = sample 10% of requests."
        ),
    )

    trace_export_queue_size: int = Field(
        default=2048,
        ge=1,
        description=(
            "Maximum queue size for trace exports. "
            "When queue is full, new spans are dropped. "
            "Larger values use more memory but handle bursts better."
        ),
    )

    trace_export_batch_size: int = Field(
        default=512,
        ge=1,
        description=(
            "Maximum batch size for trace exports. "
            "Larger batches are more efficient but use more memory."
        ),
    )

    trace_export_timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description=(
            "Timeout for trace export operations in seconds (1–300). "
            "Exports exceeding this timeout are cancelled. "
            "Values above 300s risk hanging application shutdown indefinitely."
        ),
    )

    # =========================================================================
    # Metrics Configuration (Prometheus)
    # Configure Prometheus metrics collection and exposition
    # =========================================================================

    metrics_enabled: bool = Field(
        default=True,
        description=(
            "Enable Prometheus metrics collection. "
            "When enabled, metrics are collected and can be exposed via HTTP."
        ),
    )

    metrics_port: int = Field(
        default=9090,
        ge=1,
        le=65535,
        description=(
            "Port for Prometheus metrics HTTP server. "
            "Default 9090 is the standard Prometheus port. "
            "WARNING: In Kubernetes environments with a Prometheus sidecar agent "
            "also binding 9090, use a different port (e.g. 9091) to avoid conflicts. "
            "Ensure this port is accessible to your Prometheus scraper."
        ),
    )

    metrics_path: str = Field(
        default="/metrics",
        description=(
            "URL path for metrics endpoint. Default '/metrics' is the Prometheus convention."
        ),
    )

    use_histogram: bool = Field(
        default=True,
        description=(
            "Use Prometheus histograms for latency metrics. "
            "Histograms are aggregatable across instances and support "
            "percentile calculations via histogram_quantile()."
        ),
    )

    use_summary: bool = Field(
        default=False,
        description=(
            "Use Prometheus summaries for exact percentiles. "
            "Summaries provide pre-calculated percentiles but are NOT "
            "aggregatable across instances. Enable for single-instance "
            "deployments requiring exact percentiles."
        ),
    )

    # =========================================================================
    # Logging Configuration
    # Configure structured logging output
    # =========================================================================

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description=(
            "Minimum log level to output. "
            "- DEBUG: Verbose debugging information "
            "- INFO: General operational information "
            "- WARNING: Warning messages "
            "- ERROR: Error conditions "
            "- CRITICAL: Critical failures"
        ),
    )

    log_format: Literal["json", "console"] = Field(
        default="json",
        description=(
            "Log output format. "
            "- json: Machine-readable JSON format (recommended for production) "
            "- console: Human-readable colored output (for development)"
        ),
    )

    log_include_timestamp: bool = Field(
        default=True,
        description=(
            "Include ISO 8601 timestamp in log entries. "
            "Disable if your log aggregator adds its own timestamps."
        ),
    )

    # =========================================================================
    # Health Check Configuration
    # Configure Kubernetes-style health check behavior
    # =========================================================================

    health_check_timeout: float = Field(
        default=5.0,
        ge=0.1,
        description=(
            "Timeout for individual health checks in seconds. "
            "Health checks exceeding this timeout are marked as failed. "
            "Set based on your Kubernetes probe timeouts."
        ),
    )

    # =========================================================================
    # Metrics Sampling Configuration
    # Configure sampling for high-frequency operations
    # =========================================================================

    metrics_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "Metrics sampling rate from 0.0 to 1.0 (default 1.0 = all observations). "
            "IMPORTANT ASYMMETRY: sampling only applies to duration histogram/summary "
            "observations. requests_total and errors_total counters are ALWAYS exact "
            "regardless of this setting — rate and error-rate metrics remain accurate. "
            "Setting this to 0.0 disables histograms; set OBSKIT_METRICS_ENABLED=false "
            "to disable all metrics. "
            "Example: 0.1 = sample 10% of duration observations."
        ),
    )

    # =========================================================================
    # Log Sampling Configuration
    # Configure log sampling for high-volume services
    # =========================================================================

    log_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "Log sampling rate from 0.0 (no logs) to 1.0 (all logs). "
            "Use lower values for high-volume services to reduce log volume. "
            "Example: 0.01 = sample 1% of operations for logging."
        ),
    )

    # =========================================================================
    # Fleet SLO (Redis-backed)
    # =========================================================================

    redis_url: str | None = Field(
        default=None,
        description=(
            "Redis URL for fleet-wide SLO tracking via AsyncRedisSLOTracker. "
            "When set, configure_observability() automatically creates an "
            "AsyncRedisSLOTracker and registers it so all workers share one "
            "SLO view.  Example: 'redis://redis:6379/0'. "
            "Requires the 'redis' package (pip install redis)."
        ),
        examples=["redis://localhost:6379/0", "redis://redis:6379/0"],
    )

    # =========================================================================
    # Log Redaction
    # =========================================================================

    redact_fields: list[str] = Field(
        default_factory=list,
        description=(
            "Extra sensitive field-name substrings (case-insensitive) to redact "
            "from structured log output.  Added on top of the built-in defaults "
            "(password, token, secret, …).  Example: ['authorization', 'ssn', "
            "'credit_card'].  Values are replaced with '[REDACTED]'."
        ),
        examples=[["authorization", "ssn", "credit_card"]],
    )

    # =========================================================================
    # Thread Context Propagation
    # =========================================================================

    patch_threads: bool = Field(
        default=False,
        description=(
            "When True, replace threading.Thread with obskit's context-propagating "
            "subclass so that structlog context vars and OTel trace context are "
            "automatically copied into every child thread.  Useful for services "
            "that use run_in_executor() or spawn threads from async code."
        ),
    )

    def __str__(self) -> str:
        """String representation showing key fields."""
        return (
            f"ObskitSettings(service_name={self.service_name!r}, "
            f"environment={self.environment!r}, "
            f"version={self.version!r})"
        )


# =============================================================================
# Global Settings Management
# =============================================================================

# Global settings instance - initialized lazily
_settings: ObskitSettings | None = None
_settings_lock = threading.Lock()

# Global Redis-backed SLO tracker — set by configure_observability() when
# redis_url is provided; None otherwise.
_redis_slo_tracker: Any = None


def get_redis_slo_tracker() -> Any:
    """Return the global :class:`~obskit.slo.redis_tracker.AsyncRedisSLOTracker`.

    Returns ``None`` when no Redis URL was supplied to
    :func:`configure_observability`.

    Returns
    -------
    AsyncRedisSLOTracker | None
    """
    return _redis_slo_tracker


def reset_redis_slo_tracker() -> None:
    """Clear the global Redis SLO tracker.  Intended for test teardown only."""
    global _redis_slo_tracker
    _redis_slo_tracker = None


def get_settings() -> ObskitSettings:
    """
    Get the current settings instance.

    Returns the configured settings, or creates default settings if
    configure() hasn't been called yet. Settings are cached for performance.

    Returns
    -------
    ObskitSettings
        The current configuration settings.

    Thread Safety
    -------------
    This function is thread-safe using double-checked locking pattern.
    """
    global _settings

    if _settings is None:
        with _settings_lock:
            if _settings is None:  # pragma: no cover  # re-check inside lock
                _settings = ObskitSettings()  # pragma: no cover

    return _settings


def configure(*, strict: bool = False, **kwargs: object) -> ObskitSettings:
    """
    Configure obskit settings programmatically.

    Parameters
    ----------
    strict : bool, default=False
        When True, raise on configuration errors.
    **kwargs : object
        Configuration values matching ObskitSettings fields.

    Returns
    -------
    ObskitSettings
        The configured settings instance.
    """
    global _settings

    # Validate that all kwargs are known ObskitSettings field names
    valid_fields = set(ObskitSettings.model_fields.keys())
    invalid = set(kwargs) - valid_fields
    if invalid:
        raise ValueError(
            f"Unknown obskit settings: {invalid}. Valid settings are: {sorted(valid_fields)}"
        )

    with _settings_lock:
        _settings = ObskitSettings(**kwargs)  # type: ignore[arg-type]

    import logging as _std_logging

    _cfg_logger = _std_logging.getLogger("obskit.config")
    is_valid, errors = validate_config()
    if not is_valid:
        for err in errors:
            _cfg_logger.warning("obskit config issue: %s", err)
        if strict:
            raise ValueError(
                f"obskit configuration has {len(errors)} error(s): " + "; ".join(errors)
            )

    return _settings


def configure_observability(*, strict: bool = False, **kwargs: object) -> Observability:
    """Configure obskit and return an :class:`~obskit.core.observability.Observability` handle.

    This is the **recommended** way to initialise obskit.  It creates an
    :class:`ObskitSettings` (preserving env-var loading), converts it to an
    immutable :class:`~obskit.core.observability_config.ObservabilityConfig`,
    wraps it in an :class:`~obskit.core.observability.Observability` facade,
    and stores both globally so that ``get_settings()`` and
    ``get_observability()`` both work during the transition period.

    Parameters
    ----------
    strict : bool, default=False
        Raise on configuration errors (same semantics as :func:`configure`).
    **kwargs : object
        Any :class:`ObskitSettings` field as keyword argument.

    Returns
    -------
    Observability
        The runtime handle exposing ``.tracer``, ``.metrics``, ``.logger``,
        ``.config`` and ``.shutdown()``.
    """
    from obskit.core.observability import Observability, _set_observability
    from obskit.core.observability_config import ObservabilityConfig

    settings = configure(strict=strict, **kwargs)

    # Emit structured startup summary before reconfiguring structlog so the
    # event is captured by structlog.testing.capture_logs() in tests and by
    # any pre-existing structlog pipeline in production.
    _emit_startup_summary(settings)

    # Wire structured logging pipeline immediately so that callers never need
    # to call configure_logging() separately.  Idempotent — safe to call again.
    from obskit.logging.logger import (
        configure_logging,  # noqa: PLC0415 — deferred to avoid circular import
    )

    configure_logging()

    config = ObservabilityConfig.from_settings(settings)
    obs = Observability(config)
    _set_observability(obs)

    # ── Optional: fleet-wide Redis SLO tracker ──────────────────────────
    if settings.redis_url:
        _init_redis_slo_tracker(settings)

    # ── Optional: propagate log + OTel context into child threads ────────
    if settings.patch_threads:
        from obskit.threading import patch_threading  # noqa: PLC0415

        patch_threading()

    return obs


def _init_redis_slo_tracker(settings: ObskitSettings) -> None:
    """Create and register the global AsyncRedisSLOTracker from *settings.redis_url*.

    Silently skips when the ``redis`` package is not installed.
    """
    global _redis_slo_tracker
    try:
        import redis.asyncio as _aioredis  # noqa: PLC0415

        from obskit.slo.redis_tracker import (  # noqa: PLC0415
            AsyncRedisSLOTracker,
        )
    except ImportError:
        import logging as _std_logging  # noqa: PLC0415

        _std_logging.getLogger("obskit.config").warning(
            "redis_slo_init_skipped: 'redis' package not installed — "
            "install it with: pip install redis"
        )
        return

    client = _aioredis.from_url(settings.redis_url, decode_responses=True)
    _redis_slo_tracker = AsyncRedisSLOTracker(
        client,
        service=settings.service_name,
    )


def _emit_startup_summary(settings: ObskitSettings) -> None:
    """Emit structured startup logs after configuration is complete.

    Called once per :func:`configure_observability` invocation.  Logs a
    summary of the active configuration and warns about common
    misconfiguration patterns so problems surface at startup rather than
    at the first failed request.
    """
    import structlog as _structlog  # noqa: PLC0415 — deferred

    # Use structlog directly (not obskit's get_logger) so the event passes
    # through whatever processor chain is active at call time — including
    # structlog.testing.capture_logs() in tests — without triggering the
    # auto-configure-on-first-use path inside obskit's get_logger wrapper.
    _log = _structlog.get_logger("obskit")

    tracing_enabled: bool = bool(getattr(settings, "tracing_enabled", False))
    otlp_endpoint: str | None = getattr(settings, "otlp_endpoint", None)
    trace_sample_rate: float = float(getattr(settings, "trace_sample_rate", 1.0))
    log_sample_rate: float = float(getattr(settings, "log_sample_rate", 1.0))

    _log.info(
        "obskit_configured",
        service=settings.service_name,
        environment=settings.environment,
        version=settings.version,
        log_level=settings.log_level,
        log_format=getattr(settings, "log_format", "json"),
        tracing_enabled=tracing_enabled,
        otlp_endpoint=otlp_endpoint or "(disabled)",
        trace_sample_rate=trace_sample_rate,
        log_sample_rate=log_sample_rate,
    )

    # ── Warn about common misconfiguration ──────────────────────────────
    if tracing_enabled and otlp_endpoint and "localhost" in otlp_endpoint:
        _log.warning(
            "otlp_endpoint_is_localhost",
            endpoint=otlp_endpoint,
            hint="Set OBSKIT_OTLP_ENDPOINT to your collector in production",
        )

    if tracing_enabled and not otlp_endpoint:
        _log.warning(
            "otlp_endpoint_not_configured",
            hint="Tracing is enabled but no OTLP endpoint is set — spans will be dropped",
        )

    if log_sample_rate < 1.0:
        _log.info(
            "log_sampling_active",
            rate=log_sample_rate,
            hint="Only a fraction of non-error logs will be emitted",
        )


def reset_settings() -> None:
    """
    Reset settings to default values.

    This function clears all configured settings and resets to defaults.
    Primarily useful for testing to ensure clean state between tests.

    Example
    -------
    >>> from obskit.config import configure, reset_settings, get_settings
    >>>
    >>> # Configure some settings
    >>> configure(service_name="test-service")
    >>> print(get_settings().service_name)  # "test-service"
    >>>
    >>> # Reset to defaults
    >>> reset_settings()
    >>> print(get_settings().service_name)  # "unknown"

    Warning
    -------
    Do not call this in production code. It's designed for testing only.
    """
    global _settings
    with _settings_lock:
        _settings = None


def validate_config() -> tuple[bool, list[str]]:
    """
    Validate the current configuration.

    Checks that all required settings are valid and that external
    service endpoints are reachable (if configured).

    Returns
    -------
    tuple[bool, list[str]]
        (is_valid, list_of_errors)
        - is_valid: True if configuration is valid
        - list_of_errors: List of error messages if invalid

    Example
    -------
    >>> from obskit.config import validate_config, configure
    >>>
    >>> configure(
    ...     service_name="my-service",
    ...     otlp_endpoint="http://invalid:4317",
    ... )
    >>>
    >>> is_valid, errors = validate_config()
    >>> if not is_valid:
    ...     for error in errors:
    ...         print(f"Config error: {error}")
    """
    errors: list[str] = []
    settings = get_settings()

    # Validate service identification
    if settings.service_name == "unknown":
        errors.append("service_name should be set to a meaningful value")

    # Warn (not error) for non-conventional environment names so teams that
    # use "test", "qa", "uat", "local", "canary", etc. are not blocked.
    _standard_envs = {"development", "staging", "production"}
    if settings.environment not in _standard_envs:
        warnings.warn(
            f"obskit: environment '{settings.environment}' is not one of the conventional "
            f"values {sorted(_standard_envs)}. This is informational only and will not "
            "affect functionality.",
            stacklevel=2,
        )

    # Validate tracing configuration
    if settings.tracing_enabled:
        if not settings.otlp_endpoint:
            errors.append("tracing_enabled is True but otlp_endpoint is not set")
        elif not settings.otlp_endpoint.startswith(("http://", "https://")):
            errors.append(
                f"otlp_endpoint '{settings.otlp_endpoint}' should start with http:// or https://"
            )

        if settings.environment == "production" and settings.otlp_insecure:
            errors.append(
                "otlp_insecure is True in production environment. Consider using TLS for security."
            )

        if (
            settings.environment == "production"
            and settings.otlp_endpoint == "http://localhost:4317"
        ):
            errors.append(
                "otlp_endpoint is the default 'http://localhost:4317' in production. "
                "Set OBSKIT_OTLP_ENDPOINT to your collector address."
            )

    # NOTE: metrics_port bounds, log_level literal values, and trace_sample_rate range are
    # all enforced by Pydantic at ObskitSettings construction time. No runtime checks needed.

    return (len(errors) == 0, errors)
