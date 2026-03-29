"""Auto-instrumentation detection and application for OpenTelemetry.

Detects which OTel instrumentation packages are installed and applies
them automatically, enabling zero-code tracing for common libraries
(FastAPI, SQLAlchemy, Redis, httpx, Celery, …).

Usage::

    from obskit.tracing.auto import apply_instrumentors, detect_available_instrumentors

    # Auto-detect everything that's installed
    applied = apply_instrumentors()

    # Explicit list
    applied = apply_instrumentors(["fastapi", "sqlalchemy", "redis"])

    # Check what's available without applying
    available = detect_available_instrumentors()
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Instrumentor registry
# Maps a friendly name to (OTel instrumentation module, class name).
# New libraries can be added here without changing any other code.
# ---------------------------------------------------------------------------
_INSTRUMENTORS: dict[str, tuple[str, str]] = {
    "fastapi": (
        "opentelemetry.instrumentation.fastapi",
        "FastAPIInstrumentor",
    ),
    "sqlalchemy": (
        "opentelemetry.instrumentation.sqlalchemy",
        "SQLAlchemyInstrumentor",
    ),
    "redis": (
        "opentelemetry.instrumentation.redis",
        "RedisInstrumentor",
    ),
    "httpx": (
        "opentelemetry.instrumentation.httpx",
        "HTTPXClientInstrumentor",
    ),
    "celery": (
        "opentelemetry.instrumentation.celery",
        "CeleryInstrumentor",
    ),
    "django": (
        "opentelemetry.instrumentation.django",
        "DjangoInstrumentor",
    ),
    "requests": (
        "opentelemetry.instrumentation.requests",
        "RequestsInstrumentor",
    ),
    "grpc_server": (
        "opentelemetry.instrumentation.grpc",
        "GrpcInstrumentorServer",
    ),
    "grpc_client": (
        "opentelemetry.instrumentation.grpc",
        "GrpcInstrumentorClient",
    ),
    "aiopika": (
        "opentelemetry.instrumentation.aio_pika",
        "AioPikaInstrumentor",
    ),
    # psycopg3 (modern async-capable PostgreSQL driver)
    "psycopg": (
        "opentelemetry.instrumentation.psycopg",
        "PsycopgInstrumentor",
    ),
    # psycopg2 (classic synchronous PostgreSQL driver)
    "psycopg2": (
        "opentelemetry.instrumentation.psycopg2",
        "Psycopg2Instrumentor",
    ),
}

# Active instrumentor instances (name → instance).
# Kept as module-level state so uninstrument_all() can tear them down.
_applied: dict[str, Any] = {}

# Instrumentors that previously failed — allowed to retry on next call.
_failed_instrumentors: set[str] = set()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_available_instrumentors() -> list[str]:
    """Return names of all instrumentors whose packages are installed.

    This is a read-only probe — it performs no patching.

    Returns:
        Sorted list of instrumentor names that are importable.

    Example::

        available = detect_available_instrumentors()
        # e.g. ["fastapi", "redis", "sqlalchemy"]
    """
    available: list[str] = []
    for name, (module_path, _) in _INSTRUMENTORS.items():
        try:
            importlib.import_module(module_path)
            available.append(name)
        except ImportError:
            pass  # NOSONAR
    return available


def apply_instrumentors(instruments: list[str] | None = None) -> list[str]:
    """Apply OTel auto-instrumentation for requested libraries.

    Args:
        instruments: Names to instrument.  If *None*, auto-detects all
                     available ones via :func:`detect_available_instrumentors`.

    Returns:
        Names of instrumentors that were successfully applied (or were
        already applied from a previous call).

    Notes:
        * Calling this function twice with the same name is idempotent —
          the second call is a no-op and the name is still returned.
        * Unknown names are logged at WARNING and skipped.
        * Import errors (package not installed) are logged at DEBUG.
        * Runtime errors during ``.instrument()`` are logged at WARNING.

    Example::

        applied = apply_instrumentors(["fastapi", "redis"])
    """
    targets: list[str] = (
        instruments if instruments is not None else detect_available_instrumentors()
    )
    applied_names: list[str] = []

    for name in targets:
        if name not in _INSTRUMENTORS:
            _logger.warning(
                "Unknown OTel instrumentor %r — skipping. Known instrumentors: %s",
                name,
                sorted(_INSTRUMENTORS.keys()),
            )
            continue

        if name in _applied:
            # Already active in this process — idempotent
            # But if it previously failed, allow retry by not short-circuiting
            if name not in _failed_instrumentors:
                applied_names.append(name)
                continue

        module_path, class_name = _INSTRUMENTORS[name]
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            instance = cls()
            instance.instrument()
            _applied[name] = instance
            _failed_instrumentors.discard(name)  # Clear failure record on success
            applied_names.append(name)
            _logger.debug("Applied OTel auto-instrumentation: %s", name)
        except ImportError:
            _failed_instrumentors.add(name)
            _logger.debug(
                "OTel instrumentation package not installed: %s (%s)",
                name,
                module_path,
            )
        except Exception as exc:
            _failed_instrumentors.add(name)
            _logger.warning(
                "Failed to apply OTel instrumentor %r: %s",
                name,
                exc,
            )

    return applied_names


def uninstrument_all() -> None:
    """Remove all applied instrumentors.

    Calls ``.uninstrument()`` on every active instance and clears the
    registry.  Primarily intended for test teardown and hot-reload
    scenarios.  Errors from ``.uninstrument()`` are swallowed to ensure
    cleanup always completes.
    """
    for _name, instance in list(_applied.items()):
        try:
            instance.uninstrument()
        except Exception:  # noqa: BLE001 — uninstrument errors must not block cleanup
            pass  # NOSONAR
    _applied.clear()
    _failed_instrumentors.clear()


def get_applied_instrumentors() -> list[str]:
    """Return names of currently active instrumentors.

    Returns:
        A snapshot (copy) of the applied instrumentor names.
    """
    return list(_applied.keys())


def get_failed_instrumentors() -> list[str]:
    """Return names of instrumentors that failed to apply on the last attempt.

    Useful for health checks and startup diagnostics — if an expected
    instrumentation package is installed but its instrumentor failed,
    this will surface it.

    Returns:
        A snapshot (copy) of the failed instrumentor names.
    """
    return list(_failed_instrumentors)


def get_instrumentor_registry() -> dict[str, tuple[str, str]]:
    """Return a copy of the full instrumentor registry.

    Useful for introspection — shows every instrumentor name obskit
    knows about along with its (module_path, class_name).
    """
    return dict(_INSTRUMENTORS)
