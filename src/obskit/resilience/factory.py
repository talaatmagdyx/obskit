"""
Circuit Breaker and Rate Limiter Factory
=========================================

Pre-configured factories for common resilience patterns with sensible defaults.

Example
-------
>>> from obskit.resilience.factory import (
...     get_circuit_breaker,
...     get_rate_limiter,
...     CircuitBreakerPreset,
...     RateLimiterPreset,
... )
>>>
>>> # Use preset for database
>>> db_breaker = get_circuit_breaker("postgres", preset=CircuitBreakerPreset.DATABASE)
>>>
>>> # Use preset for external API
>>> api_breaker = get_circuit_breaker("payment_api", preset=CircuitBreakerPreset.EXTERNAL_API)
>>>
>>> # Custom configuration
>>> custom_breaker = get_circuit_breaker(
...     "custom_service",
...     failure_threshold=10,
...     recovery_timeout=60.0,
... )
"""

from __future__ import annotations

import threading
from enum import Enum

from obskit.logging import get_logger
from obskit.resilience.circuit_breaker import CircuitBreaker
from obskit.resilience.rate_limiter import RateLimiter, TokenBucketRateLimiter

logger = get_logger("obskit.resilience.factory")

# Global registries
_circuit_breakers: dict[str, CircuitBreaker] = {}
_circuit_breaker_lock = threading.Lock()
_rate_limiters: dict[str, RateLimiter] = {}
_rate_limiter_lock = threading.Lock()


class CircuitBreakerPreset(Enum):
    """Pre-configured circuit breaker settings for common use cases."""

    # Database connections - fail fast, recover quickly
    DATABASE = {
        "failure_threshold": 3,
        "recovery_timeout": 15.0,
        "half_open_requests": 1,
    }

    # Cache (Redis, Memcached) - tolerant, quick recovery
    CACHE = {
        "failure_threshold": 5,
        "recovery_timeout": 10.0,
        "half_open_requests": 2,
    }

    # External APIs - less tolerant, longer recovery
    EXTERNAL_API = {
        "failure_threshold": 3,
        "recovery_timeout": 60.0,
        "half_open_requests": 1,
    }

    # Internal microservices - balanced
    MICROSERVICE = {
        "failure_threshold": 5,
        "recovery_timeout": 30.0,
        "half_open_requests": 2,
    }

    # Search engines (Elasticsearch, Solr)
    SEARCH = {
        "failure_threshold": 5,
        "recovery_timeout": 30.0,
        "half_open_requests": 1,
    }

    # Message queues (RabbitMQ, Kafka)
    MESSAGE_QUEUE = {
        "failure_threshold": 3,
        "recovery_timeout": 20.0,
        "half_open_requests": 1,
    }

    # AI/ML APIs - external, slow, expensive
    AI_API = {
        "failure_threshold": 3,
        "recovery_timeout": 120.0,
        "half_open_requests": 1,
    }

    # Default balanced settings
    DEFAULT = {
        "failure_threshold": 5,
        "recovery_timeout": 30.0,
        "half_open_requests": 1,
    }


class RateLimiterPreset(Enum):
    """Pre-configured rate limiter settings for common use cases."""

    # High throughput internal operations
    HIGH_THROUGHPUT = {
        "requests_per_minute": 10000,
    }

    # Standard API endpoints
    STANDARD_API = {
        "requests_per_minute": 1000,
    }

    # Database queries
    DATABASE = {
        "requests_per_minute": 500,
    }

    # External API calls (rate limited by provider)
    EXTERNAL_API = {
        "requests_per_minute": 100,
    }

    # AI/ML API calls (expensive, rate limited)
    AI_API = {
        "requests_per_minute": 60,
    }

    # Webhook/notification sending
    NOTIFICATION = {
        "requests_per_minute": 200,
    }

    # Default moderate rate
    DEFAULT = {
        "requests_per_minute": 500,
    }


