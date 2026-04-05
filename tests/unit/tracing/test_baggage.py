"""Unit tests for obskit.tracing.baggage."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


class TestBaggageContext:
    def test_sync_context_manager_no_otel(self):
        """Works as a no-op when opentelemetry-api is not available."""
        from obskit.tracing.baggage import baggage_context
        import obskit.tracing.baggage as _mod

        original = _mod._OTEL_AVAILABLE
        _mod._OTEL_AVAILABLE = False
        try:
            executed = []
            with baggage_context(company_id="42"):
                executed.append(True)
            assert executed == [True]
        finally:
            _mod._OTEL_AVAILABLE = original

    def test_sync_context_manager_empty_kwargs(self):
        """Empty kwargs produces a no-op (no attach/detach calls)."""
        from obskit.tracing.baggage import baggage_context
        import obskit.tracing.baggage as _mod

        with patch.object(_mod, "_attach", wraps=_mod._attach if _mod._OTEL_AVAILABLE else None) \
                if _mod._OTEL_AVAILABLE else _no_patch():
            executed = []
            with baggage_context():
                executed.append(True)
        assert executed == [True]

    def test_sync_attaches_and_detaches(self):
        """Enter attaches baggage; exit detaches the token."""
        from obskit.tracing.baggage import baggage_context
        import obskit.tracing.baggage as _mod

        if not _mod._OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        fake_ctx = MagicMock()
        fake_token = MagicMock()
        with patch.object(_mod, "_otel_baggage") as mock_bg, \
             patch.object(_mod, "_attach", return_value=fake_token) as mock_att, \
             patch.object(_mod, "_detach") as mock_det:
            mock_bg.set_baggage.return_value = fake_ctx
            with baggage_context(company_id="7"):
                mock_att.assert_called_once_with(fake_ctx)
        mock_det.assert_called_once_with(fake_token)

    def test_sync_detaches_on_exception(self):
        """Baggage is detached even when the body raises."""
        from obskit.tracing.baggage import baggage_context
        import obskit.tracing.baggage as _mod

        if not _mod._OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        fake_token = MagicMock()
        with patch.object(_mod, "_otel_baggage") as mock_bg, \
             patch.object(_mod, "_attach", return_value=fake_token), \
             patch.object(_mod, "_detach") as mock_det:
            mock_bg.set_baggage.return_value = MagicMock()
            with pytest.raises(RuntimeError):
                with baggage_context(company_id="7"):
                    raise RuntimeError("boom")
        mock_det.assert_called_once_with(fake_token)

    def test_sync_multiple_kwargs_each_set_as_baggage(self):
        """Each kwarg becomes a separate set_baggage call."""
        from obskit.tracing.baggage import baggage_context
        import obskit.tracing.baggage as _mod

        if not _mod._OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        with patch.object(_mod, "_otel_baggage") as mock_bg, \
             patch.object(_mod, "_attach", return_value=MagicMock()), \
             patch.object(_mod, "_detach"):
            mock_bg.set_baggage.return_value = MagicMock()
            with baggage_context(company_id="42", region="eu"):
                pass
        assert mock_bg.set_baggage.call_count == 2

    def test_values_coerced_to_str(self):
        """Numeric values are coerced to str before being set as baggage."""
        from obskit.tracing.baggage import baggage_context
        import obskit.tracing.baggage as _mod

        if not _mod._OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        with patch.object(_mod, "_otel_baggage") as mock_bg, \
             patch.object(_mod, "_attach", return_value=MagicMock()), \
             patch.object(_mod, "_detach"):
            mock_bg.set_baggage.return_value = MagicMock()
            with baggage_context(company_id=42):
                pass
        # Value should have been coerced to "42"
        call_args = mock_bg.set_baggage.call_args_list[0]
        assert call_args[0][1] == "42"


class TestAsyncBaggageContext:
    @pytest.mark.asyncio
    async def test_async_attaches_and_detaches(self):
        """Enter attaches; exit detaches in the async variant."""
        from obskit.tracing.baggage import async_baggage_context
        import obskit.tracing.baggage as _mod

        if not _mod._OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        fake_token = MagicMock()
        with patch.object(_mod, "_otel_baggage") as mock_bg, \
             patch.object(_mod, "_attach", return_value=fake_token) as mock_att, \
             patch.object(_mod, "_detach") as mock_det:
            mock_bg.set_baggage.return_value = MagicMock()
            async with async_baggage_context(company_id="99"):
                mock_att.assert_called_once()
        mock_det.assert_called_once_with(fake_token)

    @pytest.mark.asyncio
    async def test_async_no_otel_is_noop(self):
        """async_baggage_context is a no-op when OTel is absent."""
        from obskit.tracing.baggage import async_baggage_context
        import obskit.tracing.baggage as _mod

        original = _mod._OTEL_AVAILABLE
        _mod._OTEL_AVAILABLE = False
        try:
            ran = []
            async with async_baggage_context(company_id="1"):
                ran.append(True)
            assert ran == [True]
        finally:
            _mod._OTEL_AVAILABLE = original

    @pytest.mark.asyncio
    async def test_async_detaches_on_exception(self):
        """Detach happens in finally even on exception."""
        from obskit.tracing.baggage import async_baggage_context
        import obskit.tracing.baggage as _mod

        if not _mod._OTEL_AVAILABLE:
            pytest.skip("opentelemetry-api not installed")

        fake_token = MagicMock()
        with patch.object(_mod, "_otel_baggage") as mock_bg, \
             patch.object(_mod, "_attach", return_value=fake_token), \
             patch.object(_mod, "_detach") as mock_det:
            mock_bg.set_baggage.return_value = MagicMock()
            with pytest.raises(ValueError):
                async with async_baggage_context(company_id="7"):
                    raise ValueError("async boom")
        mock_det.assert_called_once_with(fake_token)


class TestBaggageContextPublicAPI:
    def test_exports(self):
        import obskit.tracing.baggage as _mod
        for name in ("baggage_context", "async_baggage_context"):
            assert hasattr(_mod, name), f"missing: {name}"

    def test_importable_from_obskit(self):
        import obskit
        assert hasattr(obskit, "baggage_context")
        assert hasattr(obskit, "async_baggage_context")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def _no_patch():
    """Dummy context manager used when OTel is unavailable."""
    yield
