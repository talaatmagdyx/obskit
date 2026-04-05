"""
Circuit Breaker Instrumentation
================================

Provides Prometheus metrics for circuit breakers.  Works as a
``pybreaker``-compatible listener, or as a standalone recorder when you
manage state transitions yourself.

Metrics emitted
---------------
``circuit_breaker_state{name}``
    Gauge: 0 = closed (healthy), 1 = open (failing), 2 = half-open (probing).

``circuit_breaker_failures_total{name}``
    Counter: monotonically increasing failure count.

``circuit_breaker_calls_total{name, outcome}``
    Counter: outcome is ``"success"`` or ``"failure"``.

Example — pybreaker integration
--------------------------------
.. code-block:: python

    import pybreaker
    from obskit.resilience.circuit_breaker import instrument_circuit_breaker

    cb = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)
    instrument_circuit_breaker(cb, name="redis_commands")

    # Now metrics are emitted automatically on every call.

Example — standalone usage
---------------------------
.. code-block:: python

    from obskit.resilience.circuit_breaker import ObskitCircuitBreakerListener

    listener = ObskitCircuitBreakerListener("upstream_http")
    listener.record_success()
    listener.record_failure(RuntimeError("timeout"))
    listener.record_state_change("open")
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from obskit.metrics.types import Counter, Gauge

# ---------------------------------------------------------------------------
# Prometheus metrics (module-level singletons, label sets allocated lazily)
# ---------------------------------------------------------------------------

_STATE_GAUGE = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["name"],
)

_FAILURES_TOTAL = Counter(
    "circuit_breaker_failures_total",
    "Total circuit breaker failures",
    ["name"],
)

_CALLS_TOTAL = Counter(
    "circuit_breaker_calls_total",
    "Total circuit breaker calls",
    ["name", "outcome"],
)

_TRANSITIONS_TOTAL = Counter(
    "circuit_breaker_transitions_total",
    "Total circuit breaker state transitions",
    ["name", "from_state", "to_state"],
)

# ---------------------------------------------------------------------------
# State enumeration
# ---------------------------------------------------------------------------

_STATE_MAP: dict[str, int] = {
    "closed": 0,
    "open": 1,
    "half_open": 2,
    "half-open": 2,
}


class CircuitState(IntEnum):
    """Numeric encoding for circuit breaker states."""

    CLOSED = 0   # normal operation
    OPEN = 1     # failing, calls rejected
    HALF_OPEN = 2  # probing for recovery


# ---------------------------------------------------------------------------
# Listener
# ---------------------------------------------------------------------------


class ObskitCircuitBreakerListener:
    """
    pybreaker-compatible listener that records Prometheus metrics.

    Can also be used standalone (without pybreaker) by calling
    :meth:`record_success`, :meth:`record_failure`, and
    :meth:`record_state_change` directly.

    Parameters
    ----------
    name : str
        Label value for the ``name`` dimension in all metrics.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._current_state: str = "closed"
        # Initialise gauge as CLOSED so the metric exists from the start.
        _STATE_GAUGE.labels(name=name).set(CircuitState.CLOSED)

    # ------------------------------------------------------------------
    # pybreaker listener interface
    # ------------------------------------------------------------------

    def state_change(self, cb: Any, old_state: Any, new_state: Any) -> None:
        """Called by pybreaker when the circuit state transitions."""
        # pybreaker may pass state as a string, an object with .name, or
        # an object whose str() representation is the state name.
        raw_new = getattr(new_state, "name", str(new_state)).lower()
        raw_old = getattr(old_state, "name", str(old_state)).lower()
        state_val = _STATE_MAP.get(raw_new, CircuitState.CLOSED)
        _STATE_GAUGE.labels(name=self.name).set(state_val)
        _TRANSITIONS_TOTAL.labels(
            name=self.name, from_state=raw_old, to_state=raw_new
        ).inc()

    def failure(self, cb: Any, exc: BaseException) -> None:
        """Called by pybreaker after a function raises an exception."""
        _FAILURES_TOTAL.labels(name=self.name).inc()
        _CALLS_TOTAL.labels(name=self.name, outcome="failure").inc()

    def success(self, cb: Any) -> None:
        """Called by pybreaker after a function returns successfully."""
        _CALLS_TOTAL.labels(name=self.name, outcome="success").inc()

    def before_call(self, cb: Any, func: Any, *args: Any, **kwargs: Any) -> None:
        """Called by pybreaker before the wrapped function is invoked."""

    # ------------------------------------------------------------------
    # Standalone helpers (no pybreaker required)
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        """Record a successful call (standalone, without pybreaker)."""
        _CALLS_TOTAL.labels(name=self.name, outcome="success").inc()

    def record_failure(self, exc: BaseException | None = None) -> None:
        """Record a failed call (standalone, without pybreaker)."""
        _FAILURES_TOTAL.labels(name=self.name).inc()
        _CALLS_TOTAL.labels(name=self.name, outcome="failure").inc()

    def record_state_change(self, new_state: str) -> None:
        """Record a state transition (standalone, without pybreaker).

        Parameters
        ----------
        new_state : str
            One of ``"closed"``, ``"open"``, or ``"half_open"`` / ``"half-open"``.
        """
        old_state = self._current_state
        self._current_state = new_state.lower()
        state_val = _STATE_MAP.get(self._current_state, CircuitState.CLOSED)
        _STATE_GAUGE.labels(name=self.name).set(state_val)
        _TRANSITIONS_TOTAL.labels(
            name=self.name, from_state=old_state, to_state=self._current_state
        ).inc()


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def instrument_circuit_breaker(cb: Any, *, name: str) -> ObskitCircuitBreakerListener:
    """Attach obskit metrics to a pybreaker ``CircuitBreaker`` instance.

    Parameters
    ----------
    cb : pybreaker.CircuitBreaker
        The circuit breaker to instrument.
    name : str
        Metric label — typically the resource protected by the breaker,
        e.g. ``"redis_commands"`` or ``"upstream_http"``.

    Returns
    -------
    ObskitCircuitBreakerListener
        The attached listener (useful for testing or manual removal).

    Raises
    ------
    TypeError
        If *cb* does not expose an ``add_listener`` method.

    Example
    -------
    .. code-block:: python

        import pybreaker
        from obskit.resilience.circuit_breaker import instrument_circuit_breaker

        cb = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)
        instrument_circuit_breaker(cb, name="redis_commands")
    """
    listener = ObskitCircuitBreakerListener(name=name)
    if not hasattr(cb, "add_listener"):
        raise TypeError(
            "cb must be a pybreaker CircuitBreaker (or implement add_listener). "
            "Install pybreaker: pip install pybreaker"
        )
    cb.add_listener(listener)
    return listener


__all__ = [
    "CircuitState",
    "ObskitCircuitBreakerListener",
    "instrument_circuit_breaker",
    "_STATE_GAUGE",
    "_FAILURES_TOTAL",
    "_CALLS_TOTAL",
    "_TRANSITIONS_TOTAL",
]
