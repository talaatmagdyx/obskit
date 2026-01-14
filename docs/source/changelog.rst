Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

[Unreleased]
------------

Added
~~~~~

* Database instrumentation (SQLAlchemy)
* Queue instrumentation (RabbitMQ, Kafka)
* Helm charts for Kubernetes deployment
* Comprehensive documentation with Sphinx

[0.1.0] - 2024-01-15
--------------------

Added
~~~~~

* Initial release
* RED Method metrics (Rate, Errors, Duration)
* Golden Signals metrics (Latency, Traffic, Errors, Saturation)
* USE Method metrics (Utilization, Saturation, Errors)
* Structured logging with structlog
* Distributed tracing with OpenTelemetry
* Health checks (liveness/readiness)
* Circuit breaker pattern
* Retry with exponential backoff
* Rate limiting (token bucket, sliding window)
* SLO tracking and error budgets
* PII redaction for logs
* FastAPI middleware
* Multi-tenant metrics support
* Async metric recording
* Prometheus alerting rules generation
* Dynamic log level adjustment
* Metrics endpoint authentication
* Thread-safe singletons
* Graceful shutdown handling
* W3C Trace Context propagation

Fixed
~~~~~

* Thread safety in global singletons
* Metrics HTTP server lifecycle management
* Trace context propagation in async code

Security
~~~~~~~~

* PII redaction enabled by default option
* Metrics endpoint authentication support
* Sensitive data filtering in traces

Documentation
~~~~~~~~~~~~~

* Quick start guide
* User guide with concept explanations
* API reference
* Configuration reference
* Troubleshooting guide
* Performance tuning guide
* Architecture documentation
* Examples for FastAPI, Kubernetes, Helm