def get_circuit_breaker(
    name: str,
    preset: CircuitBreakerPreset | None = None,
    failure_threshold: int | None = None,
    recovery_timeout: float | None = None,
    half_open_requests: int | None = None,
) -> CircuitBreaker:
    """
    Get or create a circuit breaker with optional preset configuration.

    Parameters
    ----------
    name : str
        Unique name for the circuit breaker.
    preset : CircuitBreakerPreset, optional
        Pre-configured settings to use.
    failure_threshold : int, optional
        Override failures before opening circuit.
    recovery_timeout : float, optional
        Override seconds before trying recovery.
    half_open_requests : int, optional
        Override requests allowed in half-open state.

    Returns
    -------
    CircuitBreaker
        Circuit breaker instance (cached by name).

    Example
    -------
    >>> # Use preset
    >>> db_breaker = get_circuit_breaker("postgres", preset=CircuitBreakerPreset.DATABASE)
    >>>
    >>> # Custom settings
    >>> custom = get_circuit_breaker("custom", failure_threshold=10, recovery_timeout=60)
    >>>
    >>> # Use with context manager
    >>> with db_breaker:
    ...     result = db.execute(query)
    """
    if name not in _circuit_breakers:
        with _circuit_breaker_lock:
            if name not in _circuit_breakers:
                # Get base config from preset or default
                if preset:
                    config = preset.value.copy()
                else:
                    config = CircuitBreakerPreset.DEFAULT.value.copy()

                # Override with explicit parameters
                if failure_threshold is not None:
                    config["failure_threshold"] = failure_threshold
                if recovery_timeout is not None:
                    config["recovery_timeout"] = recovery_timeout
                if half_open_requests is not None:
                    config["half_open_requests"] = half_open_requests

                _circuit_breakers[name] = CircuitBreaker(
                    name=name,
                    **config,
                )

                logger.info(
                    "circuit_breaker_created",
                    name=name,
                    preset=preset.name if preset else "custom",
                    **config,
                )

    return _circuit_breakers[name]


def get_rate_limiter(
    name: str,
    preset: RateLimiterPreset | None = None,
    requests_per_minute: int | None = None,
) -> RateLimiter:
    """
    Get or create a rate limiter with optional preset configuration.

    Parameters
    ----------
    name : str
        Unique name for the rate limiter.
    preset : RateLimiterPreset, optional
        Pre-configured settings to use.
    requests_per_minute : int, optional
        Override maximum requests per minute.

    Returns
    -------
    RateLimiter
        Rate limiter instance (cached by name).

    Example
    -------
    >>> # Use preset
    >>> api_limiter = get_rate_limiter("external_api", preset=RateLimiterPreset.EXTERNAL_API)
    >>>
    >>> # Custom settings
    >>> custom = get_rate_limiter("custom", requests_per_minute=200)
    >>>
    >>> # Use limiter
    >>> if api_limiter.acquire():
    ...     make_api_call()
    """
    if name not in _rate_limiters:
        with _rate_limiter_lock:
            if name not in _rate_limiters:
                # Get base config from preset or default
                if preset:
                    config = preset.value.copy()
                else:
                    config = RateLimiterPreset.DEFAULT.value.copy()

                # Override with explicit parameters
                if requests_per_minute is not None:
                    config["requests_per_minute"] = requests_per_minute

                rpm = config["requests_per_minute"]
                _rate_limiters[name] = TokenBucketRateLimiter(
                    bucket_size=rpm,  # Max burst capacity
                    refill_rate=rpm / 60.0,  # Tokens per second
                )

                logger.info(
                    "rate_limiter_created",
                    name=name,
                    preset=preset.name if preset else "custom",
                    requests_per_minute=rpm,
                )

    return _rate_limiters[name]


def reset_circuit_breaker(name: str) -> bool:
    """
    Reset a circuit breaker to closed state.

    Parameters
    ----------
    name : str
        Name of the circuit breaker.

    Returns
    -------
    bool
        True if reset, False if not found.
    """
    if name in _circuit_breakers:
        try:
            _circuit_breakers[name].reset()
            logger.info("circuit_breaker_reset", name=name)
            return True
        except Exception:
            pass  # Reset failed - return False below
    return False


def get_circuit_breaker_status(name: str) -> dict | None:
    """
    Get status of a circuit breaker.

    Parameters
    ----------
    name : str
        Name of the circuit breaker.

    Returns
    -------
    dict or None
        Status dict with state, failure_count, etc.
    """
    if name in _circuit_breakers:
        cb = _circuit_breakers[name]
        return {
            "name": name,
            "state": cb.state.name if hasattr(cb, "state") else "unknown",
            "failure_count": getattr(cb, "failure_count", 0),
            "success_count": getattr(cb, "success_count", 0),
        }
    return None


def list_circuit_breakers() -> dict[str, dict]:
    """List all registered circuit breakers with their status."""
    return {name: get_circuit_breaker_status(name) for name in _circuit_breakers}


def list_rate_limiters() -> dict[str, str]:
    """List all registered rate limiters."""
    return {name: str(limiter) for name, limiter in _rate_limiters.items()}


__all__ = [
    "CircuitBreakerPreset",
    "RateLimiterPreset",
    "get_circuit_breaker",
    "get_rate_limiter",
    "reset_circuit_breaker",
    "get_circuit_breaker_status",
    "list_circuit_breakers",
    "list_rate_limiters",
]
