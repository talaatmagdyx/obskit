"""
psycopg_pool Prometheus instrumentation for obskit.

Exposes pool size, available connections, waiting requests (gauges), and
connection-acquisition latency (histogram) for any psycopg_pool.ConnectionPool
or psycopg_pool.AsyncConnectionPool.

Usage::

    from obskit.integrations.db.psycopg_pool import instrument_psycopg_pool

    pool = psycopg_pool.ConnectionPool(conninfo, min_size=2, max_size=10)
    instr = instrument_psycopg_pool(pool, name="main")

    # Call periodically (e.g. from a background task or health check):
    instr.collect_stats()

Requires: pip install obskit[psycopg3]  or  obskit[integrations]
"""

from __future__ import annotations

import time
from typing import Any

from prometheus_client import Gauge, Histogram

DB_POOL_SIZE = Gauge(
    "db_pool_size",
    "Current number of connections in the pool",
    ["pool_name"],
)
DB_POOL_AVAILABLE = Gauge(
    "db_pool_available",
    "Number of idle connections available in the pool",
    ["pool_name"],
)
DB_POOL_WAITING = Gauge(
    "db_pool_requests_waiting",
    "Number of client requests waiting for a connection",
    ["pool_name"],
)
DB_POOL_ACQUISITION_SECONDS = Histogram(
    "db_pool_acquisition_seconds",
    "Time (seconds) spent waiting to acquire a connection from the pool",
    ["pool_name"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)


class PsycopgPoolInstrumentor:
    """Instruments a psycopg_pool pool with Prometheus metrics.

    Wraps ``pool.getconn()`` to measure acquisition latency.
    Call :meth:`collect_stats` periodically to refresh the size/available/waiting gauges.
    """

    def __init__(self, pool: Any, name: str) -> None:
        self._pool = pool
        self._name = name

        _name = name
        _original_getconn = pool.getconn

        def _timed_getconn(*args: Any, **kwargs: Any) -> Any:
            t0 = time.monotonic()
            try:
                return _original_getconn(*args, **kwargs)
            finally:
                DB_POOL_ACQUISITION_SECONDS.labels(pool_name=_name).observe(
                    time.monotonic() - t0
                )

        pool.getconn = _timed_getconn

    def collect_stats(self) -> None:
        """Read ``pool.get_stats()`` and update Prometheus gauges."""
        stats: dict[str, Any] = self._pool.get_stats()
        DB_POOL_SIZE.labels(pool_name=self._name).set(stats.get("pool_size", 0))
        DB_POOL_AVAILABLE.labels(pool_name=self._name).set(stats.get("pool_available", 0))
        DB_POOL_WAITING.labels(pool_name=self._name).set(stats.get("requests_waiting", 0))


def instrument_psycopg_pool(pool: Any, name: str = "default") -> PsycopgPoolInstrumentor:
    """Instrument a psycopg_pool ConnectionPool with Prometheus metrics.

    Parameters
    ----------
    pool:
        A ``psycopg_pool.ConnectionPool`` or ``psycopg_pool.AsyncConnectionPool``.
    name:
        Label value used in all metrics.  Default: ``"default"``.

    Returns
    -------
    PsycopgPoolInstrumentor
        Call ``.collect_stats()`` from a background task or health-check to
        keep the size/available/waiting gauges up to date.
    """
    return PsycopgPoolInstrumentor(pool, name)


__all__ = [
    "PsycopgPoolInstrumentor",
    "instrument_psycopg_pool",
    "DB_POOL_SIZE",
    "DB_POOL_AVAILABLE",
    "DB_POOL_WAITING",
    "DB_POOL_ACQUISITION_SECONDS",
]
