"""
Head-based trace sampling with optional always-sample-errors promotion.

Usage
-----
Call :func:`configure_trace_sampling` once at startup, before or after
:func:`obskit.configure_observability`:

.. code-block:: python

    from obskit import configure_trace_sampling

    # 10 % sampling, keep 100 % of error traces
    configure_trace_sampling(head_rate=0.1, always_sample_errors=True)

How ``always_sample_errors`` works
-----------------------------------
The SDK sampler returns ``RECORD_ONLY`` (instead of ``DROP``) for spans that
would otherwise be discarded.  :class:`ErrorPromotionSpanProcessor` watches
every span on ``on_end``; if the span's status is ``StatusCode.ERROR`` **and**
it was not in the sampled set, it is exported directly to the OTLP exporter.

Limitation: only the error span itself is force-exported — parent spans that
were already discarded before the error occurred will not be present in Tempo.
The error span retains its ``trace_id`` and ``parent_span_id``, so you can
correlate it with sampled portions of the trace.  For full-trace error
preservation, configure tail-based sampling in the OpenTelemetry Collector
instead.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Module-level config store
# ---------------------------------------------------------------------------

_SAMPLING_LOCK: threading.Lock = threading.Lock()
_SAMPLING_CONFIG: dict[str, Any] | None = None


def configure_trace_sampling(
    head_rate: float,
    *,
    always_sample_errors: bool = True,
) -> None:
    """Configure head-based trace sampling with optional error promotion.

    Can be called **before** or **after** :func:`~obskit.configure_observability`:

    * **Before** — stores the config; :func:`~obskit.tracing.tracer.configure_tracing`
      picks it up when it creates the ``TracerProvider``.
    * **After** — patches the active ``TracerProvider``'s sampler in-place.

    Parameters
    ----------
    head_rate:
        Fraction of traces to sample, in ``[0.0, 1.0]``.
        ``1.0`` keeps every trace; ``0.1`` keeps 10 %.
        Uses ``ParentBased(TraceIdRatioBased)`` so the decision propagates
        across services via W3C ``traceparent``.
    always_sample_errors:
        When *True* (default), spans that end with ``StatusCode.ERROR`` are
        always exported even if the trace was not in the sample.  See module
        docstring for limitations.

    Raises
    ------
    ValueError
        If *head_rate* is outside ``[0.0, 1.0]``.

    Example::

        from obskit import configure_trace_sampling, configure_observability

        configure_trace_sampling(head_rate=0.1, always_sample_errors=True)
        configure_observability(service_name="worker", otlp_endpoint="http://tempo:4317")
    """
    if not 0.0 <= head_rate <= 1.0:
        raise ValueError(
            f"head_rate must be between 0.0 and 1.0, got {head_rate!r}"
        )

    global _SAMPLING_CONFIG
    with _SAMPLING_LOCK:
        _SAMPLING_CONFIG = {
            "head_rate": head_rate,
            "always_sample_errors": always_sample_errors,
        }

    # Best-effort: also patch the active provider if one is already running.
    _apply_sampling_to_provider(head_rate, always_sample_errors)


def get_sampling_config() -> dict[str, Any] | None:
    """Return the stored sampling config, or *None* if not set.

    Used by :func:`~obskit.tracing.tracer.configure_tracing` to override the
    ``sample_rate`` parameter with the value from :func:`configure_trace_sampling`.
    """
    with _SAMPLING_LOCK:
        return dict(_SAMPLING_CONFIG) if _SAMPLING_CONFIG is not None else None


# ---------------------------------------------------------------------------
# Sampler construction
# ---------------------------------------------------------------------------

def build_sampler(head_rate: float, always_sample_errors: bool = False) -> Any:
    """Build the OTel sampler for the given config.

    Parameters
    ----------
    head_rate:
        Fraction in ``[0.0, 1.0]``.  ``1.0`` → :data:`ALWAYS_ON`.
    always_sample_errors:
        Wrap the ratio sampler with :class:`_RecordAndSampleErrors` so that
        non-sampled spans are ``RECORD_ONLY`` (not ``DROP``) and can be
        force-exported on error.

    Returns
    -------
    Any
        An OTel :class:`~opentelemetry.sdk.trace.sampling.Sampler` instance.
    """
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_ON,
        ParentBased,
        TraceIdRatioBased,
    )

    if head_rate >= 1.0:
        return ALWAYS_ON

    base: Any = ParentBased(root=TraceIdRatioBased(head_rate))

    if always_sample_errors:
        return _RecordAndSampleErrors(base)

    return base


# ---------------------------------------------------------------------------
# Custom sampler: RECORD_ONLY instead of DROP
# ---------------------------------------------------------------------------

class _RecordAndSampleErrors:
    """Wraps an inner sampler, returning ``RECORD_ONLY`` instead of ``DROP``.

    This keeps span data in memory for non-sampled traces so that
    :class:`ErrorPromotionSpanProcessor` can export them if they end with
    an error.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def should_sample(
        self,
        parent_context: Any,
        trace_id: int,
        name: str,
        kind: Any = None,
        attributes: Any = None,
        links: Any = None,
        trace_state: Any = None,
    ) -> Any:
        from opentelemetry.sdk.trace.sampling import Decision, SamplingResult

        result = self._inner.should_sample(
            parent_context, trace_id, name, kind, attributes, links, trace_state
        )

        if result.decision == Decision.DROP:
            return SamplingResult(
                decision=Decision.RECORD_ONLY,
                attributes=result.attributes,
                trace_state=result.trace_state,
            )

        return result

    def get_description(self) -> str:
        return f"RecordAndSampleErrors({self._inner.get_description()})"


