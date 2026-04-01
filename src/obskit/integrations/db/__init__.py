"""
Database Instrumentation
========================

This module provides automatic observability for database operations,
including query duration tracking, connection pool metrics, and slow query detection.

Example - SQLAlchemy Instrumentation
------------------------------------
.. code-block:: python

    from obskit.integrations.db import instrument_sqlalchemy
    from sqlalchemy import create_engine

    engine = create_engine("postgresql://user:pass@localhost/db")

    # Automatically instrument all queries
    instrument_sqlalchemy(engine)

    # Now all queries are automatically tracked:
    # - Query duration metrics
    # - Connection pool metrics
    # - Slow query detection
    # - Error tracking

Example - Manual Query Tracking
-------------------------------
.. code-block:: python

    from obskit.integrations.db import track_query

    async with track_query("get_user", query="SELECT * FROM users WHERE id = ?"):
        result = await db.execute(query, user_id)
"""

from __future__ import annotations

from obskit.integrations.db.tracker import DatabaseTracker, track_query

__all__ = [
    "DatabaseTracker",
    "instrument_sqlalchemy",
    "track_query",
]


def __getattr__(name: str) -> object:
    if name == "instrument_sqlalchemy":
        from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy  # noqa: PLC0415

        globals()["instrument_sqlalchemy"] = instrument_sqlalchemy
        return instrument_sqlalchemy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
