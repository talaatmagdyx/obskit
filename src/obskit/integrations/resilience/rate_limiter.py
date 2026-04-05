"""
Rate limiter Prometheus instrumentation for obskit.

Wraps any rate limiter that exposes ``check()`` and ``record_limit()``
methods, emitting metrics that make throttling events visible in Grafana.

Metrics emitted
---------------
``platform_rate_limit_hits_total{platform}``
    Counter: incremented each time ``check()`` raises an exception
    (i.e. the caller was rate-limited).

``platform_rate_limit_recorded_total{platform}``
    Counter: incremented each time ``record_limit()`` is called.

``platform_rate_limit_reset_seconds{platform}``
    Gauge: seconds until the rate-limit window resets, extracted from
    the exception's ``retry_after`` or ``reset_after`` attribute when
    present.  Stays at 0 when no reset-time information is available.

Example
-------
.. code-block:: python

    from obskit.integrations.resilience.rate_limiter import instrument_rate_limiter

    rate_limiter = instrument_rate_limiter(
        RateLimiter(redis_client, "TWITTER"), platform="twitter"
    )

    # Now check() and record_limit() automatically update Prometheus metrics.
"""

from __future__ import annotations

from typing import Any

from prometheus_client import Counter, Gauge

RATE_LIMIT_HITS_TOTAL = Counter(
    "platform_rate_limit_hits_total",
    "Total number of times a platform rate limit was hit",
    ["platform"],
)

RATE_LIMIT_RECORDED_TOTAL = Counter(
    "platform_rate_limit_recorded_total",
    "Total number of rate-limit events recorded to the backing store",
    ["platform"],
)

RATE_LIMIT_RESET_SECONDS = Gauge(
    "platform_rate_limit_reset_seconds",
    "Seconds until the current rate-limit window resets (0 if unknown)",
    ["platform"],
)


class RateLimiterInstrumentor:
    """Wraps a rate limiter with Prometheus metrics.

    ``check()`` is patched to increment ``platform_rate_limit_hits_total``
    whenever it raises.  If the exception carries a ``retry_after`` or
    ``reset_after`` attribute, ``platform_rate_limit_reset_seconds`` is
    updated automatically.

    ``record_limit()`` is patched to increment
    ``platform_rate_limit_recorded_total``.
    """

    def __init__(self, limiter: Any, platform: str) -> None:
        self._limiter = limiter
        self._platform = platform
        self._patch_limiter()

    def _patch_limiter(self) -> None:
        _platform = self._platform
        _original_check = self._limiter.check
        _original_record = self._limiter.record_limit

        def _patched_check(*args: Any, **kwargs: Any) -> Any:
            try:
                return _original_check(*args, **kwargs)
            except Exception as exc:
                RATE_LIMIT_HITS_TOTAL.labels(platform=_platform).inc()
                reset = getattr(exc, "retry_after", None) or getattr(
                    exc, "reset_after", None
                )
                if reset is not None:
                    RATE_LIMIT_RESET_SECONDS.labels(platform=_platform).set(
                        float(reset)
                    )
                raise

        def _patched_record(*args: Any, **kwargs: Any) -> Any:
            result = _original_record(*args, **kwargs)
            RATE_LIMIT_RECORDED_TOTAL.labels(platform=_platform).inc()
            return result

        self._limiter.check = _patched_check
        self._limiter.record_limit = _patched_record


def instrument_rate_limiter(
    limiter: Any, platform: str = "default"
) -> RateLimiterInstrumentor:
    """Instrument a rate limiter with Prometheus metrics.

    Parameters
    ----------
    limiter:
        Any object with ``check()`` and ``record_limit()`` methods.
    platform:
        Label value used in all metrics.  Default: ``"default"``.

    Returns
    -------
    RateLimiterInstrumentor
        The instrumentor wrapping *limiter*.
    """
    return RateLimiterInstrumentor(limiter, platform)


__all__ = [
    "RateLimiterInstrumentor",
    "instrument_rate_limiter",
    "RATE_LIMIT_HITS_TOTAL",
    "RATE_LIMIT_RECORDED_TOTAL",
    "RATE_LIMIT_RESET_SECONDS",
]
