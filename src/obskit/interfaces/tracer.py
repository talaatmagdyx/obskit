"""
Tracer Interface - Abstract Base Class for Distributed Tracing
===============================================================

This module defines the contract for distributed tracing implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator


class SpanInterface(ABC):
    """Interface for trace spans."""

    @property
    @abstractmethod
    def trace_id(self) -> str:
        """Get the trace ID."""

    @property
    @abstractmethod
    def span_id(self) -> str:
        """Get the span ID."""

    @abstractmethod
    def set_attribute(self, key: str, value: Any) -> None:
        """
        Set an attribute on the span.

        Parameters
        ----------
        key : str
            Attribute name.
        value : Any
            Attribute value.
        """

    @abstractmethod
    def set_status(self, status: str, description: str | None = None) -> None:
        """
        Set the span status.

        Parameters
        ----------
        status : str
            Status code ("ok", "error").
        description : str, optional
            Status description.
        """

    @abstractmethod
    def record_exception(self, exception: BaseException) -> None:
        """
        Record an exception on the span.

        Parameters
        ----------
        exception : BaseException
            The exception to record.
        """

    @abstractmethod
    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """
        Add an event to the span.

        Parameters
        ----------
        name : str
            Event name.
        attributes : dict, optional
            Event attributes.
        """


class TracerInterface(ABC):
    """
    Abstract base class for distributed tracing.

    Provides methods for creating spans and propagating trace context.

    Example
    -------
    >>> class MyTracer(TracerInterface):
    ...     @contextmanager
    ...     def start_span(self, name, **kwargs):
    ...         span = self._create_span(name)
    ...         try:
    ...             yield span
    ...         except Exception as e:
    ...             span.record_exception(e)
    ...             raise
    ...         finally:
    ...             span.end()
    """

    @abstractmethod
    @contextmanager
    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        kind: str = "internal",
    ) -> Generator[SpanInterface, None, None]:
        """
        Start a new span.

        Parameters
        ----------
        name : str
            Span name.
        attributes : dict, optional
            Initial span attributes.
        kind : str
            Span kind ("internal", "server", "client", "producer", "consumer").

        Yields
        ------
        SpanInterface
            The created span.

        Example
        -------
        >>> with tracer.start_span("process_order", attributes={"order_id": "123"}):
        ...     process_order()
        """

    @abstractmethod
    def inject_context(self, headers: dict[str, str]) -> dict[str, str]:
        """
        Inject trace context into headers for propagation.

        Parameters
        ----------
        headers : dict
            Headers dictionary to inject context into.

        Returns
        -------
        dict
            Headers with trace context added.

        Example
        -------
        >>> headers = tracer.inject_context({})
        >>> response = await client.post(url, headers=headers)
        """

    @abstractmethod
    def extract_context(self, headers: dict[str, str]) -> Any:
        """
        Extract trace context from headers.

        Parameters
        ----------
        headers : dict
            Headers dictionary containing trace context.

        Returns
        -------
        Any
            Extracted context object.

        Example
        -------
        >>> context = tracer.extract_context(request.headers)
        >>> with tracer.start_span("handle_request", context=context):
        ...     handle_request()
        """

    @abstractmethod
    def get_current_span(self) -> SpanInterface | None:
        """
        Get the current active span.

        Returns
        -------
        SpanInterface | None
            The current span or None if no span is active.
        """

    @abstractmethod
    def get_trace_id(self) -> str | None:
        """
        Get the current trace ID.

        Returns
        -------
        str | None
            The current trace ID or None if no trace is active.
        """
