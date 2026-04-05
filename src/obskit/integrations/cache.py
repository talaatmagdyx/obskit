"""
Redis Cache Instrumentation
============================

Wraps an async Redis client so that every command is automatically counted
and timed with Prometheus metrics.

Metrics exposed
---------------
``redis_commands_total{name, command, status}``
    Cumulative counter of Redis commands.  *status* is ``"success"`` or
    ``"error"``.

``redis_command_duration_seconds{name, command}``
    Histogram of command round-trip latency.

``redis_pool_connections{name, state}``
    Point-in-time gauge of connection-pool connections keyed by *state*
    (``"available"``, ``"in_use"``).  Call :meth:`InstrumentedRedis.update_pool_stats`
    periodically to keep the gauge current; it is *not* updated on every command
    because the pool introspection API differs across redis-py versions.

Usage
-----
::

    import redis.asyncio as aioredis
    from obskit.integrations.cache import instrument_redis

    redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
    redis_client = instrument_redis(redis_client, name="engagement-cache")

    # All commands are now instrumented:
    await redis_client.get("my-key")
    await redis_client.set("my-key", "value", ex=60)

The wrapper is **transparent** — every attribute that exists on the underlying
client is accessible through the wrapper.  Only ``async`` command methods are
wrapped with instrumentation; synchronous helpers (like ``.connection_pool``)
are passed through unchanged.
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# Metric definitions (module-level singletons, registered once)
# ---------------------------------------------------------------------------

REDIS_COMMANDS_TOTAL: Counter = Counter(
    "redis_commands_total",
    "Total Redis commands executed",
    ["name", "command", "status"],
)

REDIS_COMMAND_DURATION_SECONDS: Histogram = Histogram(
    "redis_command_duration_seconds",
    "Redis command round-trip duration in seconds",
    ["name", "command"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

REDIS_COMMAND_ERRORS_TOTAL: Counter = Counter(
    "redis_command_errors_total",
    "Total Redis command errors",
    ["name", "command"],
)

REDIS_POOL_CONNECTIONS: Gauge = Gauge(
    "redis_pool_connections",
    "Redis connection pool size by state",
    ["name", "state"],
)


class InstrumentedRedis:
    """Transparent async Redis proxy that records Prometheus metrics.

    Do not instantiate directly — use :func:`instrument_redis`.

    Parameters
    ----------
    client :
        The underlying async Redis client (``redis.asyncio.Redis`` or
        any compatible client with async command methods).
    name : str
        Label value used in all metric series.  Choose a human-readable
        name that identifies the role of this client (e.g.
        ``"session-cache"``, ``"rate-limit-store"``).
    """

    __slots__ = ("_client", "_name")

    def __init__(self, client: Any, name: str) -> None:
        self._client = client
        self._name = name

    # ------------------------------------------------------------------
    # Transparent attribute proxy
    # ------------------------------------------------------------------

    def __getattr__(self, attr: str) -> Any:
        original = getattr(self._client, attr)

        # Only wrap async callables — non-async attrs (properties, sync
        # helpers, the connection pool itself) pass through unchanged.
        if not asyncio.iscoroutinefunction(original):
            return original

        name = self._name  # local ref for closure

        @functools.wraps(original)
        async def _instrumented(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            status = "success"
            try:
                return await original(*args, **kwargs)
            except Exception:
                status = "error"
                REDIS_COMMAND_ERRORS_TOTAL.labels(name=name, command=attr).inc()
                raise
            finally:
                elapsed = time.perf_counter() - start
                REDIS_COMMANDS_TOTAL.labels(
                    name=name, command=attr, status=status
                ).inc()
                REDIS_COMMAND_DURATION_SECONDS.labels(
                    name=name, command=attr
                ).observe(elapsed)

        return _instrumented

    # ------------------------------------------------------------------
    # Pool gauge helper
    # ------------------------------------------------------------------

    def update_pool_stats(self) -> None:
        """Refresh the ``redis_pool_connections`` gauge from the pool state.

        Call periodically (e.g. from a background task or after large
        bursts) to keep the gauge current.  Silently no-ops if the
        underlying client does not expose a ``connection_pool`` attribute
        or if the pool API is unavailable.
        """
        try:
            pool = self._client.connection_pool
            available = getattr(pool, "_available_connections", None)
            in_use = getattr(pool, "_in_use_connections", None)

            if available is not None:
                REDIS_POOL_CONNECTIONS.labels(
                    name=self._name, state="available"
                ).set(len(available))
            if in_use is not None:
                REDIS_POOL_CONNECTIONS.labels(
                    name=self._name, state="in_use"
                ).set(len(in_use))
        except Exception:  # pragma: no cover
            pass


def instrument_redis_client(client: Any, name: str = "default") -> InstrumentedRedis:
    """Wrap an async Redis client with Prometheus instrumentation.

    Emits per-command latency histogram and error counter, making Redis
    performance directly visible in Grafana dashboards.

    Parameters
    ----------
    client :
        An async Redis client (``redis.asyncio.Redis`` or compatible).
    name : str
        Human-readable label identifying this client's role, e.g.
        ``"engagement-cache"``, ``"rate-limit-store"``.
        Default: ``"default"``.

    Returns
    -------
    InstrumentedRedis
        A transparent proxy that records the following metrics on every
        async command:

        * ``redis_command_duration_seconds{name, command}`` — latency histogram
        * ``redis_command_errors_total{name, command}`` — dedicated error counter
        * ``redis_commands_total{name, command, status}`` — full outcome counter

    Example
    -------
    >>> import redis.asyncio as aioredis
    >>> from obskit.integrations.cache import instrument_redis_client
    >>>
    >>> r = aioredis.from_url("redis://redis:6379")
    >>> r = instrument_redis_client(r, name="engagement-cache")
    >>> await r.get("key")   # metrics emitted automatically
    """
    return InstrumentedRedis(client, name)


def instrument_redis(client: Any, *, name: str = "default") -> InstrumentedRedis:
    """Wrap an async Redis client with Prometheus instrumentation.

    Parameters
    ----------
    client :
        An async Redis client (``redis.asyncio.Redis`` or compatible).
    name : str
        Human-readable label for all metric series emitted by this client.
        Default: ``"default"``.

    Returns
    -------
    InstrumentedRedis
        A transparent proxy that records metrics on every command.

    Example
    -------
    >>> import redis.asyncio as aioredis
    >>> from obskit.integrations.cache import instrument_redis
    >>>
    >>> r = aioredis.from_url("redis://redis:6379")
    >>> r = instrument_redis(r, name="my-cache")
    >>> await r.get("key")   # redis_commands_total incremented
    """
    return InstrumentedRedis(client, name)


__all__ = [
    "InstrumentedRedis",
    "instrument_redis",
    "instrument_redis_client",
    "REDIS_COMMANDS_TOTAL",
    "REDIS_COMMAND_DURATION_SECONDS",
    "REDIS_COMMAND_ERRORS_TOTAL",
    "REDIS_POOL_CONNECTIONS",
]
