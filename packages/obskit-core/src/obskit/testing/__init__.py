"""
Testing Utilities
=================

Mock objects and utilities for testing code that uses obskit.

Example
-------
>>> from obskit.testing import (
...     MockMetrics,
...     MockTracer,
...     disable_observability,
...     ObskitTestCase,
... )
>>>
>>> # Disable all observability in tests
>>> with disable_observability():
...     result = my_function()  # No metrics/traces recorded
>>>
>>> # Use mock metrics
>>> mock_metrics = MockMetrics()
>>> with mock_metrics.patch():
...     my_function()
... mock_metrics.assert_request_recorded("create_order", status="success")
>>>
>>> # Use as test case base
>>> class TestMyService(ObskitTestCase):
...     def test_order_creation(self):
...         self.mock_metrics.reset()
...         create_order(data)
...         self.mock_metrics.assert_request_recorded("create_order")
"""

from obskit.testing.context import (
    ObskitTestContext,
    disable_observability,
    mock_observability,
)
from obskit.testing.mocks import (
    MockCircuitBreaker,
    MockHealthChecker,
    MockMetrics,
    MockSLOTracker,
    MockTracer,
)
from obskit.testing.testcase import ObskitTestCase

__all__ = [
    # Mocks
    "MockMetrics",
    "MockTracer",
    "MockSLOTracker",
    "MockHealthChecker",
    "MockCircuitBreaker",
    # Context managers
    "disable_observability",
    "mock_observability",
    "ObskitTestContext",
    # Test case
    "ObskitTestCase",
]
