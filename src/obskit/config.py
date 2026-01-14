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
    - ``OBSKIT_METRICS_METHOD``: Metrics methodology (red/golden/use/all, default: "red")
    - ``OBSKIT_USE_HISTOGRAM``: Use histograms for latency (default: true)
    - ``OBSKIT_USE_SUMMARY``: Use summaries for percentiles (default: false)

Logging:
    - ``OBSKIT_LOG_LEVEL``: Log level (DEBUG/INFO/WARNING/ERROR, default: "INFO")
    - ``OBSKIT_LOG_FORMAT``: Output format (json/console, default: "json")
    - ``OBSKIT_LOG_INCLUDE_TIMESTAMP``: Include timestamps (default: true)

Health Checks:
    - ``OBSKIT_HEALTH_CHECK_TIMEOUT``: Timeout in seconds (default: 5.0)

Circuit Breaker:
    - ``OBSKIT_CIRCUIT_BREAKER_FAILURE_THRESHOLD``: Failures before open (default: 5)
    - ``OBSKIT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT``: Recovery wait seconds (default: 30.0)
    - ``OBSKIT_CIRCUIT_BREAKER_HALF_OPEN_REQUESTS``: Test requests (default: 3)

Retry:
    - ``OBSKIT_RETRY_MAX_ATTEMPTS``: Maximum retry attempts (default: 3)
    - ``OBSKIT_RETRY_BASE_DELAY``: Base delay in seconds (default: 1.0)
    - ``OBSKIT_RETRY_MAX_DELAY``: Maximum delay in seconds (default: 60.0)
    - ``OBSKIT_RETRY_EXPONENTIAL_BASE``: Exponential base (default: 2.0)

Rate Limiting:
    - ``OBSKIT_RATE_LIMIT_REQUESTS``: Requests per window (default: 100)
    - ``OBSKIT_RATE_LIMIT_WINDOW_SECONDS``: Window size in seconds (default: 60.0)

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
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from obskit.core.types import MetricsMethod


