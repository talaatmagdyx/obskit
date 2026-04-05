"""
Redis-backed Fleet SLO Tracker
================================

Stores SLO measurements in Redis sorted sets so that all Gunicorn/uvicorn
workers share a single, consistent SLO view instead of each process
maintaining its own in-memory ``deque``.

Architecture
------------
Each SLO uses two Redis sorted sets (score = Unix timestamp)::

    obskit:slo:<service>:<name>:total    — every measurement
    obskit:slo:<service>:<name>:success  — successful measurements only

For LATENCY SLOs a third key is used::

    obskit:slo:<service>:<name>:latencies  — member = "<value>:<uuid>"

Window management is handled with ``ZREMRANGEBYSCORE`` on every write so
the sets never grow beyond the configured time window.  A TTL of
``window_seconds + 60`` is set on all keys to ensure eventual cleanup even
if the application stops recording measurements.

Usage
-----
.. code-block:: python

    import redis.asyncio as aioredis
    from obskit.slo.redis_tracker import AsyncRedisSLOTracker
    from obskit.slo.types import SLOType

    redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
    tracker = AsyncRedisSLOTracker(redis_client, service="engagement-hub")

    tracker.register_slo(
        "api_availability",
        SLOType.AVAILABILITY,
        target_value=0.999,
        window_seconds=3600,
    )

    # In each request handler / middleware:
    await tracker.record_measurement("api_availability", value=1.0, success=True)

    # On /metrics or a background task:
    status = await tracker.get_status("api_availability")
    print(status.to_dict())

Both ``decode_responses=True`` and binary clients are supported.
"""

from __future__ import annotations

import math
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from obskit.logging import get_logger
from obskit.slo.types import SLOStatus, SLOTarget, SLOType

logger = get_logger(__name__)

_DEFAULT_PREFIX = "obskit:slo"
_TTL_GRACE = 60  # seconds added to window TTL so Redis auto-expires stale keys


def _decode(value: bytes | str) -> str:
    """Return *value* as str regardless of whether client uses decode_responses."""
    return value.decode() if isinstance(value, bytes) else value


