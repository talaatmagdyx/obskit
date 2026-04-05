"""
obskit resilience — circuit breaker, rate limiter, retry instrumentation.

Provides Prometheus metrics and structured logging for resilience patterns.
"""

from obskit.resilience.circuit_breaker import (
    CircuitState,
    ObskitCircuitBreakerListener,
    instrument_circuit_breaker,
)

__all__ = [
    "CircuitState",
    "ObskitCircuitBreakerListener",
    "instrument_circuit_breaker",
]
