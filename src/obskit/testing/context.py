"""
Test Context Managers
=====================

Context managers for controlling obskit behavior in tests.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from obskit.testing.mocks import MockMetrics, MockSLOTracker, MockTracer


class ObskitTestContext:
    """
    Context for testing with mocked obskit components.

    Example
    -------
    >>> ctx = ObskitTestContext()
    >>> with ctx:
    ...     result = my_function()
    >>> ctx.metrics.assert_request_recorded("my_operation")
    """

    def __init__(self):
        self.metrics = MockMetrics()
        self.tracer = MockTracer()
        self.slo_tracker = MockSLOTracker()
        self._patches = []

    def __enter__(self):
        # Patch metrics
        self._patches.append(patch("obskit.metrics.REDMetrics", return_value=self.metrics))
        self._patches.append(patch("obskit.metrics.red.get_red_metrics", return_value=self.metrics))

        # Patch tracer
        self._patches.append(patch("obskit.tracing.trace_span", self.tracer.trace_span))
        self._patches.append(patch("obskit.tracing.get_tracer", return_value=self.tracer))

        # Patch SLO tracker
        self._patches.append(patch("obskit.slo.get_slo_tracker", return_value=self.slo_tracker))

        # Start all patches
        for p in self._patches:
            p.start()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Stop all patches
        for p in self._patches:
            p.stop()
        self._patches.clear()
        return False

    def reset(self):
        """Reset all mocks."""
        self.metrics.reset()
        self.tracer.reset()
        self.slo_tracker.reset()


@contextmanager
def disable_observability():
    """
    Completely disable obskit observability.

    All metrics, traces, and SLO measurements are silently ignored.
    Useful for performance tests or when testing non-observability code.

    Example
    -------
    >>> with disable_observability():
    ...     # No metrics or traces recorded
    ...     result = my_heavy_function()
    """
    noop_metrics = MagicMock()
    noop_tracer = MagicMock()
    noop_slo = MagicMock()

    # Make trace_span return a no-op context manager
    @contextmanager
    def noop_span(*args, **kwargs):
        yield MagicMock()

    noop_tracer.trace_span = noop_span

    patches = [
        patch("obskit.metrics.REDMetrics", return_value=noop_metrics),
        patch("obskit.metrics.red.get_red_metrics", return_value=noop_metrics),
        patch("obskit.metrics.GoldenSignals", return_value=noop_metrics),
        patch("obskit.metrics.USEMetrics", return_value=noop_metrics),
        patch("obskit.tracing.trace_span", noop_span),
        patch("obskit.tracing.get_tracer", return_value=noop_tracer),
        patch("obskit.slo.get_slo_tracker", return_value=noop_slo),
        patch("obskit.get_logger", return_value=MagicMock()),
    ]

    for p in patches:
        p.start()

    try:
        yield
    finally:
        for p in patches:
            p.stop()


@contextmanager
def mock_observability(
    metrics: MockMetrics | None = None,
    tracer: MockTracer | None = None,
    slo_tracker: MockSLOTracker | None = None,
):
    """
    Mock specific obskit components.

    Parameters
    ----------
    metrics : MockMetrics, optional
        Mock metrics instance.
    tracer : MockTracer, optional
        Mock tracer instance.
    slo_tracker : MockSLOTracker, optional
        Mock SLO tracker instance.

    Example
    -------
    >>> mock_metrics = MockMetrics()
    >>> with mock_observability(metrics=mock_metrics):
    ...     my_function()
    >>> mock_metrics.assert_request_recorded("operation")
    """
    ctx = ObskitTestContext()

    if metrics:
        ctx.metrics = metrics
    if tracer:
        ctx.tracer = tracer
    if slo_tracker:
        ctx.slo_tracker = slo_tracker

    with ctx:
        yield ctx


@contextmanager
def capture_metrics():
    """
    Capture all metrics recorded during execution.

    Example
    -------
    >>> with capture_metrics() as metrics:
    ...     my_function()
    >>> print(f"Recorded {len(metrics.requests)} requests")
    """
    mock = MockMetrics()
    with mock.patch():
        yield mock


@contextmanager
def capture_traces():
    """
    Capture all traces created during execution.

    Example
    -------
    >>> with capture_traces() as tracer:
    ...     my_function()
    >>> print(f"Created {len(tracer.spans)} spans")
    """
    mock = MockTracer()
    with mock.patch():
        yield mock


__all__ = [
    "ObskitTestContext",
    "disable_observability",
    "mock_observability",
    "capture_metrics",
    "capture_traces",
]
