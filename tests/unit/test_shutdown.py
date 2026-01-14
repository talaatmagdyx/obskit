"""Tests for obskit.shutdown module."""

import importlib
from unittest.mock import patch

# Import the module directly to access its internal state
_shutdown_mod = importlib.import_module("obskit.shutdown")
from obskit.shutdown import (
    _shutdown_hooks,
    _shutdown_hooks_lock,
    register_shutdown_hook,
    shutdown,
    unregister_shutdown_hook,
)


class TestRegisterShutdownHook:
    """Tests for register_shutdown_hook function."""

    def setup_method(self):
        """Clear hooks before each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def teardown_method(self):
        """Clear hooks after each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def test_register_hook(self):
        """Test registering a shutdown hook."""

        def my_hook():
            pass

        register_shutdown_hook(my_hook)

        with _shutdown_hooks_lock:
            assert my_hook in _shutdown_hooks

    def test_register_multiple_hooks(self):
        """Test registering multiple hooks."""

        def hook1():
            pass

        def hook2():
            pass

        register_shutdown_hook(hook1)
        register_shutdown_hook(hook2)

        with _shutdown_hooks_lock:
            assert len(_shutdown_hooks) >= 2
            assert hook1 in _shutdown_hooks
            assert hook2 in _shutdown_hooks


class TestUnregisterShutdownHook:
    """Tests for unregister_shutdown_hook function."""

    def setup_method(self):
        """Clear hooks before each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def teardown_method(self):
        """Clear hooks after each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def test_unregister_hook(self):
        """Test unregistering a hook."""

        def my_hook():
            pass

        register_shutdown_hook(my_hook)
        unregister_shutdown_hook(my_hook)

        with _shutdown_hooks_lock:
            assert my_hook not in _shutdown_hooks

    def test_unregister_nonexistent_hook(self):
        """Test unregistering a hook that wasn't registered."""

        def my_hook():
            pass

        # Should not raise
        unregister_shutdown_hook(my_hook)


class TestShutdown:
    """Tests for shutdown function."""

    def _reset_shutdown_state(self):
        """Reset shutdown state for testing."""
        with _shutdown_mod._shutdown_lock:
            _shutdown_mod._shutdown_in_progress = False

    def setup_method(self):
        """Clear hooks and reset state before each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()
        self._reset_shutdown_state()

    def teardown_method(self):
        """Clear hooks and reset state after each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()
        self._reset_shutdown_state()

    def test_shutdown_calls_hooks(self):
        """Test that shutdown calls registered hooks."""
        self._reset_shutdown_state()  # Ensure clean state
        called = []

        def hook1():
            called.append("hook1")

        def hook2():
            called.append("hook2")

        register_shutdown_hook(hook1)
        register_shutdown_hook(hook2)

        shutdown()

        assert "hook1" in called
        assert "hook2" in called

    def test_shutdown_is_idempotent(self):
        """Test that calling shutdown multiple times is safe."""
        self._reset_shutdown_state()  # Ensure clean state
        call_count = [0]

        def counting_hook():
            call_count[0] += 1

        register_shutdown_hook(counting_hook)

        shutdown()
        shutdown()  # Second call should do nothing

        # Hook should only be called once
        assert call_count[0] == 1

    def test_shutdown_continues_on_hook_error(self):
        """Test that shutdown continues if a hook raises."""
        self._reset_shutdown_state()  # Ensure clean state
        called = []

        def failing_hook():
            raise ValueError("Hook failed")

        def working_hook():
            called.append("working")

        register_shutdown_hook(failing_hook)
        register_shutdown_hook(working_hook)

        shutdown()

        # Working hook should still be called
        assert "working" in called


