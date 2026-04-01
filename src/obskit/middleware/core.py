"""
Shared middleware core -- protocol-agnostic request instrumentation.

All framework-specific middleware (FastAPI, Flask, Django, gRPC) delegates
to this module so that path exclusion, correlation-ID handling, metrics
recording, logging and tracing behave identically regardless of framework.
"""

from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from obskit.core.context import get_correlation_id, set_correlation_id
from obskit.logging import get_logger
from obskit.metrics.red import REDMetrics, get_red_metrics
from obskit.tracing.tracer import extract_trace_context, inject_trace_context

if TYPE_CHECKING:  # pragma: no cover
    from obskit.core.observability import Observability

# Compiled at module level for hot-path performance.
# Allows alphanumeric, hyphens, underscores, and dots up to 128 characters.
# Matches the documented spec: ^[a-zA-Z0-9\-_\.]{1,128}$
# Comfortably fits UUID4 (36 chars), ULID (26 chars), and vendor-prefixed variants.
_CORRELATION_ID_RE = re.compile(r"^[a-zA-Z0-9\-_\.]{1,128}$")

_DEFAULT_EXCLUDE_PATHS: list[str] = ["/health", "/ready", "/live", "/metrics"]

_core_logger = get_logger("obskit.middleware.core")


@dataclass
class RequestContext:
    """Per-request state carried from ``begin_request`` to ``end_request``."""

    start_time: float
    correlation_id: str
    operation: str
    method: str
    path: str
    trace_ctx: Any | None = None
    metrics_recorded: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class MiddlewareCore:
    """Protocol-agnostic request instrumentation logic.

    Parameters
    ----------
    exclude_paths : list[str] | None
        Paths to skip.  Matches exact path or any sub-path
        (e.g. ``/health`` also matches ``/health/detail``).
    track_metrics : bool
        Record RED metrics per request.
    track_logging : bool
        Emit structured ``request_started`` / ``request_completed`` logs.
    track_tracing : bool
        Propagate W3C trace context.
    obs : Observability | None
        Optional explicit observability handle.  When *None* the global
        singletons are used.
    """

    def __init__(
        self,
        exclude_paths: list[str] | None = None,
        track_metrics: bool = True,
        track_logging: bool = True,
        track_tracing: bool = True,
        obs: Observability | None = None,
    ) -> None:
        self.exclude_paths = (
            exclude_paths if exclude_paths is not None else list(_DEFAULT_EXCLUDE_PATHS)
        )
        self.track_metrics = track_metrics
        self.track_logging = track_logging
        self.track_tracing = track_tracing
        self._obs = obs

        self.red_metrics: REDMetrics | None = None
        if self.track_metrics:
            self.red_metrics = obs.metrics if obs is not None else get_red_metrics()

        # Pre-compute normalised exclude prefixes once so should_exclude() avoids
        # per-call rstrip() string allocations on every request.
        self._exclude_prefixes: list[str] = [p.rstrip("/") + "/" for p in self.exclude_paths]

    # ── Path exclusion ────────────────────────────────────────────────

    def should_exclude(self, path: str) -> bool:
        """Return *True* if *path* matches an excluded prefix."""
        for excluded, prefix in zip(self.exclude_paths, self._exclude_prefixes, strict=True):
            if path == excluded or path.startswith(prefix):
                return True
        return False

    # ── Correlation ID ────────────────────────────────────────────────

    @staticmethod
    def extract_correlation_id(headers: dict[str, str]) -> str:
        """Extract and validate a correlation ID from *headers*, or generate one."""
        # Check common casings; also do a case-insensitive lookup as fallback
        raw = headers.get("x-correlation-id") or headers.get("X-Correlation-ID")
        if raw is None:
            for key, value in headers.items():
                if key.lower() == "x-correlation-id":
                    raw = value
                    break
        if raw is not None and _CORRELATION_ID_RE.match(raw):
            return raw
        # secrets.token_hex(16) = os.urandom(16).hex() — 32 lowercase hex chars,
        # ~300 ns vs uuid4's ~1.65 µs, and passes _CORRELATION_ID_RE.
        return secrets.token_hex(16)

    # ── Request lifecycle ─────────────────────────────────────────────

    def begin_request(
        self,
        headers: dict[str, str],
        path: str,
        method: str,
        operation: str | None = None,
        client_ip: str | None = None,
    ) -> RequestContext:
        """Start instrumenting a request.  Returns a :class:`RequestContext`."""
        correlation_id = self.extract_correlation_id(headers)
        set_correlation_id(correlation_id)

        if operation is None:
            operation = path.replace("/", "_").strip("_") or "unknown"

        trace_ctx = None
        if self.track_tracing:
            trace_ctx = extract_trace_context(headers)

        ctx = RequestContext(
            start_time=time.perf_counter(),
            correlation_id=correlation_id,
            operation=operation,
            method=method,
            path=path,
            trace_ctx=trace_ctx,
        )

        if self.track_logging:
            _core_logger.info(
                "request_started",
                method=method,
                path=path,
                operation=operation,
                correlation_id=correlation_id,
                client_ip=client_ip,
            )

        return ctx

    def end_request(
        self,
        ctx: RequestContext,
        status_code: int,
        *,
        operation_override: str | None = None,
    ) -> None:
        """Record metrics and log for a completed request."""
        if ctx.metrics_recorded:
            return

        duration_seconds = time.perf_counter() - ctx.start_time
        duration_ms = duration_seconds * 1000
        effective_op = operation_override or ctx.operation
        is_success = status_code < 400

        if self.track_metrics and self.red_metrics:
            self.red_metrics.observe_request(
                operation=effective_op,
                duration_seconds=duration_seconds,
                status="success" if is_success else "failure",
                error_type=None if is_success else f"HTTP{status_code}",
            )

        if self.track_logging:
            _core_logger.info(
                "request_completed",
                method=ctx.method,
                path=ctx.path,
                operation=effective_op,
                status_code=status_code,
                duration_ms=duration_ms,
                correlation_id=ctx.correlation_id,
            )

        ctx.metrics_recorded = True

    def record_error(
        self,
        ctx: RequestContext,
        error: Exception,
    ) -> None:
        """Record metrics and log for a failed request."""
        if ctx.metrics_recorded:
            return

        duration_seconds = time.perf_counter() - ctx.start_time
        duration_ms = duration_seconds * 1000

        if self.track_metrics and self.red_metrics:
            self.red_metrics.observe_request(
                operation=ctx.operation,
                duration_seconds=duration_seconds,
                status="failure",
                error_type=type(error).__name__,
            )

        if self.track_logging:
            _core_logger.error(
                "request_failed",
                method=ctx.method,
                path=ctx.path,
                operation=ctx.operation,
                error_type=type(error).__name__,
                duration_ms=duration_ms,
                correlation_id=ctx.correlation_id,
                exc_info=True,
            )

        ctx.metrics_recorded = True

    # ── Response headers ──────────────────────────────────────────────

    def response_headers(self, ctx: RequestContext) -> list[tuple[str, str]]:
        """Return headers to inject into the response."""
        out: list[tuple[str, str]] = []

        correlation_id = get_correlation_id() or ctx.correlation_id
        out.append(("X-Correlation-ID", correlation_id))

        if self.track_tracing:
            trace_out = inject_trace_context({})
            if trace_out:
                for key, value in trace_out.items():
                    out.append((key, value))

        return out
