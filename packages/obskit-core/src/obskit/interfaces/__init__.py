"""
Interfaces Module - Abstract Base Classes for obskit Components
================================================================

This module provides abstract base classes (ABCs) that define the contracts
for all major obskit components. Using these interfaces enables:

1. **Better Testability**: Mock implementations for unit testing
2. **Extensibility**: Custom implementations for specific use cases
3. **Type Safety**: Clear contracts for IDE support and static analysis
4. **Dependency Injection**: Swap implementations at runtime

Available Interfaces
--------------------
- ``LoggerInterface``: Contract for logging backends
- ``MetricsInterface``: Contract for metrics collectors
- ``CircuitBreakerInterface``: Contract for circuit breakers
- ``HealthCheckerInterface``: Contract for health checkers
- ``TracerInterface``: Contract for distributed tracing

Example - Custom Logger Implementation
--------------------------------------
.. code-block:: python

    from obskit.interfaces import LoggerInterface

    class MyCustomLogger(LoggerInterface):
        def info(self, event: str, **kwargs) -> None:
            print(f"INFO: {event} {kwargs}")

        def error(self, event: str, **kwargs) -> None:
            print(f"ERROR: {event} {kwargs}")

        # ... implement other methods

Example - Testing with Mock
---------------------------
.. code-block:: python

    from unittest.mock import MagicMock
    from obskit.interfaces import MetricsInterface

    def test_my_service():
        mock_metrics = MagicMock(spec=MetricsInterface)
        service = MyService(metrics=mock_metrics)
        service.process()
        mock_metrics.observe_request.assert_called_once()
"""

from obskit.interfaces.circuit_breaker import CircuitBreakerInterface
from obskit.interfaces.health_checker import HealthCheckerInterface
from obskit.interfaces.logging import LoggerInterface
from obskit.interfaces.metrics import MetricsInterface
from obskit.interfaces.tracer import TracerInterface

__all__ = [
    "LoggerInterface",
    "MetricsInterface",
    "CircuitBreakerInterface",
    "HealthCheckerInterface",
    "TracerInterface",
]
