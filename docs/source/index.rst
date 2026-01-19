.. obskit documentation master file

obskit Documentation
====================

**obskit** is a production-ready observability toolkit for Python microservices.
It provides unified metrics, tracing, logging, and resilience patterns following
industry best practices.

.. image:: https://img.shields.io/pypi/v/obskit.svg
   :target: https://pypi.org/project/obskit/
   :alt: PyPI version

.. image:: https://img.shields.io/badge/python-3.11%2B-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python 3.11+

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License: MIT

.. image:: https://img.shields.io/badge/coverage-100%25-brightgreen.svg
   :alt: Coverage: 100%

.. note::

   🎉 **v1.3.0 Released** - 52 comprehensive observability features for enterprise production!

Why obskit?
-----------

Modern microservices need comprehensive observability to:

- **Detect issues quickly** - Know when things go wrong before users report them
- **Debug efficiently** - Trace requests across services with correlated logs
- **Measure reliability** - Track SLOs and error budgets
- **Scale confidently** - Understand resource utilization patterns

obskit provides all of this with minimal configuration.

Quick Example
-------------

.. code-block:: python

   from obskit import configure, get_logger, get_red_metrics
   from obskit.health import get_health_checker
   from obskit.metrics import start_http_server

   # Configure at startup
   configure(
       service_name="my-service",
       environment="production",
       metrics_auth_enabled=True,
       metrics_auth_token="your-secret-token",
   )

   # Structured logging
   logger = get_logger(__name__)
   logger.info("order_created", order_id="123", amount=99.99)

   # RED metrics (Rate, Errors, Duration)
   metrics = get_red_metrics()
   with metrics.track_request(endpoint="/api/orders", method="POST"):
       create_order(data)

   # Health checks
   health = get_health_checker()
   health.add_readiness_check("database", check_database)

   # Start metrics server
   start_http_server(port=9090)

Installation
------------

.. code-block:: bash

   # Core package
   pip install obskit

   # Full installation (recommended)
   pip install obskit[all]

   # Specific features
   pip install obskit[metrics]      # Prometheus
   pip install obskit[tracing]      # OpenTelemetry
   pip install obskit[redis-async]  # Distributed circuit breaker

Features at a Glance
--------------------

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Category
     - Features
   * - **Metrics**
     - RED, Golden Signals, USE, Tenant metrics, OTLP export, Pushgateway
   * - **Logging**
     - Structured (structlog/loguru), PII redaction, Dynamic log levels
   * - **Tracing**
     - OpenTelemetry, W3C context propagation, Adaptive sampling
   * - **Health**
     - Kubernetes probes, SLO-based checks, HTTP server
   * - **Resilience**
     - Circuit breaker (local + distributed), Retry, Rate limiting, Load shedding
   * - **v1.3.0 New**
     - Chaos engineering, Self-healing, Flame graphs, Root cause analysis, Audit trail

Documentation
-------------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   getting-started/installation
   getting-started/quickstart
   getting-started/first-app

.. toctree::
   :maxdepth: 2
   :caption: Features

   features/index
   features/complete-reference

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   user-guide/concepts
   user-guide/metrics
   user-guide/tracing
   user-guide/logging
   user-guide/health-checks
   user-guide/resilience
   user-guide/slo
   user-guide/pii
   user-guide/multi-tenancy
   user-guide/advanced-resilience
   user-guide/debugging
   user-guide/infrastructure

.. toctree::
   :maxdepth: 2
   :caption: Technical Docs

   tech-docs/index
   tech-docs/01_QUICK_START
   tech-docs/02_CONFIGURATION
   tech-docs/03_METRICS
   tech-docs/04_HEALTH_CHECKS
   tech-docs/05_RESILIENCE
   tech-docs/06_SLO_TRACKING
   tech-docs/07_SECURITY
   tech-docs/08_KUBERNETES_DEPLOYMENT
   tech-docs/09_TROUBLESHOOTING

.. toctree::
   :maxdepth: 2
   :caption: Examples & Tutorials

   examples/fastapi
   examples/kubernetes
   examples/helm
   tutorials/index
   tutorials/fastapi-integration
   tutorials/flask-integration
   tutorials/kubernetes-deployment

.. toctree::
   :maxdepth: 2
   :caption: Migration

   migration/index
   migration/from-prometheus
   migration/from-opentelemetry
   migration/from-structlog
   migration/from-datadog

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api/index
   config/index
   troubleshooting/index
   performance/index
   performance/tuning
   performance/benchmarks

.. toctree::
   :maxdepth: 2
   :caption: Architecture

   architecture/overview
   architecture/diagrams

.. toctree::
   :maxdepth: 1
   :caption: Development

   contributing
   changelog

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

