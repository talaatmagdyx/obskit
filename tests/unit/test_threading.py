"""Unit tests for obskit.threading — context-propagating Thread."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from obskit.threading import (
    _ContextThread,
    _original_thread,
    patch_threading,
    reset_threading_patch,
)


@pytest.fixture(autouse=True)
def _restore_threading():
    """Ensure threading.Thread is restored after every test."""
    yield
    reset_threading_patch()


class TestPatchThreading:
    def test_patch_replaces_threading_thread(self):
        patch_threading()
        assert threading.Thread is _ContextThread

    def test_patch_is_idempotent(self):
        patch_threading()
        patch_threading()
        assert threading.Thread is _ContextThread

    def test_reset_restores_original(self):
        patch_threading()
        reset_threading_patch()
        assert threading.Thread is _original_thread

    def test_reset_idempotent_without_patch(self):
        # Should not raise even if called before patch
        reset_threading_patch()
        assert threading.Thread is _original_thread


class TestContextPropagation:
    def test_structlog_context_copied_to_thread(self):
        """Context vars bound before thread.start() appear inside the thread."""
        from structlog.contextvars import bind_contextvars, clear_contextvars

        clear_contextvars()
        bind_contextvars(company_id="acme", request_id="req-1")

        captured: dict = {}

        def worker():
            from structlog.contextvars import get_contextvars

            captured.update(get_contextvars())

        t = _ContextThread(target=worker)
        t.start()
        t.join(timeout=5)

        assert captured.get("company_id") == "acme"
        assert captured.get("request_id") == "req-1"

        clear_contextvars()

    def test_empty_context_does_not_raise(self):
        """Thread with no bound context starts and runs cleanly."""
        from structlog.contextvars import clear_contextvars

        clear_contextvars()
        ran = []

        t = _ContextThread(target=lambda: ran.append(True))
        t.start()
        t.join(timeout=5)

        assert ran == [True]

    def test_thread_context_isolated_from_parent(self):
        """Mutations inside the thread do NOT leak back to the parent."""
        from structlog.contextvars import (
            bind_contextvars,
            clear_contextvars,
            get_contextvars,
        )

        clear_contextvars()
        bind_contextvars(base="parent")

        def worker():
            from structlog.contextvars import bind_contextvars

            bind_contextvars(inside="thread")

        t = _ContextThread(target=worker)
        t.start()
        t.join(timeout=5)

        # Parent context should not contain "inside"
        ctx = get_contextvars()
        assert "inside" not in ctx

        clear_contextvars()

    def test_otel_context_copied_when_available(self):
        """If opentelemetry is installed, attach() is called inside the thread."""
        import opentelemetry.context as _otel_ctx_mod

        fake_token = object()
        fake_ctx = object()

        from structlog.contextvars import clear_contextvars

        clear_contextvars()

        with (
            patch.object(_otel_ctx_mod, "get_current", return_value=fake_ctx),
            patch.object(_otel_ctx_mod, "attach", return_value=fake_token) as mock_attach,
            patch.object(_otel_ctx_mod, "detach") as mock_detach,
        ):
            t = _ContextThread(target=lambda: None)
            t.start()
            t.join(timeout=5)

        mock_attach.assert_called_once_with(fake_ctx)
        mock_detach.assert_called_once_with(fake_token)

    def test_otel_skipped_when_not_installed(self):
        """Thread starts and runs normally even when opentelemetry is absent."""
        from structlog.contextvars import clear_contextvars

        clear_contextvars()
        ran = []

        with patch("builtins.__import__", side_effect=lambda name, *a, **kw: (
            (_ for _ in ()).throw(ImportError("no otel")) if "opentelemetry" in name
            else __import__(name, *a, **kw)
        )):
            # Use the _ContextThread directly without triggering the import
            # inside start() — simulate by manually setting _obskit_otel_ctx=None
            t = _ContextThread(target=lambda: ran.append(True))
            t._obskit_log_ctx = {}
            t._obskit_otel_ctx = None
            # Call run() directly to avoid double-start complexity
            t.run()  # type: ignore[call-arg]

        assert ran == [True]

    def test_subclassing_works(self):
        """Users can subclass _ContextThread; context is available after super().run()."""
        from structlog.contextvars import bind_contextvars, clear_contextvars

        clear_contextvars()
        bind_contextvars(env="test")

        captured = []

        class MyThread(_ContextThread):
            def run(self):
                # Call super().run() first — it sets up the copied context, then
                # runs _target (None here).  After it returns, context is still set.
                super().run()
                from structlog.contextvars import get_contextvars

                captured.append(get_contextvars())

        t = MyThread()
        t.start()
        t.join(timeout=5)

        assert captured[0].get("env") == "test"
        clear_contextvars()


class TestContextThreadAttributes:
    def test_is_subclass_of_threading_thread(self):
        assert issubclass(_ContextThread, _original_thread)

    def test_original_thread_saved(self):
        assert _original_thread is threading.Thread or _original_thread.__name__ == "Thread"
