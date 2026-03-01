"""Prometheus trace exemplar support.

OpenMetrics exemplars attach a trace-id to individual histogram or
summary observations, so a Prometheus/Grafana stack can display a
clickable link from a latency spike to the exact Tempo trace that caused
it.

How exemplars work
------------------
A Prometheus exemplar is a key-value dictionary that is stored alongside
a single metric observation.  The Grafana/Tempo integration uses the
``trace_id`` key to render a direct link from a metric panel to the
trace viewer.

.. code-block:: text

    # TYPE request_duration_seconds histogram
    request_duration_seconds_bucket{le="0.5"} 42 # {trace_id="4bf92f35..."} 1
    request_duration_seconds_bucket{le="1.0"} 50 # {trace_id="4bf92f35..."} 1

Requirements
------------
*   ``prometheus-client >= 0.16.0``  (exemplar support was added there)
*   ``opentelemetry-api`` installed (for reading the current span context)

If either package is absent the helpers silently fall back to plain
observations — no code changes needed.

Usage
-----
Standalone helper — wraps any prometheus_client Histogram::

    from obskit.metrics.exemplar import observe_with_exemplar
    from prometheus_client import Histogram

    h = Histogram("req_duration_seconds", "...", ["operation"])
    observe_with_exemplar(h.labels(operation="create_order"), 0.045)

With REDMetrics / GoldenSignals — pass ``exemplars=True``::

    from obskit.metrics import REDMetrics

    red = REDMetrics("order_service")
    red.observe_request("create_order", 0.045, exemplars=True)

Grafana dashboard setup
-----------------------
1. Enable exemplar storage in Prometheus (``--enable-feature=exemplar-storage``).
2. In Grafana, go to your histogram panel → Query → enable "Exemplars".
3. Trace links appear on the panel when you zoom into spike areas.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# OTel availability check
# ---------------------------------------------------------------------------

try:
    from opentelemetry import trace as _otel_trace

    _OTEL_AVAILABLE = True
except ImportError:
    _otel_trace = None  # type: ignore[assignment]
    _OTEL_AVAILABLE = False

# ---------------------------------------------------------------------------
# prometheus-client exemplar availability check
# ---------------------------------------------------------------------------

try:
    # exemplar support was added in 0.16.0; test by importing the flag
    from prometheus_client import REGISTRY as _REGISTRY  # noqa: F401

    _PROM_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PROM_AVAILABLE = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_trace_exemplar() -> dict[str, str]:
    """Return ``{"trace_id": "...", "span_id": "..."}`` for the active span.

    Returns an empty dict when:
    *   ``opentelemetry-api`` is not installed, or
    *   no span is currently active.

    Grafana's Tempo integration uses the ``trace_id`` key to link metric
    data-points to the corresponding trace.

    Returns:
        Dict with ``trace_id`` (32 hex chars) and ``span_id`` (16 hex chars),
        or ``{}`` if no valid span is active.

    Example::

        exemplar = get_trace_exemplar()
        # {"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        #  "span_id":  "00f067aa0ba902b7"}
    """
    if not _OTEL_AVAILABLE or _otel_trace is None:
        return {}

    try:
        span = _otel_trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.is_valid:
            return {
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
            }
    except Exception:  # nosec B110
        pass  # NOSONAR

    return {}


def observe_with_exemplar(
    metric_object: Any,
    value: float,
    exemplar: dict[str, str] | None = None,
) -> None:
    """Observe a prometheus_client metric with an auto-injected trace exemplar.

    If *exemplar* is ``None``, :func:`get_trace_exemplar` is called
    automatically to read the current span context.  If no span is active
    the observation is recorded without an exemplar (plain ``observe``).

    Args:
        metric_object: A labeled prometheus_client metric returned by
                       ``Histogram.labels(...)`` or ``Summary.labels(...)``.
        value: The observation value (e.g. duration in seconds).
        exemplar: Explicit exemplar dict.  Pass ``{}`` to suppress
                  auto-injection.  Pass ``None`` to auto-detect.

    Example::

        from prometheus_client import Histogram
        from obskit.metrics.exemplar import observe_with_exemplar

        h = Histogram("http_latency_seconds", "Latency", ["method"])
        observe_with_exemplar(h.labels(method="GET"), 0.032)
    """
    exc = exemplar if exemplar is not None else get_trace_exemplar()

    if exc:
        try:
            metric_object.observe(value, exemplar=exc)
            return
        except TypeError:
            # Older prometheus-client versions don't support `exemplar` kwarg
            pass  # NOSONAR
        except Exception:  # nosec B110
            pass  # NOSONAR

    # Fallback: plain observe (no exemplar)
    metric_object.observe(value)


def is_exemplar_available() -> bool:
    """Return *True* when both OTel and prometheus-client are available.

    Example::

        if is_exemplar_available():
            print("Exemplar links enabled in Grafana")
    """
    return _OTEL_AVAILABLE and _PROM_AVAILABLE
