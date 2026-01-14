"""
Database Query Tracker
======================

This module provides tracking for database queries with metrics and logging.
"""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager

from obskit.logging import get_logger
from obskit.metrics.red import get_red_metrics

logger = get_logger("obskit.db.tracker")


class DatabaseTracker:
    """
    Tracks database operations with metrics and logging.

    Example
    -------
    >>> from obskit.db import DatabaseTracker
    >>>
    >>> tracker = DatabaseTracker("user_db")
    >>>
    >>> with tracker.track_query("get_user", query="SELECT * FROM users"):
    ...     result = db.execute(query)
    """

    def __init__(self, database_name: str) -> None:
        """
        Initialize database tracker.

        Parameters
        ----------
        database_name : str
            Name of the database (e.g., "postgres", "mysql", "mongodb").
        """
        self.database_name = database_name
        self.red_metrics = get_red_metrics()

    @contextmanager
    def track_query(
        self,
        operation: str,
        query: str | None = None,
        slow_query_threshold_ms: float = 1000.0,
    ) -> Generator[None, None, None]:
        """
        Track a database query with metrics and logging.

        Parameters
        ----------
        operation : str
            Operation name (e.g., "get_user", "create_order").

        query : str, optional
            SQL query string (for logging).

        slow_query_threshold_ms : float, optional
            Threshold for slow query detection in milliseconds.
            Default: 1000ms.

        Yields
        ------
        None
        """
        start_time = time.perf_counter()
        full_operation = f"{self.database_name}.{operation}"

        try:
            logger.debug(
                "db_query_started",
                database=self.database_name,
                operation=operation,
                query=query,
            )

            yield

            duration_seconds = time.perf_counter() - start_time
            duration_ms = duration_seconds * 1000

            # Record metrics
            self.red_metrics.observe_request(
                operation=full_operation,
                duration_seconds=duration_seconds,
                status="success",
            )

            # Log slow queries
            if duration_ms > slow_query_threshold_ms:
                logger.warning(
                    "slow_query_detected",
                    database=self.database_name,
                    operation=operation,
                    duration_ms=duration_ms,
                    threshold_ms=slow_query_threshold_ms,
                    query=query,
                )
            else:
                logger.debug(
                    "db_query_completed",
                    database=self.database_name,
                    operation=operation,
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_seconds = time.perf_counter() - start_time

            # Record error metrics
            self.red_metrics.observe_request(
                operation=full_operation,
                duration_seconds=duration_seconds,
                status="failure",
                error_type=type(e).__name__,
            )

            logger.error(
                "db_query_failed",
                database=self.database_name,
                operation=operation,
                error=str(e),
                error_type=type(e).__name__,
                query=query,
                exc_info=True,
            )

            raise


@contextmanager
def track_query(
    operation: str,
    database_name: str = "database",
    query: str | None = None,
    slow_query_threshold_ms: float = 1000.0,
) -> Generator[None, None, None]:
    """
    Track a database query (convenience function).

    Parameters
    ----------
    operation : str
        Operation name.

    database_name : str, optional
        Database name. Default: "database".

    query : str, optional
        SQL query string.

    slow_query_threshold_ms : float, optional
        Slow query threshold in milliseconds.

    Example
    -------
    >>> from obskit.db import track_query
    >>>
    >>> with track_query("get_user", query="SELECT * FROM users"):
    ...     result = db.execute(query)
    """
    tracker = DatabaseTracker(database_name)
    with tracker.track_query(operation, query, slow_query_threshold_ms):
        yield


__all__ = ["DatabaseTracker", "track_query"]
