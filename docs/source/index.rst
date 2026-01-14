.. obskit documentation master file

obskit Documentation
====================

**obskit** is a production-ready observability toolkit for Python microservices.
It provides unified metrics, tracing, logging, and resilience patterns following
industry best practices.

.. image:: https://img.shields.io/badge/python-3.11%2B-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python 3.11+

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License: MIT

.. image:: https://img.shields.io/badge/coverage-100%25-brightgreen.svg
   :alt: Coverage: 100%

.. image:: https://img.shields.io/badge/code%20style-ruff-000000.svg
   :target: https://github.com/astral-sh/ruff
   :alt: Code style: ruff

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

   from obskit import configure_logging, get_red_metrics, get_health_checker

   # Configure structured logging
   configure_logging(service_name="my-service")

   # Get RED metrics (Rate, Errors, Duration)
   metrics = get_red_metrics(service_name="my-service")

   # Track a request
   with metrics.track_request(endpoint="/api/users", method="GET"):
       # Your business logic here
       pass

   # Health checks
   health = get_health_checker()
   health.add_readiness_check("database", check_database_connection)

Features
--------

.. grid:: 2

   .. grid-item-card:: Metrics
      :link: user-guide/metrics
      :link-type: doc

      RED, Golden Signals, and USE methodologies with Prometheus export.

   .. grid-item-card:: Tracing
      :link: user-guide/tracing
      :link-type: doc

      OpenTelemetry-based distributed tracing with automatic context propagation.

   .. grid-item-card:: Logging
      :link: user-guide/logging
      :link-type: doc

      Structured logging with automatic correlation IDs and PII redaction.

   .. grid-item-card:: Resilience
      :link: user-guide/resilience
      :link-type: doc

      Circuit breakers, retries, and rate limiting for fault tolerance.

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

.. toctree::
   :maxdepth: 2
   :caption: Examples

   examples/fastapi
   examples/kubernetes
   examples/helm

.. toctree::
   :maxdepth: 2
   :caption: Tutorials

   tutorials/index
   tutorials/quickstart
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

