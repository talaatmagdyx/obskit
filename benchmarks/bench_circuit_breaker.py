"""
Benchmarks for circuit breaker operations.

These benchmarks measure the overhead of circuit breaker checks,
which is critical for understanding the cost of resilience patterns.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from typing import Any

import pytest

from obskit.resilience.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreakerBenchmarks:
    """Benchmarks for CircuitBreaker operations."""

    breaker: CircuitBreaker

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        """Set up circuit breaker for benchmarking."""
        self.breaker = CircuitBreaker(
            name="bench_breaker",
            failure_threshold=5,
            recovery_timeout=30.0,
        )
        yield

    @pytest.mark.benchmark(group="circuit_breaker")
    def test_state_check(self, benchmark: Any) -> None:
        """Benchmark checking circuit state."""
        benchmark(lambda: self.breaker.state)

    @pytest.mark.benchmark(group="circuit_breaker")
    def test_is_closed_check(self, benchmark: Any) -> None:
        """Benchmark checking if circuit is closed."""
        benchmark(lambda: self.breaker.state == CircuitState.CLOSED)

    @pytest.mark.benchmark(group="circuit_breaker")
    def test_failure_count_check(self, benchmark: Any) -> None:
        """Benchmark checking failure count."""
        benchmark(lambda: self.breaker.failure_count)

    @pytest.mark.benchmark(group="circuit_breaker")
    def test_decorated_function(self, benchmark: Any) -> None:
        """Benchmark decorated function call (closed circuit)."""

        @self.breaker
        def work() -> int:
            return 42

        benchmark(work)

    @pytest.mark.benchmark(group="circuit_breaker")
    def test_decorated_async_function(self, benchmark: Any) -> None:
        """Benchmark decorated async function call."""

        @self.breaker
        async def work() -> int:
            return 42

        def run() -> None:
            asyncio.run(work())

        benchmark(run)


class TestCircuitBreakerRecordBenchmarks:
    """Benchmarks for circuit breaker recording operations."""

    breaker: CircuitBreaker
    test_error: Exception

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        """Set up circuit breaker for benchmarking."""
        self.breaker = CircuitBreaker(
            name="bench_breaker_record",
            failure_threshold=1000,  # High threshold to avoid state changes
            recovery_timeout=30.0,
        )
        self.test_error = Exception("benchmark error")
        yield

    @pytest.mark.benchmark(group="circuit_breaker_record")
    def test_record_success(self, benchmark: Any) -> None:
        """Benchmark recording success."""
        benchmark(self.breaker._record_success)

    @pytest.mark.benchmark(group="circuit_breaker_record")
    def test_record_failure(self, benchmark: Any) -> None:
        """Benchmark recording failure."""

        # Reset after each failure to prevent state change
        def record_and_reset() -> None:
            self.breaker._record_failure(self.test_error)
            self.breaker._failure_count = 0

        benchmark(record_and_reset)


class TestCircuitBreakerDecoratorBenchmarks:
    """Benchmarks for circuit breaker as decorator."""

    breaker: CircuitBreaker

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        """Set up circuit breaker for benchmarking."""
        self.breaker = CircuitBreaker(
            name="bench_breaker_decorator",
            failure_threshold=5,
        )
        yield

    @pytest.mark.benchmark(group="circuit_breaker_decorator")
    def test_decorated_sync_function(self, benchmark: Any) -> None:
        """Benchmark decorated sync function."""

        @self.breaker
        def work() -> int:
            return 42

        benchmark(work)

    @pytest.mark.benchmark(group="circuit_breaker_decorator")
    def test_decorated_async_function(self, benchmark: Any) -> None:
        """Benchmark decorated async function."""

        @self.breaker
        async def work() -> int:
            return 42

        def run() -> None:
            asyncio.run(work())

        benchmark(run)

