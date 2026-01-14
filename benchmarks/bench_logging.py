"""
Benchmarks for logging operations.

These benchmarks measure the overhead of structured logging,
which is important for understanding the cost of verbose logging.
"""

from __future__ import annotations

import io
import sys
from typing import Any

import pytest

from obskit.core.context import set_correlation_id
from obskit.logging import get_logger


class TestLoggingBenchmarks:
    """Benchmarks for logging operations."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Set up logger for benchmarking."""
        # Redirect output to avoid I/O overhead in benchmarks
        self.original_stderr = sys.stderr
        sys.stderr = io.StringIO()
        self.logger = get_logger("benchmark")
        yield
        sys.stderr = self.original_stderr

    @pytest.mark.benchmark(group="logging")
    def test_log_info_simple(self, benchmark: Any) -> None:
        """Benchmark simple info log."""
        benchmark(self.logger.info, "benchmark_event")

    @pytest.mark.benchmark(group="logging")
    def test_log_info_with_context(self, benchmark: Any) -> None:
        """Benchmark info log with structured context."""
        benchmark(
            self.logger.info,
            "benchmark_event",
            user_id="user123",
            order_id="order456",
            amount=99.99,
        )

    @pytest.mark.benchmark(group="logging")
    def test_log_info_many_fields(self, benchmark: Any) -> None:
        """Benchmark info log with many fields."""

        def log_many() -> None:
            self.logger.info(
                "benchmark_event",
                field1="value1",
                field2="value2",
                field3="value3",
                field4="value4",
                field5="value5",
                field6="value6",
                field7="value7",
                field8="value8",
                field9="value9",
                field10="value10",
            )

        benchmark(log_many)

    @pytest.mark.benchmark(group="logging")
    def test_log_with_correlation_id(self, benchmark: Any) -> None:
        """Benchmark logging with correlation ID in context."""
        set_correlation_id("bench-correlation-id")

        benchmark(
            self.logger.info,
            "benchmark_event",
            user_id="user123",
        )

    @pytest.mark.benchmark(group="logging")
    def test_bound_logger(self, benchmark: Any) -> None:
        """Benchmark using a pre-bound logger."""
        bound = self.logger.bind(
            service="benchmark",
            version="1.0.0",
        )

        benchmark(bound.info, "benchmark_event")


class TestLoggerCreationBenchmarks:
    """Benchmarks for logger creation."""

    @pytest.mark.benchmark(group="logging_creation")
    def test_get_logger(self, benchmark: Any) -> None:
        """Benchmark getting a logger."""
        counter = [0]

        def get() -> None:
            counter[0] += 1
            get_logger(f"benchmark_{counter[0]}")

        benchmark(get)

    @pytest.mark.benchmark(group="logging_creation")
    def test_get_same_logger(self, benchmark: Any) -> None:
        """Benchmark getting the same logger (cached)."""
        benchmark(get_logger, "benchmark_cached")

