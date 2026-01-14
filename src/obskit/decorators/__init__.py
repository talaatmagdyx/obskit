"""
Observability Decorators for obskit
===================================

This module provides decorators that automatically add observability
to your functions. Instead of manually adding logging, metrics, and
error handling to every function, you can use these decorators to
get comprehensive observability with a single line.

Available Decorators
--------------------

**with_observability** / **with_observability_async**
    Full observability: logging, metrics, and error tracking.
    Use for important business operations.

**track_operation**
    Lightweight logging only (no metrics).
    Use for internal operations where metrics aren't needed.

**track_metrics_only**
    Metrics only (no logging).
    Use for high-frequency operations where logging would be too verbose.

Quick Start
-----------
.. code-block:: python

    from obskit.decorators import with_observability

    @with_observability(
        component="OrderService",
        operation="create_order",
        threshold_ms=500.0,
    )
    async def create_order(order_data: dict) -> Order:
        '''
        Create a new order.

        The decorator automatically:
        1. Logs operation start (if log_start=True)
        2. Records execution duration
        3. Logs operation completion with timing
        4. Records RED metrics (rate, errors, duration)
        5. Logs errors with full context
        6. Warns if duration exceeds threshold
        '''
        return await Order.create(**order_data)

Decorator Comparison
--------------------

+----------------------+----------+---------+-------+-----------+
| Decorator            | Logging  | Metrics | Trace | Use Case  |
+======================+==========+=========+=======+===========+
| with_observability   | ✓        | ✓       | ✓     | Business  |
|                      |          |         |       | operations|
+----------------------+----------+---------+-------+-----------+
| track_operation      | ✓        | ✗       | ✗     | Internal  |
|                      |          |         |       | helpers   |
+----------------------+----------+---------+-------+-----------+
| track_metrics_only   | ✗        | ✓       | ✗     | High-freq |
|                      |          |         |       | operations|
+----------------------+----------+---------+-------+-----------+

Example - Full Observability
----------------------------
.. code-block:: python

    from obskit.decorators import with_observability

    @with_observability(
        component="PaymentService",
        operation="process_payment",
        threshold_ms=1000.0,  # Warn if > 1 second
        log_start=True,       # Log when operation starts
    )
    async def process_payment(payment_id: str, amount: float) -> PaymentResult:
        '''Process a payment transaction.'''
        # Your business logic here
        result = await payment_gateway.charge(payment_id, amount)
        return result

    # When called, the decorator will:
    # 1. Log: "operation_started" with component, operation
    # 2. Execute your function
    # 3. On success:
    #    - Log: "operation_completed" with duration
    #    - Record metric: payment_service_requests_total{operation="process_payment",status="success"}
    #    - Record metric: payment_service_request_duration_seconds{operation="process_payment"}
    # 4. On failure:
    #    - Log: "operation_failed" with error details
    #    - Record metric: payment_service_requests_total{operation="process_payment",status="failure"}
    #    - Record metric: payment_service_errors_total{operation="process_payment",error_type="..."}

Example - Sync Functions
------------------------
.. code-block:: python

    from obskit.decorators.combined import with_observability_sync

    @with_observability_sync(component="FileProcessor")
    def process_file(filepath: str) -> ProcessResult:
        '''Process a file synchronously.'''
        with open(filepath, 'r') as f:
            data = f.read()
        return process_data(data)

Example - High-Frequency Operations
-----------------------------------
.. code-block:: python

    from obskit.decorators import track_metrics_only

    @track_metrics_only(component="CacheService")
    async def get_from_cache(key: str) -> Optional[str]:
        '''
        Get value from cache.

        Uses metrics-only decorator because:
        1. Called very frequently (every request)
        2. Logging would create too much noise
        3. We still want latency metrics
        '''
        return await cache.get(key)

Example - Internal Operations
-----------------------------
.. code-block:: python

    from obskit.decorators import track_operation

    @track_operation(component="DataTransformer")
    async def transform_response(data: dict) -> dict:
        '''
        Transform API response.

        Uses lightweight logging because:
        1. This is an internal helper function
        2. We don't need metrics for this
        3. But logging helps with debugging
        '''
        return {
            "id": data["user_id"],
            "name": data["full_name"],
        }

Context Propagation
-------------------
All decorators automatically propagate correlation IDs:

.. code-block:: python

    from obskit import with_observability, get_logger

    logger = get_logger(__name__)

    @with_observability(component="OrderService")
    async def create_order(order_data: dict, correlation_id: str = None) -> Order:
        # The correlation_id is automatically:
        # 1. Extracted from kwargs if provided
        # 2. Included in all log entries
        # 3. Propagated to downstream services

        logger.info("creating_order", order_id=order_data["id"])
        # Log output includes: {"correlation_id": "abc-123", ...}

        return await Order.create(**order_data)

Performance Thresholds
----------------------
Use thresholds to automatically warn about slow operations:

.. code-block:: python

    @with_observability(
        component="SearchService",
        threshold_ms=200.0,  # Warn if search takes > 200ms
    )
    async def search(query: str) -> SearchResults:
        return await search_engine.query(query)

    # If search takes 350ms, logs:
    # {
    #   "event": "slow_operation",
    #   "component": "SearchService",
    #   "operation": "search",
    #   "duration_ms": 350.0,
    #   "threshold_ms": 200.0,
    #   "exceeded_by_ms": 150.0
    # }

Error Handling
--------------
Errors are automatically logged with full context:

.. code-block:: python

    @with_observability(component="PaymentService")
    async def charge_card(card_id: str, amount: float):
        if amount <= 0:
            raise ValueError("Amount must be positive")
        return await gateway.charge(card_id, amount)

    # On ValueError, logs:
    # {
    #   "event": "operation_error",
    #   "component": "PaymentService",
    #   "operation": "charge_card",
    #   "error": "Amount must be positive",
    #   "error_type": "ValueError",
    #   "exc_info": true
    # }
    #
    # And records metrics:
    # - payment_service_errors_total{operation="charge_card",error_type="ValueError"}

See Also
--------
obskit.logging : Structured logging utilities
obskit.metrics : Prometheus metrics collection
obskit.core.context : Correlation ID management
"""

from obskit.decorators.combined import (
    track_metrics_only,
    track_operation,
    with_observability,
    with_observability_async,
    with_observability_sync,
)

__all__ = [
    # Full observability (async)
    "with_observability",
    "with_observability_async",  # Alias for with_observability
    # Full observability (sync)
    "with_observability_sync",
    # Lightweight alternatives
    "track_operation",  # Logging only
    "track_metrics_only",  # Metrics only
]
