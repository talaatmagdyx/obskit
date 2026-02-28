"""
Correlation ID Manager.

Provides better correlation across async boundaries and distributed systems.
"""

import contextvars
import functools
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, TypeVar

# Context variables for correlation tracking
_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "session_id", default=None
)
_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tenant_id", default=None
)
_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("user_id", default=None)
_custom_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "custom_context", default=None
)

F = TypeVar("F", bound=Callable[..., Any])


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def get_correlation_id() -> str | None:
    """Get the current correlation ID."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> contextvars.Token:
    """Set the correlation ID."""
    return _correlation_id.set(correlation_id)


def get_request_id() -> str | None:
    """Get the current request ID."""
    return _request_id.get()


def set_request_id(request_id: str) -> contextvars.Token:
    """Set the request ID."""
    return _request_id.set(request_id)


def get_session_id() -> str | None:
    """Get the current session ID."""
    return _session_id.get()


def set_session_id(session_id: str) -> contextvars.Token:
    """Set the session ID."""
    return _session_id.set(session_id)


def get_tenant_id() -> str | None:
    """Get the current tenant ID."""
    return _tenant_id.get()


def set_tenant_id(tenant_id: str) -> contextvars.Token:
    """Set the tenant ID."""
    return _tenant_id.set(tenant_id)


def get_user_id() -> str | None:
    """Get the current user ID."""
    return _user_id.get()


def set_user_id(user_id: str) -> contextvars.Token:
    """Set the user ID."""
    return _user_id.set(user_id)


def get_custom_context() -> dict[str, Any]:
    """Get custom context values."""
    ctx = _custom_context.get()
    return ctx.copy() if ctx else {}


def set_custom_value(key: str, value: Any):
    """Set a custom context value."""
    ctx = _custom_context.get()
    new_ctx = ctx.copy() if ctx else {}
    new_ctx[key] = value
    _custom_context.set(new_ctx)


def get_full_context() -> dict[str, Any]:
    """Get all context values."""
    context = {
        "correlation_id": get_correlation_id(),
        "request_id": get_request_id(),
        "session_id": get_session_id(),
        "tenant_id": get_tenant_id(),
        "user_id": get_user_id(),
    }
    context.update(get_custom_context())
    return {k: v for k, v in context.items() if v is not None}


class CorrelationManager:
    """
    Manages correlation context across async boundaries.

    Example:
        # Create new context
        with CorrelationManager.new_context(correlation_id="req-123"):
            # All logs/traces automatically include correlation_id
            await process_async_task()

        # Propagate existing context
        ctx = CorrelationManager.capture()
        # ... in another thread/task
        with CorrelationManager.restore(ctx):
            process()
    """

    @staticmethod
    @contextmanager
    def new_context(
        correlation_id: str | None = None,
        request_id: str | None = None,
        session_id: str | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        **custom,
    ):
        """
        Create a new correlation context.

        Args:
            correlation_id: Correlation ID (auto-generated if not provided)
            request_id: Request ID
            session_id: Session ID
            tenant_id: Tenant ID
            user_id: User ID
            **custom: Custom context values
        """
        tokens = []

        if correlation_id or not get_correlation_id():
            tokens.append(set_correlation_id(correlation_id or generate_correlation_id()))
        if request_id:
            tokens.append(set_request_id(request_id))
        if session_id:
            tokens.append(set_session_id(session_id))
        if tenant_id:
            tokens.append(set_tenant_id(tenant_id))
        if user_id:
            tokens.append(set_user_id(user_id))

        for key, value in custom.items():
            set_custom_value(key, value)

        try:
            yield
        finally:
            # Tokens are automatically reset when context exits
            pass

    @staticmethod
    def capture() -> dict[str, Any]:
        """
        Capture the current correlation context.

        Returns:
            Dictionary with all context values
        """
        return get_full_context()

    @staticmethod
    @contextmanager
    def restore(context: dict[str, Any]):
        """
        Restore a captured correlation context.

        Args:
            context: Previously captured context
        """
        with CorrelationManager.new_context(**context):
            yield

    @staticmethod
    def propagate_to_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
        """
        Propagate correlation context to HTTP headers.

        Args:
            headers: Existing headers (will be modified)

        Returns:
            Headers with correlation context
        """
        if headers is None:
            headers = {}

        context = get_full_context()
        header_mapping = {
            "correlation_id": "X-Correlation-ID",
            "request_id": "X-Request-ID",
            "session_id": "X-Session-ID",
            "tenant_id": "X-Tenant-ID",
            "user_id": "X-User-ID",
        }

        for key, header_name in header_mapping.items():
            if key in context and context[key]:
                headers[header_name] = str(context[key])

        return headers

    @staticmethod
    def extract_from_headers(headers: dict[str, str]) -> dict[str, Any]:
        """
        Extract correlation context from HTTP headers.

        Args:
            headers: HTTP headers

        Returns:
            Extracted context values
        """
        header_mapping = {
            "X-Correlation-ID": "correlation_id",
            "X-Request-ID": "request_id",
            "X-Session-ID": "session_id",
            "X-Tenant-ID": "tenant_id",
            "X-User-ID": "user_id",
        }

        context = {}
        for header_name, key in header_mapping.items():
            # Check various header name formats
            value = (
                headers.get(header_name)
                or headers.get(header_name.lower())
                or headers.get(header_name.lower().replace("-", "_"))
            )
            if value:
                context[key] = value

        return context

    @staticmethod
    def propagate_to_message(
        message: dict[str, Any], headers_key: str = "headers"
    ) -> dict[str, Any]:
        """
        Propagate correlation context to a message.

        Args:
            message: Message dict
            headers_key: Key for headers in message

        Returns:
            Message with correlation context
        """
        if headers_key not in message:
            message[headers_key] = {}

        message[headers_key] = CorrelationManager.propagate_to_headers(message[headers_key])
        return message

    @staticmethod
    def extract_from_message(
        message: dict[str, Any], headers_key: str = "headers"
    ) -> dict[str, Any]:
        """
        Extract correlation context from a message.

        Args:
            message: Message dict
            headers_key: Key for headers in message

        Returns:
            Extracted context values
        """
        headers = message.get(headers_key, {})
        return CorrelationManager.extract_from_headers(headers)


def with_correlation(generate_if_missing: bool = True, propagate: bool = True) -> Callable[[F], F]:
    """
    Decorator to ensure correlation context is available.

    Args:
        generate_if_missing: Generate correlation ID if not present
        propagate: Propagate context to child calls

    Example:
        @with_correlation()
        async def handle_request(request):
            # correlation_id is available
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            correlation_id = get_correlation_id()
            if not correlation_id and generate_if_missing:
                correlation_id = generate_correlation_id()

            with CorrelationManager.new_context(correlation_id=correlation_id):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            correlation_id = get_correlation_id()
            if not correlation_id and generate_if_missing:
                correlation_id = generate_correlation_id()

            with CorrelationManager.new_context(correlation_id=correlation_id):
                return await func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