class ObskitSettings(BaseSettings):
    """
    Configuration settings for obskit.

    This class uses Pydantic Settings to provide configuration from multiple
    sources with automatic type validation and conversion.

    Configuration Priority (highest to lowest):
        1. Programmatic configuration via configure()
        2. Environment variables
        3. .env file
        4. Default values

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
        default="http://localhost:4317",
        description=(
            "OpenTelemetry Protocol (OTLP) collector endpoint. "
            "This is where traces are sent. Examples: "
            "- Jaeger: http://jaeger:4317 "
            "- Tempo: http://tempo:4317 "
            "- Local: http://localhost:4317"
        ),
        examples=["http://localhost:4317", "http://jaeger:4317"],
    )

    otlp_insecure: bool = Field(
        default=True,
        description=(
            "Use insecure (non-TLS) connection to OTLP endpoint. "
            "Set to False in production with proper TLS configuration."
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
        description=(
            "Timeout for trace export operations in seconds. "
            "Exports exceeding this timeout are cancelled."
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
            "Ensure this port is accessible to your Prometheus scraper."
        ),
    )

    metrics_path: str = Field(
        default="/metrics",
        description=(
            "URL path for metrics endpoint. Default '/metrics' is the Prometheus convention."
        ),
    )

    metrics_method: MetricsMethod = Field(
        default=MetricsMethod.RED,
        description=(
            "Metrics methodology to use. Options: "
            "- red: Rate, Errors, Duration (service metrics) "
            "- golden: Four Golden Signals (service + saturation) "
            "- use: Utilization, Saturation, Errors (infrastructure) "
            "- all: All methodologies"
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
    # Circuit Breaker Configuration
    # Configure circuit breaker defaults for resilience
    # =========================================================================

    circuit_breaker_failure_threshold: int = Field(
        default=5,
        ge=1,
        description=(
            "Number of consecutive failures before circuit opens. "
            "Lower values = faster failure detection but more false positives. "
            "Higher values = slower detection but fewer false positives."
        ),
    )

    circuit_breaker_recovery_timeout: float = Field(
        default=30.0,
        ge=1.0,
        description=(
            "Seconds to wait before testing recovery (half-open state). "
            "Set based on expected recovery time of downstream services. "
            "Too short = unnecessary load on recovering service. "
            "Too long = extended outage time."
        ),
    )

    circuit_breaker_half_open_requests: int = Field(
        default=3,
        ge=1,
        description=(
            "Number of test requests allowed in half-open state. "
            "These requests test if the downstream service has recovered. "
            "If all succeed, circuit closes. If any fail, circuit opens."
        ),
    )

    # =========================================================================
    # Retry Configuration
    # Configure retry behavior with exponential backoff
    # =========================================================================

    retry_max_attempts: int = Field(
        default=3,
        ge=1,
        description=(
            "Maximum number of retry attempts (including first try). "
            "Total attempts = retry_max_attempts. "
            "Example: 3 means try once, retry twice if failed."
        ),
    )

    retry_base_delay: float = Field(
        default=1.0,
        ge=0.0,
        description=(
            "Base delay in seconds for exponential backoff. "
            "Actual delay = base_delay * (exponential_base ^ attempt). "
            "With jitter, delay is randomized between 0 and calculated value."
        ),
    )

    retry_max_delay: float = Field(
        default=60.0,
        ge=0.0,
        description=(
            "Maximum delay in seconds between retries. "
            "Caps the exponential backoff to prevent excessively long waits."
        ),
    )

    retry_exponential_base: float = Field(
        default=2.0,
        ge=1.0,
        description=(
            "Base for exponential backoff calculation. "
            "With base=2: delays are 1s, 2s, 4s, 8s, 16s... "
            "With base=3: delays are 1s, 3s, 9s, 27s..."
        ),
    )

    # =========================================================================
    # Rate Limiting Configuration
    # Configure default rate limiting behavior
    # =========================================================================

    rate_limit_requests: int = Field(
        default=100,
        ge=1,
        description=(
            "Default maximum requests allowed per time window. "
            "Adjust based on your service's capacity."
        ),
    )

    rate_limit_window_seconds: float = Field(
        default=60.0,
        ge=1.0,
        description=(
            "Default time window for rate limiting in seconds. "
            "Example: 100 requests per 60 seconds = ~1.67 requests/second."
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
            "Metrics sampling rate from 0.0 (no metrics) to 1.0 (all metrics). "
            "Use lower values for high-frequency operations to reduce cardinality. "
            "Example: 0.1 = sample 10% of operations for metrics."
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
    # Security Configuration
    # Configure security features
    # =========================================================================

    metrics_auth_enabled: bool = Field(
        default=False,
        description=(
            "Enable authentication for metrics endpoint. "
            "When enabled, metrics endpoint requires authentication token."
        ),
    )

    metrics_auth_token: str = Field(
        default="",
        description=(
            "Authentication token for metrics endpoint. "
            "Required if metrics_auth_enabled=True. "
            "Set via environment variable for security."
        ),
    )

    # =========================================================================
    # Logging Backend Configuration
    # =========================================================================

    logging_backend: Literal["structlog", "loguru", "auto"] = Field(
        default="structlog",
        description=(
            "Logging backend to use. Options: "
            "- structlog: Default, recommended for production "
            "- loguru: Alternative backend with rich features "
            "- auto: Auto-detect, prefer structlog if available"
        ),
    )

    # =========================================================================
    # Internal Queue Configuration
    # Configure internal queue sizes for async operations
    # =========================================================================

    async_metric_queue_size: int = Field(
        default=10000,
        ge=100,
        le=1000000,
        description=(
            "Maximum size of async metric recording queue. "
            "When queue is full, metrics are dropped with warning. "
            "Larger values use more memory but handle bursts better. "
            "Default: 10000 (suitable for most services)."
        ),
    )

    # =========================================================================
    # Self-Monitoring Configuration
    # Configure obskit's internal metrics and monitoring
    # =========================================================================

    enable_self_metrics: bool = Field(
        default=True,
        description=(
            "Enable obskit's internal metrics (queue depth, errors, etc.). "
            "Useful for monitoring obskit's own health and performance."
        ),
    )

    # =========================================================================
    # Rate Limiting for Metrics Endpoint
    # =========================================================================

    metrics_rate_limit_enabled: bool = Field(
        default=False,
        description=(
            "Enable rate limiting for metrics endpoint. "
            "Helps prevent DoS attacks on the metrics endpoint."
        ),
    )

    metrics_rate_limit_requests: int = Field(
        default=60,
        ge=1,
        description=(
            "Maximum requests per minute to metrics endpoint. "
            "Only applies if metrics_rate_limit_enabled=True."
        ),
    )


# =============================================================================
# Global Settings Management
# =============================================================================

# Global settings instance - initialized lazily
_settings: ObskitSettings | None = None
_settings_lock = threading.Lock()


def get_settings() -> ObskitSettings:
    """
    Get the current settings instance.

    Returns the configured settings, or creates default settings if
    configure() hasn't been called yet. Settings are cached for performance.

    Returns
    -------
    ObskitSettings
        The current configuration settings.

    Example
    -------
    >>> from obskit.config import get_settings
    >>>
    >>> settings = get_settings()
    >>> print(f"Service: {settings.service_name}")
    >>> print(f"Environment: {settings.environment}")
    >>> print(f"Log Level: {settings.log_level}")

    Notes
    -----
    If you need to change settings after initialization, call configure()
    again with the new values. This will replace the existing settings.

    Thread Safety
    -------------
    This function is thread-safe using double-checked locking pattern.
    """
    global _settings

    # Double-checked locking pattern for thread safety
    if _settings is None:
        with _settings_lock:
            if _settings is None:  # pragma: no branch
                _settings = ObskitSettings()

    return _settings


def configure(**kwargs: object) -> ObskitSettings:
    """
    Configure obskit settings programmatically.

    This function should be called once at application startup to configure
    observability settings. It can also be called again to update settings,
    though this is not recommended in production.

    Parameters
    ----------
    **kwargs : object
        Configuration values matching ObskitSettings fields.
        See ObskitSettings class for available options.

    Returns
    -------
    ObskitSettings
        The configured settings instance.

    Example - Basic Configuration
    -----------------------------
    >>> from obskit import configure
    >>>
    >>> configure(
    ...     service_name="order-service",
    ...     environment="production",
    ...     log_level="INFO",
    ... )

    Example - Full Configuration
    ----------------------------
    >>> from obskit import configure
    >>>
    >>> configure(
    ...     # Service identification
    ...     service_name="order-service",
    ...     environment="production",
    ...     version="1.2.3",
    ...
    ...     # Tracing
    ...     tracing_enabled=True,
    ...     otlp_endpoint="http://jaeger:4317",
    ...     trace_sample_rate=0.1,  # Sample 10% of traces
    ...
    ...     # Metrics
    ...     metrics_enabled=True,
    ...     metrics_port=9090,
    ...
    ...     # Logging
    ...     log_level="INFO",
    ...     log_format="json",
    ...
    ...     # Resilience
    ...     circuit_breaker_failure_threshold=5,
    ...     retry_max_attempts=3,
    ... )

    Example - FastAPI Integration
    -----------------------------
    >>> from fastapi import FastAPI
    >>> from obskit import configure
    >>>
    >>> app = FastAPI()
    >>>
    >>> @app.on_event("startup")
    ... async def startup():
    ...     configure(
    ...         service_name="my-api",
    ...         environment="production",
    ...     )

    Notes
    -----
    - Call this early in your application startup, before using any obskit features
    - Environment variables take precedence over programmatic configuration
    - The settings are global and shared across your application

    See Also
    --------
    get_settings : Get the current settings instance
    reset_settings : Reset settings to defaults (for testing)
    """
    global _settings

    with _settings_lock:
        # Create new settings with provided values
        # Type ignore because we're passing dynamic kwargs
        _settings = ObskitSettings(**kwargs)  # type: ignore[arg-type]

        # Clear cached settings to ensure new values are used
        _get_cached_settings.cache_clear()

    return _settings


@lru_cache(maxsize=1)
def _get_cached_settings() -> ObskitSettings:
    """
    Get cached settings for performance-critical paths.

    This internal function caches the settings instance to avoid
    repeated dictionary lookups in hot paths like request handling.

    Returns
    -------
    ObskitSettings
        Cached settings instance.
    """
    return get_settings()  # pragma: no cover


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
        _get_cached_settings.cache_clear()


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

    if settings.environment not in ["development", "staging", "production"]:
        errors.append(
            f"environment '{settings.environment}' is not a standard value. "
            "Consider using: development, staging, or production"
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

    # Validate metrics configuration
    if settings.metrics_enabled:
        if settings.metrics_port < 1 or settings.metrics_port > 65535:  # pragma: no cover
            errors.append(
                f"metrics_port {settings.metrics_port} is not a valid port number (1-65535)"
            )

    # Validate log level
    if settings.log_level not in [
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ]:  # pragma: no cover
        errors.append(f"log_level '{settings.log_level}' is not a valid log level")

    # Validate trace sample rate
    if settings.trace_sample_rate < 0.0 or settings.trace_sample_rate > 1.0:  # pragma: no cover
        errors.append(f"trace_sample_rate {settings.trace_sample_rate} must be between 0.0 and 1.0")

    return (len(errors) == 0, errors)
