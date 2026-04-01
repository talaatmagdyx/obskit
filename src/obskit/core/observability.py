"""
Observability facade -- the runtime handle returned by ``configure_observability()``.

This module provides a thin coordinator that holds configuration and
exposes lazy accessors for the tracer, metrics, and logger subsystems.
"""

from __future__ import annotations

import threading
from functools import cached_property
from typing import Any

from obskit.core.observability_config import ObservabilityConfig

# ── Global singleton ──────────────────────────────────────────────────────
_global_obs: Observability | None = None
_obs_lock = threading.Lock()


class Observability:
    """Thin facade over obskit's subsystems.

    Users should not construct this directly -- use
    :func:`obskit.configure_observability` instead.
    """

    def __init__(self, config: ObservabilityConfig) -> None:
        self._config = config

    # ── Public properties ─────────────────────────────────────────────

    @property
    def config(self) -> ObservabilityConfig:
        """The immutable configuration snapshot."""
        return self._config

    @cached_property
    def tracer(self) -> Any:
        """The OpenTelemetry tracer (lazy)."""
        from obskit.tracing.tracer import get_tracer

        return get_tracer()

    @cached_property
    def metrics(self) -> Any:
        """The RED metrics recorder (lazy)."""
        from obskit.metrics.red import get_red_metrics

        return get_red_metrics()

    @cached_property
    def logger(self) -> Any:
        """A structured logger for the service (lazy)."""
        from obskit.logging import get_logger

        return get_logger(self._config.service.name)

    @cached_property
    def diagnostics(self) -> Any:
        """Unified diagnostics: package health + internal self-metrics (lazy)."""
        from obskit.core.diagnostics import Diagnostics

        return Diagnostics()

    # ── Lifecycle ─────────────────────────────────────────────────────

    def shutdown(self) -> None:
        """Gracefully shut down tracing exporters and the metrics HTTP server."""
        from obskit.tracing.tracer import shutdown_tracing

        shutdown_tracing()

        try:
            from obskit.metrics.registry import stop_http_server

            stop_http_server()
        except Exception:  # pragma: no cover
            pass

    def __repr__(self) -> str:
        return (
            f"Observability(service={self._config.service.name!r}, "
            f"env={self._config.service.environment!r})"
        )


# ── Module-level accessors ────────────────────────────────────────────────


def get_observability() -> Observability:
    """Return the global :class:`Observability` instance.

    If :func:`obskit.configure_observability` has not been called yet,
    a default instance is created automatically.
    """
    global _global_obs

    if _global_obs is None:
        with _obs_lock:
            if _global_obs is None:  # pragma: no cover
                _global_obs = Observability(ObservabilityConfig())  # pragma: no cover

    return _global_obs


def _set_observability(obs: Observability) -> None:
    """Replace the global singleton (called by ``configure_observability``)."""
    global _global_obs
    with _obs_lock:
        _global_obs = obs


def reset_observability() -> None:
    """Clear the global singleton -- for testing only."""
    global _global_obs
    with _obs_lock:
        _global_obs = None
