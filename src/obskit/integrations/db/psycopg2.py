"""
psycopg2 OpenTelemetry instrumentation for obskit.

Requires: pip install obskit[psycopg2]  or  obskit[integrations]
"""
from __future__ import annotations

from typing import Any

try:
    from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
except ImportError as e:
    raise ImportError(
        "psycopg2 instrumentation requires opentelemetry-instrumentation-psycopg2 "
        "and psycopg2-binary. "
        "Install: pip install obskit[psycopg2]  or  obskit[integrations]"
    ) from e


def instrument_psycopg2(
    *,
    tracer_provider: Any = None,
    capture_parameters: bool = False,
    enable_commenter: bool = False,
) -> None:
    """Activate OTel auto-instrumentation for all psycopg2 connections globally.

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
    Psycopg2Instrumentor().instrument(
        tracer_provider=tracer_provider,
        capture_parameters=capture_parameters,
        enable_commenter=enable_commenter,
    )


def instrument_psycopg2_connection(
    connection: Any,
    *,
    tracer_provider: Any = None,
) -> Any:
    """Instrument a single psycopg2 connection instance.

    Use this for per-connection instrumentation instead of global.

    Parameters
    ----------
    connection:
        A psycopg2 connection object.
    tracer_provider:
        Optional custom TracerProvider.

    Returns
    -------
    The instrumented connection.
    """
    return Psycopg2Instrumentor().instrument_connection(  # type: ignore[no-untyped-call]
        connection,
        tracer_provider=tracer_provider,
    )


__all__ = ["instrument_psycopg2", "instrument_psycopg2_connection"]
