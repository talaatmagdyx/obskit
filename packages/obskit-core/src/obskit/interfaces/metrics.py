"""
Metrics Interface - Abstract Base Class for Metrics Collectors
===============================================================

This module defines the contract for metrics collection in obskit.
Implementations can use Prometheus, OpenTelemetry metrics, or custom solutions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Generator


class MetricsInterface(ABC):
    """
    Abstract base class for metrics collectors.

    This interface defines the contract for RED method metrics collection.
    Implementations must provide methods for observing requests and tracking
    request lifecycle via context managers.

    Attributes
    ----------
    name : str
        The service or component name for metrics.

    Methods
    -------
    observe_request(operation, duration_seconds, status, error_type)
        Record a request observation.
    track_request(operation)
        Context manager for automatic request tracking.

    Example
    -------
    >>> class MyMetrics(MetricsInterface):
    ...     def observe_request(self, operation, duration_seconds, status, error_type=None):
    ...         print(f"{operation}: {duration_seconds}s, status={status}")
    ...
    ...     @contextmanager
    ...     def track_request(self, operation):
    ...         start = time.time()
    ...         try:
    ...             yield
    ...             self.observe_request(operation, time.time() - start, "success")
    ...         except Exception as e:
    ...             self.observe_request(operation, time.time() - start, "failure", type(e).__name__)
    ...             raise
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the service/component name for metrics."""

    @abstractmethod
    def observe_request(
        self,
        operation: str,
        duration_seconds: float,
        status: Literal["success", "failure"] = "success",
        error_type: str | None = None,
    ) -> None:
        """
        Record a request observation.

        This method updates all relevant metrics:
        - Request counter (rate)
        - Error counter (if status="failure")
        - Duration histogram/summary

        Parameters
        ----------
        operation : str
            Name of the operation (e.g., "create_order", "get_user").
        duration_seconds : float
            Duration of the operation in seconds.
        status : {"success", "failure"}
            Whether the operation succeeded or failed.
        error_type : str, optional
            Type of error if status="failure" (e.g., "ValidationError").

        Example
        -------
        >>> metrics.observe_request(
        ...     operation="create_order",
        ...     duration_seconds=0.045,
        ...     status="success",
        ... )
        """

    @abstractmethod
    @contextmanager
    def track_request(self, operation: str) -> Generator[None, None, None]:
        """
        Context manager for automatic request tracking.

        Automatically measures duration and detects errors.

        Parameters
        ----------
        operation : str
            Name of the operation.

        Yields
        ------
        None

        Example
        -------
        >>> with metrics.track_request("process_payment"):
        ...     process_payment(amount)
        """

    def inc_request(
        self, operation: str, status: Literal["success", "failure"] = "success"
    ) -> None:
        """
        Increment request counter without duration tracking.

        Useful for counting events that don't have meaningful duration.

        Parameters
        ----------
        operation : str
            Name of the operation.
        status : {"success", "failure"}
            Status of the operation.
        """
        self.observe_request(operation, 0.0, status)


class GoldenSignalsInterface(MetricsInterface):
    """
    Extended interface for Four Golden Signals metrics.

    Adds saturation tracking to the base MetricsInterface.
    """

    @abstractmethod
    def set_saturation(self, resource: str, value: float) -> None:
        """
        Set saturation level for a resource.

        Parameters
        ----------
        resource : str
            Resource name (e.g., "cpu", "memory", "connections").
        value : float
            Saturation level from 0.0 to 1.0.
        """

    @abstractmethod
    def set_queue_depth(self, queue_name: str, depth: int) -> None:
        """
        Set queue depth for saturation tracking.

        Parameters
        ----------
        queue_name : str
            Name of the queue.
        depth : int
            Current queue depth.
        """


class USEMetricsInterface(ABC):
    """
    Abstract base class for USE Method metrics.

    USE = Utilization, Saturation, Errors (for infrastructure monitoring).
    """

    @abstractmethod
    def set_utilization(self, resource: str, value: float) -> None:
        """
        Set utilization percentage for a resource.

        Parameters
        ----------
        resource : str
            Resource name.
        value : float
            Utilization from 0.0 to 1.0.
        """

    @abstractmethod
    def set_saturation(self, resource: str, value: float) -> None:
        """
        Set saturation (queue length or wait time).

        Parameters
        ----------
        resource : str
            Resource name.
        value : float
            Saturation value.
        """

    @abstractmethod
    def inc_error(self, resource: str, error_type: str) -> None:
        """
        Increment error count for a resource.

        Parameters
        ----------
        resource : str
            Resource name.
        error_type : str
            Type of error.
        """
