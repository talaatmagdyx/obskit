"""
psycopg3 (psycopg) OpenTelemetry instrumentation for obskit.

Supports both sync psycopg.Connection and async psycopg.AsyncConnection.

Requires: pip install obskit[psycopg3]  or  obskit[integrations]
"""

from __future__ import annotations

from typing import Any

try:
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
except ImportError as e:
    raise ImportError(
        "psycopg3 instrumentation requires opentelemetry-instrumentation-psycopg "
        "and psycopg>=3.1.0. "
        "Install: pip install obskit[psycopg3]  or  obskit[integrations]"
    ) from e


def instrument_psycopg3(
    *,
    tracer_provider: Any = None,
    capture_parameters: bool = False,
    enable_commenter: bool = False,
) -> None:
    """Activate OTel auto-instrumentation for all psycopg3 connections globally.

    Works with both psycopg.Connection (sync) and psycopg.AsyncConnection (async).
    Call once at application startup before any connections are created.

    Parameters
    ----------
    tracer_provider:
        Optional custom TracerProvider. Defaults to the global provider.
    capture_parameters:
        If True, SQL query parameters are captured as span attributes.
        Disable in production to avoid leaking sensitive data.
    enable_commenter:
        If True, appends a SQL comment with trace context to each query.
    """
    PsycopgInstrumentor().instrument(
        tracer_provider=tracer_provider,
        capture_parameters=capture_parameters,
        enable_commenter=enable_commenter,
    )


def instrument_psycopg3_connection(
    connection: Any,
    *,
    tracer_provider: Any = None,
) -> Any:
    """Instrument a single psycopg3 connection instance.

    Works with both sync and async connections.

    Parameters
    ----------
    connection:
        A psycopg.Connection or psycopg.AsyncConnection object.
    tracer_provider:
        Optional custom TracerProvider.

    Returns
    -------
    The instrumented connection.
    """
    return PsycopgInstrumentor().instrument_connection(
        connection,
        tracer_provider=tracer_provider,
    )


__all__ = ["instrument_psycopg3", "instrument_psycopg3_connection"]
