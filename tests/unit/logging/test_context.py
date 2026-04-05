"""Unit tests for obskit.logging.context."""

from __future__ import annotations

import pytest
from structlog.contextvars import clear_contextvars


@pytest.fixture(autouse=True)
def _clean_ctx():
    """Ensure structlog context vars are cleared before and after each test."""
    clear_contextvars()
    yield
    clear_contextvars()


class TestBindContext:
    def test_bind_single_key(self):
        from obskit.logging.context import bind_context, get_context

        bind_context(company_id="acme")
        ctx = get_context()
        assert ctx["company_id"] == "acme"

    def test_bind_multiple_keys(self):
        from obskit.logging.context import bind_context, get_context

        bind_context(company_id="acme", region="eu-west-1", user_id=42)
        ctx = get_context()
        assert ctx["company_id"] == "acme"
        assert ctx["region"] == "eu-west-1"
        assert ctx["user_id"] == 42

    def test_bind_overwrites_existing(self):
        from obskit.logging.context import bind_context, get_context

        bind_context(company_id="acme")
        bind_context(company_id="globex")
        ctx = get_context()
        assert ctx["company_id"] == "globex"


class TestUnbindContext:
    def test_unbind_removes_key(self):
        from obskit.logging.context import bind_context, get_context, unbind_context

        bind_context(company_id="acme", region="eu-west-1")
        unbind_context("company_id")
        ctx = get_context()
        assert "company_id" not in ctx
        assert ctx["region"] == "eu-west-1"

    def test_unbind_multiple_keys(self):
        from obskit.logging.context import bind_context, get_context, unbind_context

        bind_context(a=1, b=2, c=3)
        unbind_context("a", "b")
        ctx = get_context()
        assert "a" not in ctx
        assert "b" not in ctx
        assert ctx["c"] == 3

    def test_unbind_nonexistent_key_is_safe(self):
        from obskit.logging.context import unbind_context

        # Should not raise
        unbind_context("nonexistent_key")


class TestClearContext:
    def test_clear_removes_all_keys(self):
        from obskit.logging.context import bind_context, clear_context, get_context

        bind_context(a=1, b=2, c=3)
        clear_context()
        ctx = get_context()
        assert ctx == {}

    def test_clear_on_empty_context_is_safe(self):
        from obskit.logging.context import clear_context, get_context

        clear_context()
        assert get_context() == {}


class TestGetContext:
    def test_get_empty_context(self):
        from obskit.logging.context import get_context

        ctx = get_context()
        assert isinstance(ctx, dict)
        assert ctx == {}

    def test_get_returns_copy(self):
        from obskit.logging.context import bind_context, get_context

        bind_context(key="val")
        ctx = get_context()
        ctx["injected"] = "mutated"  # modifying the copy

        ctx2 = get_context()
        assert "injected" not in ctx2  # original not affected


class TestResetContext:
    def test_reset_context_exists(self):
        """reset_context must be importable — it's an escape hatch."""
        from obskit.logging.context import reset_context

        assert callable(reset_context)

    def test_reset_context_clears_all(self):
        from obskit.logging.context import bind_context, get_context, reset_context

        bind_context(sentinel="yes", other="val")
        assert get_context()["sentinel"] == "yes"

        reset_context()
        assert get_context() == {}


class TestScopedContext:
    def test_sync_binds_keys_inside_block(self):
        from obskit.logging.context import get_context, scoped_context

        with scoped_context(job_id="batch-1"):
            ctx = get_context()
            assert ctx["job_id"] == "batch-1"

    def test_sync_unbinds_keys_on_exit(self):
        from obskit.logging.context import get_context, scoped_context

        with scoped_context(job_id="batch-2"):
            pass
        assert "job_id" not in get_context()

    def test_sync_does_not_remove_unrelated_keys(self):
        from obskit.logging.context import bind_context, get_context, scoped_context

        bind_context(persistent="yes")
        with scoped_context(job_id="batch-3"):
            pass
        ctx = get_context()
        assert ctx["persistent"] == "yes"
        assert "job_id" not in ctx

    def test_sync_unbinds_on_exception(self):
        from obskit.logging.context import get_context, scoped_context

        try:
            with scoped_context(job_id="batch-err"):
                raise ValueError("boom")
        except ValueError:
            pass
        assert "job_id" not in get_context()

    def test_sync_returns_self(self):
        from obskit.logging.context import scoped_context

        cm = scoped_context(x=1)
        with cm as result:
            assert result is cm

    @pytest.mark.asyncio
    async def test_async_binds_keys_inside_block(self):
        from obskit.logging.context import get_context, scoped_context

        async with scoped_context(tenant="acme"):
            ctx = get_context()
            assert ctx["tenant"] == "acme"

    @pytest.mark.asyncio
    async def test_async_unbinds_keys_on_exit(self):
        from obskit.logging.context import get_context, scoped_context

        async with scoped_context(tenant="globex"):
            pass
        assert "tenant" not in get_context()

    @pytest.mark.asyncio
    async def test_async_does_not_remove_unrelated_keys(self):
        from obskit.logging.context import bind_context, get_context, scoped_context

        bind_context(persistent="outer")
        async with scoped_context(tenant="temp"):
            pass
        ctx = get_context()
        assert ctx["persistent"] == "outer"
        assert "tenant" not in ctx

    @pytest.mark.asyncio
    async def test_async_unbinds_on_exception(self):
        from obskit.logging.context import get_context, scoped_context

        try:
            async with scoped_context(tenant="err"):
                raise RuntimeError("async boom")
        except RuntimeError:
            pass
        assert "tenant" not in get_context()

    @pytest.mark.asyncio
    async def test_async_returns_self(self):
        from obskit.logging.context import scoped_context

        cm = scoped_context(y=2)
        async with cm as result:
            assert result is cm

    def test_multiple_keys_all_unbound(self):
        from obskit.logging.context import get_context, scoped_context

        with scoped_context(a=1, b=2, c=3):
            pass
        ctx = get_context()
        for k in ("a", "b", "c"):
            assert k not in ctx


