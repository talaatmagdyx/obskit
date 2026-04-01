"""
SQLAlchemy Instrumentation
==========================

This module provides automatic instrumentation for SQLAlchemy engines,
tracking all queries automatically.
"""

from __future__ import annotations

from typing import Any

from obskit.logging import get_logger
from obskit.metrics.red import get_red_metrics

logger = get_logger("obskit.integrations.db.sqlalchemy")


def instrument_sqlalchemy(engine: Any, database_name: str = "database") -> None:
    """
    Instrument a SQLAlchemy engine for automatic query tracking.

    This function adds event listeners to track:
    - Query execution time
    - Connection pool metrics
    - Slow queries
    - Query errors

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
        SQLAlchemy engine to instrument.

    database_name : str, optional
        Name for the database in metrics. Default: "database".

    Example
    -------
    >>> from sqlalchemy import create_engine
    >>> from obskit.integrations.db import instrument_sqlalchemy
    >>>
    >>> engine = create_engine("postgresql://user:pass@localhost/db")
    >>> instrument_sqlalchemy(engine, database_name="postgres")
    >>>
    >>> # All queries are now automatically tracked
    >>> result = engine.execute("SELECT * FROM users")
    """
    try:
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        if not isinstance(engine, Engine):
            logger.warning(
                "invalid_sqlalchemy_engine",
                message="Expected SQLAlchemy Engine instance",
            )
            return

        red = get_red_metrics()

        # Listen on the specific engine INSTANCE (not the Engine class).
        # Using the class would register global listeners that fire for ALL
        # SQLAlchemy engines in the process — including those created by
        # third-party libraries — causing double-instrumentation and data
        # pollution when instrument_sqlalchemy() is called more than once.
        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(
            conn: Any,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: Any,
            executemany: bool,
        ) -> None:
            """Track query start."""
            context._query_start_time = __import__("time").perf_counter()
            context._query_statement = statement

        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(
            conn: Any,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: Any,
            executemany: bool,
        ) -> None:
            """Track query completion."""
            if hasattr(context, "_query_start_time"):
                duration = __import__("time").perf_counter() - context._query_start_time
                duration_ms = duration * 1000

                # Track query duration
                red.observe_request(
                    operation=f"{database_name}.query",
                    duration_seconds=duration,
                )

                # Track slow queries
                if duration_ms > 1000.0:  # 1 second
                    logger.warning(
                        "slow_sql_query",
                        database=database_name,
                        duration_ms=duration_ms,
                        query=statement[:200],  # First 200 chars
                    )

        @event.listens_for(engine, "handle_error")
        def handle_error(exception_context: Any) -> None:
            """Track query errors."""
            logger.error(
                "sql_query_error",
                database=database_name,
                error=str(exception_context.original_exception),
                error_type=type(exception_context.original_exception).__name__,
            )

        # Track connection pool metrics
        @event.listens_for(engine, "connect")
        def on_connect(dbapi_conn: Any, connection_record: Any) -> None:
            """Track connection creation."""
            logger.debug(
                "sqlalchemy_connection_created",
                database=database_name,
            )

        logger.info(
            "sqlalchemy_instrumented",
            database=database_name,
            engine=str(engine.url),
        )

    except ImportError:
        logger.warning(
            "sqlalchemy_not_available",
            message="SQLAlchemy not installed. Install with: pip install sqlalchemy",
        )


__all__ = ["instrument_sqlalchemy"]