# ---------------------------------------------------------------------------
# Span processor: force-export error spans that were not sampled
# ---------------------------------------------------------------------------

class ErrorPromotionSpanProcessor:
    """Exports ``StatusCode.ERROR`` spans even when not in the sample.

    Attach this processor to the ``TracerProvider`` alongside the normal
    :class:`~opentelemetry.sdk.trace.export.BatchSpanProcessor`.  It is a
    no-op for sampled spans (those are handled by the batch processor already)
    and for non-error spans.

    Parameters
    ----------
    exporter:
        The :class:`~opentelemetry.sdk.trace.export.SpanExporter` to use for
        force-exported error spans.  Typically the same OTLP exporter used by
        the ``BatchSpanProcessor``.
    """

    def __init__(self, exporter: Any) -> None:
        self._exporter = exporter

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        pass

    def on_end(self, span: Any) -> None:
        try:
            from opentelemetry.trace import StatusCode

            if (
                span.status.status_code == StatusCode.ERROR
                and not span.context.trace_flags.sampled
            ):
                self._exporter.export([span])
        except Exception:  # pragma: no cover
            pass  # defensive — never break the caller

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_sampling_to_provider(head_rate: float, always_sample_errors: bool) -> None:
    """Patch the sampler on the active TracerProvider, if one exists."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            return  # No SDK provider active yet — configure_tracing will use stored config

        sampler = build_sampler(head_rate, always_sample_errors)
        provider._sampler = sampler

        if always_sample_errors:
            _attach_error_promotion_processor(provider)
    except Exception:  # pragma: no cover
        pass  # Best effort — don't break the caller


def _attach_error_promotion_processor(provider: Any) -> None:
    """Add an ErrorPromotionSpanProcessor to *provider* using the BSP's exporter."""
    try:
        from obskit.tracing.tracer import _batch_span_processor

        if _batch_span_processor is None:
            return

        exporter = getattr(_batch_span_processor, "span_exporter", None)
        if exporter is None:  # pragma: no branch
            return  # pragma: no cover

        provider.add_span_processor(ErrorPromotionSpanProcessor(exporter))
    except Exception:  # pragma: no cover
        pass


__all__ = [
    "configure_trace_sampling",
    "get_sampling_config",
    "build_sampler",
    "ErrorPromotionSpanProcessor",
]