class TestPublicAPI:
    def test_all_exports(self):
        import obskit.logging.context as ctx_mod

        for name in ("bind_context", "unbind_context", "clear_context", "get_context",
                     "reset_context", "scoped_context"):
            assert hasattr(ctx_mod, name), f"missing: {name}"


class TestScopedContextPropagate:
    """Tests for scoped_context(propagate=[...]) — W3C baggage integration."""

    def test_propagate_none_no_otel_calls(self):
        """With propagate=None (default), no OTel baggage is attached."""
        from unittest.mock import patch
        from obskit.logging.context import scoped_context
        import obskit.logging.context as ctx_mod

        with patch.object(ctx_mod, "_try_attach_baggage") as mock_attach, \
             patch.object(ctx_mod, "_try_detach_baggage") as mock_detach:
            with scoped_context(company_id="42"):
                pass
        mock_attach.assert_not_called()
        mock_detach.assert_not_called()

    def test_propagate_calls_attach_and_detach(self):
        """propagate=[key] attaches baggage on enter and detaches on exit."""
        from unittest.mock import MagicMock, patch
        from obskit.logging.context import scoped_context
        import obskit.logging.context as ctx_mod

        mock_token = MagicMock()
        with patch.object(ctx_mod, "_try_attach_baggage", return_value=mock_token) as mock_attach, \
             patch.object(ctx_mod, "_try_detach_baggage") as mock_detach:
            with scoped_context(company_id="42", propagate=["company_id"]):
                mock_attach.assert_called_once_with(["company_id"], {"company_id": "42"})
        mock_detach.assert_called_once_with(mock_token)

    @pytest.mark.asyncio
    async def test_propagate_async_attaches_and_detaches(self):
        """async with scoped_context(propagate=[...]) follows the same pattern."""
        from unittest.mock import MagicMock, patch
        from obskit.logging.context import scoped_context
        import obskit.logging.context as ctx_mod

        mock_token = MagicMock()
        with patch.object(ctx_mod, "_try_attach_baggage", return_value=mock_token) as mock_attach, \
             patch.object(ctx_mod, "_try_detach_baggage") as mock_detach:
            async with scoped_context(company_id="7", propagate=["company_id"]):
                mock_attach.assert_called_once_with(["company_id"], {"company_id": "7"})
        mock_detach.assert_called_once_with(mock_token)

    def test_propagate_detaches_on_exception(self):
        """Baggage is always detached even if an exception is raised inside the block."""
        from unittest.mock import MagicMock, patch
        from obskit.logging.context import scoped_context
        import obskit.logging.context as ctx_mod

        mock_token = MagicMock()
        with patch.object(ctx_mod, "_try_attach_baggage", return_value=mock_token), \
             patch.object(ctx_mod, "_try_detach_baggage") as mock_detach:
            with pytest.raises(ValueError):
                with scoped_context(company_id="42", propagate=["company_id"]):
                    raise ValueError("boom")
        mock_detach.assert_called_once_with(mock_token)

    def test_propagate_ignores_keys_not_in_kw(self):
        """Keys listed in propagate but absent from kwargs are silently ignored."""
        from unittest.mock import patch
        import obskit.logging.context as ctx_mod
        from obskit.logging.context import _try_attach_baggage

        # _try_attach_baggage must handle missing keys without error
        with patch("obskit.logging.context.bind_contextvars"), \
             patch("obskit.logging.context.unbind_contextvars"):
            result = _try_attach_baggage(["missing_key"], {"company_id": "42"})
        # No baggage set because the key isn't in kw — returns None
        assert result is None

    def test_try_attach_baggage_with_otel(self):
        """_try_attach_baggage sets baggage and returns a token."""
        from unittest.mock import MagicMock, patch
        import obskit.logging.context as ctx_mod

        fake_ctx = MagicMock()
        fake_token = MagicMock()

        with patch("opentelemetry.baggage.set_baggage", return_value=fake_ctx), \
             patch("opentelemetry.context.attach", return_value=fake_token) as mock_att:
            token = ctx_mod._try_attach_baggage(["company_id"], {"company_id": "42"})
        assert token is fake_token

    def test_try_detach_baggage_none_is_noop(self):
        """_try_detach_baggage(None) returns without calling detach."""
        from unittest.mock import patch
        import obskit.logging.context as ctx_mod

        with patch("opentelemetry.context.detach") as mock_det:
            ctx_mod._try_detach_baggage(None)
        mock_det.assert_not_called()

    def test_try_detach_baggage_with_token(self):
        """_try_detach_baggage(token) calls OTel detach with the token."""
        from unittest.mock import MagicMock, patch
        import obskit.logging.context as ctx_mod

        fake_token = MagicMock()
        with patch("opentelemetry.context.detach") as mock_det:
            ctx_mod._try_detach_baggage(fake_token)
        mock_det.assert_called_once_with(fake_token)
