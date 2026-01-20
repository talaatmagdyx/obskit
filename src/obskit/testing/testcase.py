"""
Test Case Base Class
====================

Base class for tests that need obskit mocking.
"""

from __future__ import annotations

import unittest

from obskit.testing.context import ObskitTestContext
from obskit.testing.mocks import (
    MockHealthChecker,
    MockMetrics,
    MockSLOTracker,
    MockTracer,
)


class ObskitTestCase(unittest.TestCase):
    """
    Base test case class with obskit mocking built-in.

    Automatically sets up and tears down mock observability components.

    Example
    -------
    >>> class TestOrderService(ObskitTestCase):
    ...     def test_create_order(self):
    ...         # Mocks are automatically set up
    ...         create_order({"item": "widget"})
    ...
    ...         # Assert on metrics
    ...         self.mock_metrics.assert_request_recorded("create_order")
    ...
    ...         # Assert on traces
    ...         self.mock_tracer.assert_span_created("order.create")
    ...
    ...     def test_order_slo(self):
    ...         create_order({"item": "widget"})
    ...         self.mock_slo.assert_measurement_recorded("order_latency")
    """

    # Class-level mocks (shared across all tests in class)
    mock_metrics: MockMetrics
    mock_tracer: MockTracer
    mock_slo: MockSLOTracker
    mock_health: MockHealthChecker

    # Test context
    _obskit_context: ObskitTestContext | None = None

    @classmethod
    def setUpClass(cls):
        """Set up class-level resources."""
        super().setUpClass()
        cls.mock_metrics = MockMetrics()
        cls.mock_tracer = MockTracer()
        cls.mock_slo = MockSLOTracker()
        cls.mock_health = MockHealthChecker()

    def setUp(self):
        """Set up test resources."""
        super().setUp()

        # Reset mocks between tests
        self.mock_metrics.reset()
        self.mock_tracer.reset()
        self.mock_slo.reset()

        # Create and enter test context
        self._obskit_context = ObskitTestContext()
        self._obskit_context.metrics = self.mock_metrics
        self._obskit_context.tracer = self.mock_tracer
        self._obskit_context.slo_tracker = self.mock_slo
        self._obskit_context.__enter__()

    def tearDown(self):
        """Tear down test resources."""
        if self._obskit_context:
            self._obskit_context.__exit__(None, None, None)
            self._obskit_context = None
        super().tearDown()

    # Assertion helpers

    def assertMetricRecorded(
        self,
        operation: str,
        status: str | None = None,
        min_count: int = 1,
    ):
        """Assert that a metric was recorded."""
        self.mock_metrics.assert_request_recorded(operation, status, min_count)

    def assertNoMetrics(self, operation: str | None = None):
        """Assert no metrics were recorded."""
        self.mock_metrics.assert_no_requests(operation)

    def assertSpanCreated(self, name: str, min_count: int = 1):
        """Assert that a trace span was created."""
        self.mock_tracer.assert_span_created(name, min_count)

    def assertSLOMeasured(self, slo_name: str, min_count: int = 1):
        """Assert that an SLO measurement was recorded."""
        self.mock_slo.assert_measurement_recorded(slo_name, min_count)

    def getMetricCount(self, operation: str, status: str | None = None) -> int:
        """Get the count of metrics recorded for an operation."""
        return self.mock_metrics.get_request_count(operation, status)

    def getSpanCount(self, name: str) -> int:
        """Get the count of spans created with a name."""
        return len(self.mock_tracer.get_spans(name))


class AsyncObskitTestCase(ObskitTestCase):
    """
    Async-compatible test case for obskit testing.

    Use this when testing async code.

    Example
    -------
    >>> class TestAsyncService(AsyncObskitTestCase):
    ...     async def test_async_operation(self):
    ...         await async_create_order({"item": "widget"})
    ...         self.assertMetricRecorded("create_order")
    """

    def setUp(self):
        """Set up async test resources."""
        super().setUp()
        # Set up async event loop if needed
        try:
            import asyncio

            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        except ImportError:
            self._loop = None

    def tearDown(self):
        """Tear down async test resources."""
        if self._loop:
            self._loop.close()
        super().tearDown()

    def run_async(self, coro):
        """Run an async coroutine."""
        if self._loop:
            return self._loop.run_until_complete(coro)
        raise RuntimeError("No event loop available")


__all__ = [
    "ObskitTestCase",
    "AsyncObskitTestCase",
]
