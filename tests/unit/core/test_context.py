"""Tests for obskit.core.context module."""

import asyncio
import pytest

from obskit.core.context import (
    get_correlation_id,
    set_correlation_id,
    correlation_context,
    async_correlation_context,
    generate_correlation_id,
    ensure_correlation_id,
)


class TestGetCorrelationId:
    """Tests for get_correlation_id function."""

    def test_returns_none_when_not_set(self):
        """Test that get_correlation_id returns None when not in context."""
        assert get_correlation_id() is None

    def test_returns_id_when_set(self):
        """Test that get_correlation_id returns the set ID."""
        with correlation_context("test-id"):
            assert get_correlation_id() == "test-id"


class TestSetCorrelationId:
    """Tests for set_correlation_id function."""

    def test_set_correlation_id(self):
        """Test setting correlation ID."""
        token = set_correlation_id("my-id")
        try:
            assert get_correlation_id() == "my-id"
        finally:
            # Reset using the context var directly
            from obskit.core.context import _correlation_id
            _correlation_id.reset(token)

    def test_set_correlation_id_to_none(self):
        """Test setting correlation ID to None."""
        with correlation_context("existing"):
            token = set_correlation_id(None)
            try:
                assert get_correlation_id() is None
            finally:
                from obskit.core.context import _correlation_id
                _correlation_id.reset(token)


class TestCorrelationContext:
    """Tests for correlation_context context manager."""

    def test_auto_generated_id(self):
        """Test that context auto-generates ID if not provided."""
        with correlation_context() as cid:
            assert cid is not None
            assert len(cid) > 0
            assert get_correlation_id() == cid

    def test_provided_id(self):
        """Test context with provided ID."""
        with correlation_context("custom-id") as cid:
            assert cid == "custom-id"
            assert get_correlation_id() == "custom-id"

    def test_context_cleanup(self):
        """Test that context cleans up after exit."""
        with correlation_context("temp-id"):
            pass
        assert get_correlation_id() is None

    def test_nested_contexts(self):
        """Test nested correlation contexts."""
        with correlation_context("outer"):
            assert get_correlation_id() == "outer"
            
            with correlation_context("inner"):
                assert get_correlation_id() == "inner"
            
            # Back to outer
            assert get_correlation_id() == "outer"

    def test_context_on_exception(self):
        """Test that context cleans up on exception."""
        try:
            with correlation_context("error-id"):
                raise ValueError("Test error")
        except ValueError:
            pass
        
        assert get_correlation_id() is None

    def test_context_yields_id(self):
        """Test that context yields the correlation ID."""
        with correlation_context("yielded-id") as yielded:
            assert yielded == "yielded-id"


class TestAsyncCorrelationContext:
    """Tests for async_correlation_context context manager."""

    @pytest.mark.asyncio
    async def test_auto_generated_id(self):
        """Test async context auto-generates ID."""
        async with async_correlation_context() as cid:
            assert cid is not None
            assert get_correlation_id() == cid

    @pytest.mark.asyncio
    async def test_provided_id(self):
        """Test async context with provided ID."""
        async with async_correlation_context("async-id") as cid:
            assert cid == "async-id"
            assert get_correlation_id() == "async-id"

    @pytest.mark.asyncio
    async def test_context_cleanup(self):
        """Test async context cleans up."""
        async with async_correlation_context("async-temp"):
            pass
        assert get_correlation_id() is None

    @pytest.mark.asyncio
    async def test_context_across_await(self):
        """Test context preserved across await points."""
        async with async_correlation_context("await-id"):
            await asyncio.sleep(0)
            assert get_correlation_id() == "await-id"

    @pytest.mark.asyncio
    async def test_nested_async_contexts(self):
        """Test nested async contexts."""
        async with async_correlation_context("async-outer"):
            assert get_correlation_id() == "async-outer"
            
            async with async_correlation_context("async-inner"):
                assert get_correlation_id() == "async-inner"
            
            assert get_correlation_id() == "async-outer"


class TestGenerateCorrelationId:
    """Tests for generate_correlation_id function."""

    def test_generates_unique_ids(self):
        """Test that generate_correlation_id creates unique IDs."""
        ids = [generate_correlation_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generates_valid_uuid(self):
        """Test that generated ID is a valid UUID format."""
        cid = generate_correlation_id()
        # UUID format: 8-4-4-4-12 hex digits
        parts = cid.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12


class TestEnsureCorrelationId:
    """Tests for ensure_correlation_id function."""

    def test_returns_current_id_when_set(self):
        """Test that ensure returns current ID when in context."""
        with correlation_context("existing-id"):
            cid = ensure_correlation_id()
            assert cid == "existing-id"

    def test_generates_new_id_when_not_set(self):
        """Test that ensure generates new ID when not in context."""
        cid = ensure_correlation_id()
        assert cid is not None
        assert len(cid) > 0

    def test_generates_different_ids_when_not_set(self):
        """Test that ensure generates different IDs each call when not set."""
        cid1 = ensure_correlation_id()
        cid2 = ensure_correlation_id()
        assert cid1 != cid2

    def test_returns_same_id_in_context(self):
        """Test that ensure returns same ID within context."""
        with correlation_context("stable-id"):
            cid1 = ensure_correlation_id()
            cid2 = ensure_correlation_id()
            assert cid1 == cid2 == "stable-id"

