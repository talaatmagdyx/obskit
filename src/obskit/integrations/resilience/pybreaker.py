"""
pybreaker circuit-breaker integration for obskit.

Attaches an :class:`~obskit.resilience.circuit_breaker.ObskitCircuitBreakerListener`
to a ``pybreaker.CircuitBreaker`` instance so that state changes and call
outcomes are automatically exported as Prometheus metrics.

Metrics emitted
---------------
``circuit_breaker_state{name}``
    Gauge: 0 = closed (healthy), 1 = open (failing), 2 = half-open (probing).

``circuit_breaker_transitions_total{name, from_state, to_state}``
    Counter: incremented on every state transition — enables alerting on
    "Twitter circuit opened".

``circuit_breaker_failures_total{name}``
    Counter: total failure count.

``circuit_breaker_calls_total{name, outcome}``
    Counter: outcome is ``"success"`` or ``"failure"``.

Example
-------
.. code-block:: python

    import pybreaker
    from obskit.integrations.resilience.pybreaker import instrument_pybreaker

    breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=30)
    listener = instrument_pybreaker(breaker, name="twitter")
    # Metrics are now populated automatically on every call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from obskit.resilience.circuit_breaker import ObskitCircuitBreakerListener


def instrument_pybreaker(cb: Any, name: str) -> "ObskitCircuitBreakerListener":
    """Attach obskit Prometheus metrics to a pybreaker ``CircuitBreaker``.

    Parameters
    ----------
    cb : pybreaker.CircuitBreaker
        The circuit breaker to instrument.
    name : str
        Metric label — typically the resource protected by the breaker,
        e.g. ``"twitter"``, ``"redis"``, ``"payments-api"``.

    Returns
    -------
    ObskitCircuitBreakerListener
        The attached listener (useful for testing or manual removal).

    Raises
    ------
    TypeError
        If *cb* does not expose an ``add_listener`` method.
    """
    from obskit.resilience.circuit_breaker import instrument_circuit_breaker  # noqa: PLC0415

    return instrument_circuit_breaker(cb, name=name)


__all__ = ["instrument_pybreaker"]
