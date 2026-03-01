"""
Histogram Bucket Presets for Common Scenarios
==============================================

This module provides pre-configured histogram bucket sets for different
types of services and latency requirements.

Example - Fast Service (Sub-100ms)
----------------------------------
.. code-block:: python

    from obskit.metrics import REDMetrics
    from obskit.metrics.presets import FAST_SERVICE_BUCKETS

    red = REDMetrics("cache_service", histogram_buckets=FAST_SERVICE_BUCKETS)

Example - API Service (100ms-1s)
--------------------------------
.. code-block:: python

    from obskit.metrics.presets import API_SERVICE_BUCKETS

    red = REDMetrics("api_service", histogram_buckets=API_SERVICE_BUCKETS)

Example - Batch Processing (Seconds to Minutes)
-----------------------------------------------
.. code-block:: python

    from obskit.metrics.presets import BATCH_SERVICE_BUCKETS

    red = REDMetrics("batch_processor", histogram_buckets=BATCH_SERVICE_BUCKETS)
"""

from __future__ import annotations

# =============================================================================
# Fast Service Buckets (Sub-100ms operations)
# =============================================================================
# For services with strict latency requirements:
# - Cache lookups
# - In-memory operations
# - Fast database queries
# - Real-time analytics

FAST_SERVICE_BUCKETS: tuple[float, ...] = (
    0.001,  # 1ms
    0.005,  # 5ms
    0.010,  # 10ms
    0.025,  # 25ms
    0.050,  # 50ms
    0.075,  # 75ms
    0.100,  # 100ms
    0.250,  # 250ms
    0.500,  # 500ms
    1.0,  # 1s
)

# =============================================================================
# API Service Buckets (100ms-1s typical)
# =============================================================================
# For standard API services:
# - REST APIs
# - GraphQL services
# - Microservices
# - Web applications

API_SERVICE_BUCKETS: tuple[float, ...] = (
    0.010,  # 10ms
    0.025,  # 25ms
    0.050,  # 50ms
    0.100,  # 100ms
    0.250,  # 250ms
    0.500,  # 500ms
    1.0,  # 1s
    2.5,  # 2.5s
    5.0,  # 5s
    10.0,  # 10s
)

# =============================================================================
# Database Service Buckets
# =============================================================================
# For database operations:
# - Query execution
# - Transaction processing
# - Data migrations

DATABASE_SERVICE_BUCKETS: tuple[float, ...] = (
    0.001,  # 1ms
    0.005,  # 5ms
    0.010,  # 10ms
    0.025,  # 25ms
    0.050,  # 50ms
    0.100,  # 100ms
    0.250,  # 250ms
    0.500,  # 500ms
    1.0,  # 1s
    2.5,  # 2.5s
    5.0,  # 5s
)

# =============================================================================
# Batch Processing Buckets (Seconds to Minutes)
# =============================================================================
# For long-running operations:
# - Batch jobs
# - Data processing
# - ETL pipelines
# - Report generation

BATCH_SERVICE_BUCKETS: tuple[float, ...] = (
    0.1,  # 100ms
    0.5,  # 500ms
    1.0,  # 1s
    2.5,  # 2.5s
    5.0,  # 5s
    10.0,  # 10s
    30.0,  # 30s
    60.0,  # 1m
    120.0,  # 2m
    300.0,  # 5m
    600.0,  # 10m
)

# =============================================================================
# Default Buckets (General Purpose)
# =============================================================================
# Good default for most services:
# - Covers 1ms to 10s
# - Good resolution across the range
# - Works for most use cases

DEFAULT_BUCKETS: tuple[float, ...] = (
    0.001,  # 1ms
    0.005,  # 5ms
    0.010,  # 10ms
    0.025,  # 25ms
    0.050,  # 50ms
    0.100,  # 100ms
    0.250,  # 250ms
    0.500,  # 500ms
    1.0,  # 1s
    2.5,  # 2.5s
    5.0,  # 5s
    10.0,  # 10s
)

__all__ = [
    "FAST_SERVICE_BUCKETS",
    "API_SERVICE_BUCKETS",
    "DATABASE_SERVICE_BUCKETS",
    "BATCH_SERVICE_BUCKETS",
    "DEFAULT_BUCKETS",
]