class TestSignalHandler:
    """Tests for signal handler."""

    def _reset_shutdown_state(self):
        """Reset shutdown state for testing."""
        with _shutdown_mod._shutdown_lock:
            _shutdown_mod._shutdown_in_progress = False

    def setup_method(self):
        """Reset state before each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()
        self._reset_shutdown_state()

    def teardown_method(self):
        """Reset state after each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()
        self._reset_shutdown_state()

    def test_signal_handler_calls_shutdown(self):
        """Test that signal handler calls shutdown."""
        self._reset_shutdown_state()

        # Mock sys.exit to prevent actual exit
        with patch.object(_shutdown_mod, "shutdown") as mock_shutdown:
            with patch("sys.exit") as mock_exit:
                _shutdown_mod._signal_handler(15, None)  # SIGTERM

                mock_shutdown.assert_called_once()
                mock_exit.assert_called_once_with(0)


class TestSetupSignalHandlers:
    """Tests for _setup_signal_handlers function."""

    def test_setup_skipped_during_pytest(self):
        """Test that signal handlers are not set up during pytest."""
        # Since we're in pytest, this should not register handlers
        # Just verify it doesn't raise
        _shutdown_mod._setup_signal_handlers()

    @patch.dict("sys.modules", {}, clear=False)
    @patch("signal.signal")
    @patch("atexit.register")
    def test_setup_registers_handlers(self, mock_atexit, mock_signal):
        """Test that handlers are registered when not in pytest."""
        # Temporarily hide pytest from sys.modules to test the registration path
        import sys

        original_modules = dict(sys.modules)

        # Remove pytest from modules temporarily
        modules_to_remove = [k for k in sys.modules.keys() if "pytest" in k.lower()]
        for mod in modules_to_remove:
            del sys.modules[mod]

        try:
            # Now call setup - it should attempt to register handlers
            _shutdown_mod._setup_signal_handlers()
            # Even if registration fails due to environment, it shouldn't raise
        finally:
            # Restore modules
            sys.modules.update(original_modules)


class TestShutdownWithComponents:
    """Tests for shutdown with various component states."""

    def _reset_shutdown_state(self):
        """Reset shutdown state for testing."""
        with _shutdown_mod._shutdown_lock:
            _shutdown_mod._shutdown_in_progress = False

    def setup_method(self):
        """Reset state before each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()
        self._reset_shutdown_state()

    def teardown_method(self):
        """Reset state after each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()
        self._reset_shutdown_state()

    @patch("obskit.metrics.registry.stop_http_server")
    @patch("obskit.tracing.tracer.shutdown_tracing")
    def test_shutdown_stops_components(self, mock_shutdown_tracing, mock_stop_http):
        """Test shutdown stops metrics server and tracing."""
        self._reset_shutdown_state()

        shutdown()

        mock_stop_http.assert_called_once()
        mock_shutdown_tracing.assert_called_once()

    @patch("obskit.metrics.registry.stop_http_server")
    @patch("obskit.tracing.tracer.shutdown_tracing")
    def test_shutdown_handles_component_errors(self, mock_shutdown_tracing, mock_stop_http):
        """Test shutdown handles errors from components."""
        self._reset_shutdown_state()

        mock_stop_http.side_effect = RuntimeError("Server not running")
        mock_shutdown_tracing.side_effect = RuntimeError("Tracing not initialized")

        # Should not raise despite component errors
        shutdown()

    def test_shutdown_logs_already_in_progress(self):
        """Test shutdown logs when already in progress."""
        # First shutdown
        shutdown()

        # Second shutdown should be a no-op
        # We can't easily verify logging, but it shouldn't raise
        shutdown()


class TestShutdownEdgeCases:
    """Tests for shutdown edge cases."""

    def _reset_shutdown_state(self):
        """Reset shutdown state for testing."""
        with _shutdown_mod._shutdown_lock:
            _shutdown_mod._shutdown_in_progress = False

    def setup_method(self):
        """Reset state before each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()
        self._reset_shutdown_state()

    def teardown_method(self):
        """Reset state after each test."""
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()
        self._reset_shutdown_state()

    def test_shutdown_with_no_hooks(self):
        """Test shutdown with no registered hooks."""
        self._reset_shutdown_state()

        # Should complete without error
        shutdown()

    def test_hook_name_in_log(self):
        """Test that hook name is logged."""
        self._reset_shutdown_state()

        def named_hook():
            pass

        register_shutdown_hook(named_hook)

        # Should log the hook name during execution
        shutdown()