class AsyncRedisSLOTracker:
    """
    Fleet-wide SLO tracker that stores measurements in Redis.

    All workers in a Gunicorn/uvicorn cluster share the same sorted sets,
    so :meth:`get_status` always reflects the fleet aggregate rather than
    the per-process view given by :class:`~obskit.slo.tracker.SLOTracker`.

    Parameters
    ----------
    redis :
        An **async** Redis client (``redis.asyncio.Redis`` or compatible).
        The client may use ``decode_responses=True`` or binary mode — both
        are handled transparently.
    service : str
        Service name used as part of the Redis key namespace.
    key_prefix : str
        Redis key prefix.  Default: ``"obskit:slo"``.

    Notes
    -----
    * ``register_slo`` is synchronous — it only stores the target locally.
      No Redis I/O is performed at registration time.
    * Each :meth:`record_measurement` call issues 4–6 Redis commands
      (ZADD + ZREMRANGEBYSCORE + EXPIRE per set).  For high-throughput
      services consider batching or using a local in-process buffer that
      flushes to Redis periodically.
    * LATENCY and THROUGHPUT SLOs are supported but read from Redis on
      every :meth:`get_status` call — prefer AVAILABILITY / ERROR_RATE
      for low-latency monitoring dashboards.
    """

    def __init__(
        self,
        redis: Any,
        *,
        service: str = "default",
        key_prefix: str = _DEFAULT_PREFIX,
    ) -> None:
        self._redis = redis
        self._service = service
        self._key_prefix = key_prefix
        self._targets: dict[str, SLOTarget] = {}

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def _key(self, name: str, suffix: str) -> str:
        return f"{self._key_prefix}:{self._service}:{name}:{suffix}"

    # ------------------------------------------------------------------
    # Registration (no I/O)
    # ------------------------------------------------------------------

    def register_slo(
        self,
        name: str,
        slo_type: SLOType,
        target_value: float,
        window_seconds: int = 3600,
        percentile: int | None = None,
    ) -> None:
        """Register an SLO target.

        Parameters
        ----------
        name : str
            Unique SLO name (used as part of the Redis key).
        slo_type : SLOType
            AVAILABILITY, ERROR_RATE, LATENCY, or THROUGHPUT.
        target_value : float
            Target threshold (e.g. ``0.999`` for 99.9 % availability).
        window_seconds : int
            Rolling time window in seconds.  Default: 3600 (1 h).
        percentile : int | None
            Required for LATENCY SLOs (e.g. ``99`` for P99).
        """
        target = SLOTarget(
            slo_type=slo_type,
            target_value=target_value,
            window_seconds=window_seconds,
            percentile=percentile,
        )
        self._targets[name] = target
        logger.info(
            "slo_registered",
            slo_name=name,
            slo_type=slo_type.value,
            target_value=target_value,
            window_seconds=window_seconds,
            backend="redis",
        )

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def record_measurement(
        self,
        name: str,
        value: float,
        success: bool = True,
    ) -> None:
        """Record an SLO measurement.

        Parameters
        ----------
        name : str
            SLO name (must have been registered with :meth:`register_slo`).
        value : float
            Measurement value (latency in ms, 1.0/0.0 for availability, …).
        success : bool
            Whether the operation succeeded.
        """
        if name not in self._targets:
            logger.warning("slo_not_registered", slo_name=name, backend="redis")
            return

        target = self._targets[name]
        now = time.time()
        uid = uuid.uuid4().hex
        cutoff = now - target.window_seconds
        ttl = target.window_seconds + _TTL_GRACE

        try:
            if target.slo_type in (SLOType.AVAILABILITY, SLOType.ERROR_RATE):
                await self._redis.zadd(self._key(name, "total"), {uid: now})
                if success:
                    await self._redis.zadd(self._key(name, "success"), {uid: now})
                await self._redis.zremrangebyscore(self._key(name, "total"), "-inf", cutoff)
                await self._redis.zremrangebyscore(self._key(name, "success"), "-inf", cutoff)
                await self._redis.expire(self._key(name, "total"), ttl)
                await self._redis.expire(self._key(name, "success"), ttl)

            elif target.slo_type == SLOType.LATENCY:
                member = f"{value}:{uid}"
                await self._redis.zadd(self._key(name, "latencies"), {member: now})
                await self._redis.zremrangebyscore(self._key(name, "latencies"), "-inf", cutoff)
                await self._redis.expire(self._key(name, "latencies"), ttl)

            else:  # THROUGHPUT
                await self._redis.zadd(self._key(name, "total"), {uid: now})
                await self._redis.zremrangebyscore(self._key(name, "total"), "-inf", cutoff)
                await self._redis.expire(self._key(name, "total"), ttl)

        except Exception as exc:  # pragma: no cover
            logger.warning(
                "slo_redis_write_error",
                slo_name=name,
                error=str(exc),
                error_type=type(exc).__name__,
            )

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    async def get_status(self, name: str) -> SLOStatus | None:
        """Return the current fleet-wide SLO status for *name*.

        Parameters
        ----------
        name : str
            SLO name.

        Returns
        -------
        SLOStatus | None
            ``None`` if the SLO has not been registered.
        """
        if name not in self._targets:
            return None

        target = self._targets[name]
        now = time.time()
        cutoff = now - target.window_seconds
        window_end = datetime.now(UTC)
        window_start = window_end - timedelta(seconds=target.window_seconds)

        try:
            if target.slo_type in (SLOType.AVAILABILITY, SLOType.ERROR_RATE):
                total = await self._redis.zcount(self._key(name, "total"), cutoff, "+inf")
                success_count = await self._redis.zcount(
                    self._key(name, "success"), cutoff, "+inf"
                )
                total = int(total)
                success_count = int(success_count)

                if total == 0:
                    current_value = 1.0 if target.slo_type == SLOType.AVAILABILITY else 0.0
                elif target.slo_type == SLOType.AVAILABILITY:
                    current_value = success_count / total
                else:
                    current_value = (total - success_count) / total
                measurement_count = total

            elif target.slo_type == SLOType.LATENCY:
                raw_members = await self._redis.zrangebyscore(
                    self._key(name, "latencies"), cutoff, "+inf"
                )
                if not raw_members:
                    return SLOStatus(
                        slo_type=target.slo_type,
                        target=target,
                        current_value=0.0,
                        compliance=True,
                        error_budget_remaining=1.0,
                        error_budget_burn_rate=0.0,
                        window_start=window_start,
                        window_end=window_end,
                        measurement_count=0,
                    )
                values = sorted(
                    float(_decode(m).split(":")[0]) for m in raw_members
                )
                measurement_count = len(values)
                if target.percentile:
                    raw_idx = math.ceil(measurement_count * target.percentile / 100) - 1
                    idx = max(0, min(raw_idx, measurement_count - 1))
                    current_value = values[idx]
                else:  # pragma: no cover — LATENCY always has percentile (enforced by SLOTarget)
                    current_value = sum(values) / measurement_count

            else:  # THROUGHPUT
                raw_members = await self._redis.zrangebyscore(
                    self._key(name, "total"), cutoff, "+inf", withscores=True
                )
                measurement_count = len(raw_members)
                if measurement_count < 2:
                    current_value = 0.0
                else:
                    time_span = raw_members[-1][1] - raw_members[0][1]
                    current_value = measurement_count / time_span if time_span > 0 else 0.0

        except Exception as exc:  # pragma: no cover
            logger.warning(
                "slo_redis_read_error",
                slo_name=name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None

        compliance = self._check_compliance(target, current_value)
        budget_remaining, burn_rate = self._calculate_error_budget(target, current_value)

        return SLOStatus(
            slo_type=target.slo_type,
            target=target,
            current_value=current_value,
            compliance=compliance,
            error_budget_remaining=budget_remaining,
            error_budget_burn_rate=burn_rate,
            window_start=window_start,
            window_end=window_end,
            measurement_count=measurement_count,
        )

    async def get_all_status(self) -> dict[str, SLOStatus]:
        """Return fleet-wide status for all registered SLOs.

        Returns
        -------
        dict[str, SLOStatus]
            Mapping of SLO name → :class:`~obskit.slo.types.SLOStatus`.
        """
        result: dict[str, SLOStatus] = {}
        for name in list(self._targets):
            status = await self.get_status(name)
            if status is not None:  # pragma: no branch — only None on Redis exception
                result[name] = status
        return result

    # ------------------------------------------------------------------
    # Compliance + budget helpers (pure, no I/O — matches SLOTracker)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_compliance(target: SLOTarget, current_value: float) -> bool:
        if target.slo_type in (SLOType.ERROR_RATE, SLOType.LATENCY):
            return current_value <= target.target_value
        return current_value >= target.target_value

    @staticmethod
    def _calculate_error_budget(
        target: SLOTarget, current_value: float
    ) -> tuple[float, float]:
        if target.slo_type == SLOType.AVAILABILITY:
            budget = 1.0 - target.target_value
            used = 1.0 - current_value
            remaining = max(0.0, budget - used)
            burn_rate = used / budget if budget > 0 else 0.0
            return remaining, burn_rate
        if target.slo_type == SLOType.ERROR_RATE:
            budget = target.target_value
            used = current_value
            remaining = max(0.0, budget - used)
            burn_rate = used / budget if budget > 0 else 0.0
            return remaining, burn_rate
        return 1.0, 0.0


__all__ = ["AsyncRedisSLOTracker"]
