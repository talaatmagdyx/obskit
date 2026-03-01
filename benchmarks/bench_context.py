"""
Benchmarks for context propagation operations.

These benchmarks measure the overhead of correlation ID and
context management, which is used on every request.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from typing import Any

import pytest

from obskit.core.context import (
    async_correlation_context,
    correlation_context,
    get_correlation_id,
    set_correlation_id,
)


def reset_correlation_id() -> None:
    """Reset the correlation ID by setting it to None."""
    set_correlation_id(None)


class TestCorrelationIdBenchmarks:
    """Benchmarks for correlation ID operations."""

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        """Reset correlation ID before each test."""
        reset_correlation_id()
        yield
        reset_correlation_id()

    @pytest.mark.benchmark(group="correlation")
    def test_set_correlation_id(self, benchmark: Any) -> None:
        """Benchmark setting correlation ID."""
        benchmark(set_correlation_id, "bench-correlation-id")

    @pytest.mark.benchmark(group="correlation")
    def test_get_correlation_id(self, benchmark: Any) -> None:
        """Benchmark getting correlation ID."""
        set_correlation_id("bench-correlation-id")
        benchmark(get_correlation_id)

    @pytest.mark.benchmark(group="correlation")
    def test_get_correlation_id_none(self, benchmark: Any) -> None:
        """Benchmark getting correlation ID when not set."""
        benchmark(get_correlation_id)

    @pytest.mark.benchmark(group="correlation")
    def test_reset_correlation_id(self, benchmark: Any) -> None:
        """Benchmark resetting correlation ID."""
        set_correlation_id("bench-correlation-id")
        benchmark(reset_correlation_id)

    @pytest.mark.benchmark(group="correlation")
    def test_set_get_cycle(self, benchmark: Any) -> None:
        """Benchmark set/get cycle."""

        def cycle() -> str | None:
            set_correlation_id("bench-id")
            return get_correlation_id()

        benchmark(cycle)


class TestCorrelationContextBenchmarks:
    """Benchmarks for correlation context managers."""

    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, None, None]:
        """Reset correlation ID before each test."""
        reset_correlation_id()
        yield
        reset_correlation_id()

    @pytest.mark.benchmark(group="correlation_context")
    def test_sync_context_manager(self, benchmark: Any) -> None:
        """Benchmark sync context manager."""

        def use_context() -> None:
            with correlation_context("bench-id"):
                _ = 0  # Measure context manager overhead

        benchmark(use_context)

    @pytest.mark.benchmark(group="correlation_context")
    def test_sync_context_with_work(self, benchmark: Any) -> None:
        """Benchmark sync context with work inside."""

        def use_context() -> None:
            with correlation_context("bench-id"):
                _ = sum(range(100))

        benchmark(use_context)

    @pytest.mark.benchmark(group="correlation_context")
    def test_async_context_manager(self, benchmark: Any) -> None:
        """Benchmark async context manager."""

        async def use_context() -> None:
            async with async_correlation_context("bench-id"):
                _ = 0  # Measure context manager overhead

        def run() -> None:
            asyncio.run(use_context())

        benchmark(run)

    @pytest.mark.benchmark(group="correlation_context")
    def test_nested_contexts(self, benchmark: Any) -> None:
        """Benchmark nested context managers."""

        def nested() -> None:
            with correlation_context("outer"):
                with correlation_context("inner"):
                    _ = 0  # Measure context manager overhead

        benchmark(nested)


class TestContextVarsOverhead:
    """Benchmarks to measure raw contextvars overhead."""

    @pytest.mark.benchmark(group="contextvars_raw")
    def test_contextvar_get(self, benchmark: Any) -> None:
        """Benchmark raw contextvar get."""
        from contextvars import ContextVar

        var: ContextVar[str] = ContextVar("bench_var", default="default")

        benchmark(var.get)

    @pytest.mark.benchmark(group="contextvars_raw")
    def test_contextvar_set(self, benchmark: Any) -> None:
        """Benchmark raw contextvar set."""
        from contextvars import ContextVar

        var: ContextVar[str] = ContextVar("bench_var")

        benchmark(var.set, "value")

    @pytest.mark.benchmark(group="contextvars_raw")
    def test_contextvar_set_reset(self, benchmark: Any) -> None:
        """Benchmark contextvar set and reset cycle."""
        from contextvars import ContextVar

        var: ContextVar[str] = ContextVar("bench_var")

        def set_reset() -> None:
            token = var.set("value")
            var.reset(token)

        benchmark(set_reset)

