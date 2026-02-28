"""Unified tracing setup for obskit services.

Single entry point that:

1. Reads service identity from obskit-core settings.
2. Configures the OpenTelemetry SDK (TracerProvider + OTLP exporter).
3. Optionally applies auto-instrumentation for all installed libraries.

Call :func:`setup_tracing` **once** at application startup, **before**
importing instrumented libraries (FastAPI, SQLAlchemy, etc.) so that
OpenTelemetry can patch them before they are first loaded.

Example — minimal (reads everything from obskit-core config)::

    from obskit.tracing import setup_tracing
    setup_tracing()

Example — explicit exporter and library list::

    from obskit.tracing import setup_tracing
    setup_tracing(
        exporter_endpoint="http://tempo:4317",
        instrument=["fastapi", "sqlalchemy", "redis"],
    )

Example — local development (print spans to stdout, no collector needed)::

    from obskit.tracing import setup_tracing
    setup_tracing(debug=True)

Example — production with 10 % sampling::

    from obskit.tracing import setup_tracing
    setup_tracing(
        exporter_endpoint="http://tempo:4317",
        sample_rate=0.1,
    )

Example — manual spans only, no auto-instrumentation::

    from obskit.tracing import setup_tracing
    setup_tracing(auto_instrument=False)
"""

from __future__ import annotations

from obskit.tracing.auto import apply_instrumentors
from obskit.tracing.tracer import configure_tracing


def setup_tracing(
    *,
    exporter_endpoint: str | None = None,
    auto_instrument: bool = True,
    instrument: list[str] | None = None,
    service_name: str | None = None,
    debug: bool = False,
    sample_rate: float = 1.0,
) -> list[str]:
    """Configure OTel tracing and optionally apply auto-instrumentation.

    Args:
        exporter_endpoint: OTLP endpoint URL (e.g. ``"http://tempo:4317"``).
                           Falls back to ``obskit-core`` settings when *None*.
        auto_instrument: When *True* (default), auto-detect and instrument
                         every installed OTel instrumentation package.
        instrument: Explicit list of instrumentor names to apply
                    (e.g. ``["fastapi", "redis"]``).  When *None* and
                    *auto_instrument* is *True*, all available ones are used.
                    Ignored when *auto_instrument* is *False*.
        service_name: Service name override.  Falls back to
                      ``obskit-core`` settings when *None*.
        debug: When *True*, print every span to stdout via
               ``ConsoleSpanExporter``.  Ideal for local development —
               no Tempo / Jaeger collector required.
        sample_rate: Fraction of traces to keep in ``[0.0, 1.0]``.
                     ``1.0`` keeps every trace (default).  Uses
                     W3C-compliant ``ParentBased(TraceIdRatioBased)``
                     so the decision propagates across services.

    Returns:
        List of instrumentor names that were successfully applied.
        Empty list when *auto_instrument* is *False*.

    Raises:
        Nothing — all internal errors are logged and swallowed.

    Example::

        # Kitchen-sink install, then call once at startup:
        # pip install "obskit-tracing[auto]"

        from obskit.tracing import setup_tracing

        applied = setup_tracing(
            exporter_endpoint="http://localhost:4317",
            instrument=["fastapi", "sqlalchemy", "redis", "httpx"],
        )
        print("Instrumented:", applied)
        # Instrumented: ['fastapi', 'sqlalchemy', 'redis', 'httpx']
    """
    configure_tracing(
        service_name=service_name,
        otlp_endpoint=exporter_endpoint,
        debug=debug,
        sample_rate=sample_rate,
    )

    if not auto_instrument:
        return []

    return apply_instrumentors(instrument)