class CorrelatedTask:
    """
    Wrapper for async tasks that preserves correlation context.

    Example:
        async def my_task():
            # Has access to correlation context
            pass

        # Create task with context preserved
        task = CorrelatedTask(my_task())
        await task
    """

    def __init__(self, coro):
        self.coro = coro
        self.context = CorrelationManager.capture()

    def __await__(self):
        async def run_with_context():
            with CorrelationManager.restore(self.context):
                return await self.coro

        return run_with_context().__await__()


def create_correlated_task(coro):
    """
    Create an asyncio task that preserves correlation context.

    Example:
        task = create_correlated_task(my_async_function())
    """
    import asyncio

    context = CorrelationManager.capture()

    async def wrapper():
        with CorrelationManager.restore(context):
            return await coro

    return asyncio.create_task(wrapper())


__all__ = [
    "CorrelationManager",
    "CorrelatedTask",
    "generate_correlation_id",
    "get_correlation_id",
    "set_correlation_id",
    "get_request_id",
    "set_request_id",
    "get_session_id",
    "set_session_id",
    "get_tenant_id",
    "set_tenant_id",
    "get_user_id",
    "set_user_id",
    "get_custom_context",
    "set_custom_value",
    "get_full_context",
    "with_correlation",
    "create_correlated_task",
]
