"""Unit tests for obskit.tracing.tracer.use_span_context."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestUseSpanContext:
    def test_none_ctx_is_noop(self):
        """use_span_context(None) enters and exits without touching OTel."""
        from obskit.tracing.tracer import use_span_context

        ran = []
        with use_span_context(None):
            ran.append(True)
        assert ran == [True]

    def test_none_ctx_does_not_call_attach(self):
        """attach is never called when ctx is None."""
        from obskit.tracing.tracer import use_span_context
        import obskit.tracing.tracer as _mod

        with patch.object(_mod, "context_api") as mock_ctx_api:
            with use_span_context(None):
                pass
        mock_ctx_api.attach.assert_not_called()

    def test_valid_ctx_attaches_and_detaches(self):
        """A valid context is attached on enter and detached on exit."""
        from obskit.tracing.tracer import use_span_context
        import obskit.tracing.tracer as _mod

        fake_ctx = MagicMock()
        fake_token = MagicMock()
        with patch.object(_mod, "context_api") as mock_ctx_api:
            mock_ctx_api.attach.return_value = fake_token
            ran = []
            with use_span_context(fake_ctx):
                mock_ctx_api.attach.assert_called_once_with(fake_ctx)
                ran.append(True)
        mock_ctx_api.detach.assert_called_once_with(fake_token)
        assert ran == [True]

    def test_detaches_on_exception(self):
        """detach is always called in finally even when body raises."""
        from obskit.tracing.tracer import use_span_context
        import obskit.tracing.tracer as _mod

        fake_token = MagicMock()
        with patch.object(_mod, "context_api") as mock_ctx_api:
            mock_ctx_api.attach.return_value = fake_token
            with pytest.raises(RuntimeError, match="boom"):
                with use_span_context(MagicMock()):
                    raise RuntimeError("boom")
        mock_ctx_api.detach.assert_called_once_with(fake_token)

    def test_importable_from_tracer(self):
        from obskit.tracing.tracer import use_span_context

        assert callable(use_span_context)
