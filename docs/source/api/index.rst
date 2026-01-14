API Reference
=============

This section provides API documentation for obskit modules.

.. note::

   Full API documentation is auto-generated from docstrings. 
   For the most up-to-date API reference, use Python's built-in help::

       import obskit
       help(obskit)
       help(obskit.get_red_metrics)

Main Module
-----------

The main ``obskit`` module provides convenience imports for common functionality.

.. code-block:: python

   from obskit import (
       # Configuration
       configure_logging,
       configure_tracing,
       get_settings,
       validate_config,
       
       # Metrics
       get_red_metrics,
       get_registry,
       start_http_server,
       
       # Health
       get_health_checker,
       
       # Resilience
       CircuitBreaker,
       retry,
       retry_async,
       
       # Logging
       get_logger,
       set_log_level,
       get_log_level,
       
       # Tracing
       get_tracer,
       inject_trace_context,
       extract_trace_context,
       
       # Shutdown
       shutdown,
       register_shutdown_hook,
   )

Module Reference
----------------

obskit.config
~~~~~~~~~~~~~

Configuration management using Pydantic Settings.

**Classes:**

- ``ObskitSettings`` - Main settings class with all configuration options

**Functions:**

- ``get_settings()`` - Get the current settings singleton
- ``configure(settings)`` - Apply new settings
- ``validate_config()`` - Validate current configuration

obskit.metrics
~~~~~~~~~~~~~~

Prometheus-compatible metrics collection.

**Classes:**

- ``REDMetrics`` - Rate, Errors, Duration metrics
- ``GoldenSignals`` - Four Golden Signals metrics
- ``USEMetrics`` - Utilization, Saturation, Errors metrics
- ``TenantREDMetrics`` - Per-tenant RED metrics
- ``AsyncREDMetrics`` - Async metric recording

**Functions:**

- ``get_red_metrics(service_name)`` - Get RED metrics instance
- ``get_registry()`` - Get Prometheus registry
- ``start_http_server(port)`` - Start metrics HTTP server
- ``stop_http_server()`` - Stop metrics HTTP server
- ``reset_registry()`` - Reset metrics registry

obskit.logging
~~~~~~~~~~~~~~

Structured logging with structlog.

**Functions:**

- ``configure_logging(service_name, ...)`` - Configure structured logging
- ``get_logger(name)`` - Get a logger instance
- ``set_log_level(level)`` - Change log level at runtime
- ``get_log_level()`` - Get current log level

obskit.tracing
~~~~~~~~~~~~~~

OpenTelemetry-based distributed tracing.

**Functions:**

- ``configure_tracing(service_name, otlp_endpoint, ...)`` - Configure tracing
- ``get_tracer()`` - Get tracer instance
- ``inject_trace_context(headers)`` - Inject trace context into headers
- ``extract_trace_context(headers)`` - Extract trace context from headers
- ``trace_context(context)`` - Context manager for trace context

obskit.health
~~~~~~~~~~~~~

Kubernetes-style health checks.

**Classes:**

- ``HealthChecker`` - Main health check manager
- ``HealthStatus`` - Health status enum (HEALTHY, UNHEALTHY)

**Functions:**

- ``get_health_checker()`` - Get health checker singleton

obskit.resilience
~~~~~~~~~~~~~~~~~

Fault tolerance patterns.

**Classes:**

- ``CircuitBreaker`` - Circuit breaker pattern
- ``DistributedCircuitBreaker`` - Redis-backed circuit breaker
- ``RateLimiter`` - Token bucket rate limiter
- ``SlidingWindowRateLimiter`` - Sliding window rate limiter
- ``RetryError`` - Raised when retries exhausted

**Functions/Decorators:**

- ``retry(max_attempts, ...)`` - Sync retry decorator
- ``retry_async(max_attempts, ...)`` - Async retry decorator

obskit.slo
~~~~~~~~~~

Service Level Objective tracking.

**Classes:**

- ``SLOTracker`` - Track SLO compliance
- ``SLOStatus`` - SLO status information

**Functions:**

- ``expose_slo_metrics()`` - Expose SLO metrics to Prometheus
- ``update_slo_metrics()`` - Update SLO metrics

obskit.alerts
~~~~~~~~~~~~~

Prometheus alerting rules generation.

**Classes:**

- ``AlertConfig`` - Alert configuration

**Functions:**

- ``generate_prometheus_rules(config)`` - Generate Prometheus alerting rules

obskit.compliance
~~~~~~~~~~~~~~~~~

Data compliance utilities.

**Functions:**

- ``redact_pii(data)`` - Redact PII from data

obskit.middleware
~~~~~~~~~~~~~~~~~

Web framework middleware.

**Classes:**

- ``ObskitMiddleware`` - FastAPI/Starlette middleware

obskit.shutdown
~~~~~~~~~~~~~~~

Graceful shutdown handling.

**Functions:**

- ``shutdown()`` - Perform graceful shutdown
- ``register_shutdown_hook(hook)`` - Register a shutdown hook

Using Help
----------

For detailed API documentation of any function or class:

.. code-block:: python

   from obskit import get_red_metrics
   help(get_red_metrics)
   
   from obskit.resilience import CircuitBreaker
   help(CircuitBreaker)
