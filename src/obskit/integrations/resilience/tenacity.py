"""
Tenacity retry instrumentation for obskit.

Wraps a :mod:`tenacity` ``Retrying`` (or ``AsyncRetrying``) decorator so that
retry attempts and exhaustion events are exported as Prometheus metrics.

Metrics emitted
---------------
``retry_attempts_total{name, attempt_number}``
    Counter: incremented via the ``before_sleep`` hook each time an attempt
    fails and a retry is scheduled.  *attempt_number* is the number of the
    attempt that just failed (``"1"`` means the first attempt failed and a
    second will be tried).

``retry_exhausted_total{name}``
    Counter: incremented via the ``after`` hook when the stop condition is
    reached on a failed attempt — i.e. all retries have been exhausted.

Example (``tenacity.retry`` shorthand — tenacity 9.x)
------------------------------------------------------
.. code-block:: python

    from tenacity import retry, retry_if_exception_type, stop_after_attempt
    from tenacity import wait_exponential_jitter
    from obskit.integrations.resilience.tenacity import instrument_tenacity

    platform_retry = instrument_tenacity(
        retry(
            retry=retry_if_exception_type(IOError),
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=0.5, max=8),
            reraise=True,
        ),
        name="platform_http",
    )

    @platform_retry
    async def call_api():
        ...

Example (``AsyncRetrying`` instance)
-------------------------------------
.. code-block:: python

    import tenacity
    from obskit.integrations.resilience.tenacity import instrument_tenacity

    platform_retry = instrument_tenacity(
        tenacity.AsyncRetrying(
            retry=tenacity.retry_if_exception_type(IOError),
            stop=tenacity.stop_after_attempt(3),
            wait=tenacity.wait_exponential_jitter(initial=0.5, max=8),
            reraise=True,
        ),
        name="platform_http",
    )

    @platform_retry.wraps
    async def call_api():
        ...
"""

from __future__ import annotations

from typing import Any

from prometheus_client import Counter

RETRY_ATTEMPTS_TOTAL: Counter = Counter(
    "retry_attempts_total",
    "Total retry attempts made (incremented before each sleep between retries)",
    ["name", "attempt_number"],
)

RETRY_EXHAUSTED_TOTAL: Counter = Counter(
    "retry_exhausted_total",
    "Total times all retry attempts were exhausted without success",
    ["name"],
)


def _patch_hooks(retry_instance: Any, name: str) -> None:
    """Patch ``before_sleep`` and ``after`` on a ``Retrying``/``AsyncRetrying`` instance."""
    _orig_before_sleep = getattr(retry_instance, "before_sleep", None)

    def _patched_before_sleep(retry_state: Any) -> None:
        RETRY_ATTEMPTS_TOTAL.labels(
            name=name,
            attempt_number=str(retry_state.attempt_number),
        ).inc()
        if _orig_before_sleep is not None:
            _orig_before_sleep(retry_state)

    retry_instance.before_sleep = _patched_before_sleep

    _orig_after = getattr(retry_instance, "after", None)

    def _patched_after(retry_state: Any) -> None:
        if _orig_after is not None:  # pragma: no branch
            _orig_after(retry_state)
        if retry_state.outcome is not None and retry_state.outcome.failed:
            try:
                if retry_instance.stop(retry_state):
                    RETRY_EXHAUSTED_TOTAL.labels(name=name).inc()
            except Exception:  # pragma: no cover
                pass  # defensive — never break the caller

    retry_instance.after = _patched_after


def instrument_tenacity(retry_obj: Any, name: str) -> Any:
    """Attach Prometheus metrics to a tenacity retry decorator.

    Accepts either a :class:`tenacity.Retrying` / :class:`tenacity.AsyncRetrying`
    instance **or** the decorator factory returned by :func:`tenacity.retry` (the
    ``@retry(...)`` shorthand in tenacity 9.x).

    * **Instance path** — hooks are patched in-place; use with ``.wraps``:

      .. code-block:: python

          retry_obj = instrument_tenacity(
              tenacity.AsyncRetrying(stop=tenacity.stop_after_attempt(3), reraise=True),
              name="my_service",
          )

          @retry_obj.wraps
          async def call_remote():
              ...

    * **Factory path** — a new decorator factory is returned that patches hooks
      each time it is applied to a function:

      .. code-block:: python

          platform_retry = instrument_tenacity(
              retry(stop=stop_after_attempt(3), reraise=True),
              name="platform_http",
          )

          @platform_retry
          async def call_api():
              ...

    Parameters
    ----------
    retry_obj :
        Either a tenacity ``Retrying`` / ``AsyncRetrying`` instance (has a
        ``stop`` attribute) **or** the decorator factory returned by
        ``tenacity.retry(...)`` (a plain callable without a ``stop`` attribute).
    name : str
        Label value for all metric series emitted by this retry context.
        Use a human-readable name such as ``"twitter_api"`` or
        ``"payments_http"``.

    Returns
    -------
    Any
        * If *retry_obj* is an instance: the same object with hooks patched.
        * If *retry_obj* is a factory: a new decorator factory that patches
          hooks on the ``Retrying``/``AsyncRetrying`` object created at
          decoration time.

    Notes
    -----
    * ``retry_attempts_total`` is incremented in ``before_sleep`` — it fires
      for every attempt that fails **and** has a retry scheduled, so a
      3-attempt exhaustion increments attempt_number ``"1"`` and ``"2"`` (the
      last failure is captured by ``retry_exhausted_total`` instead).

    * ``retry_exhausted_total`` is incremented in ``after`` when the stop
      condition is met on a failed attempt.

    * Any pre-existing ``before_sleep`` or ``after`` hook on the retry object
      is preserved and called first / after the metrics hooks.
    """
    # Discriminate between Retrying/AsyncRetrying instances (have a "stop"
    # attribute) and the plain decorator factory returned by tenacity.retry()
    # in tenacity 9.x (a plain function with no "stop" attribute).
    if not hasattr(retry_obj, "stop"):
        # Factory path — wrap the factory so hooks are patched at decoration time.
        _factory = retry_obj

        def _instrumented_factory(fn: Any) -> Any:
            wrapped = _factory(fn)
            retry_instance = getattr(wrapped, "retry", None)
            if retry_instance is not None:  # pragma: no branch
                _patch_hooks(retry_instance, name)
            return wrapped

        return _instrumented_factory

    # Instance path — patch hooks directly on the Retrying/AsyncRetrying object.
    _patch_hooks(retry_obj, name)
    return retry_obj


__all__ = [
    "instrument_tenacity",
    "RETRY_ATTEMPTS_TOTAL",
    "RETRY_EXHAUSTED_TOTAL",
]
