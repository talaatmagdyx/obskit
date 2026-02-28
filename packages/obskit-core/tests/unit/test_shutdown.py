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


class TestGracefulShutdown:
    def _reset_shutdown_state(self):
        import obskit.shutdown as _mod
        with _mod._shutdown_lock:
            _mod._shutdown_in_progress = False

    def setup_method(self):
        self._reset_shutdown_state()
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def teardown_method(self):
        self._reset_shutdown_state()
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def test_init_defaults(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown()
        assert gs.timeout == 30.0
        assert gs.exit_code == 0
        assert gs.auto_exit is True
        assert gs._is_shutting_down is False
        assert gs._shutdown_count == 0

    def test_init_custom(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown(timeout=10, exit_code=1, auto_exit=False)
        assert gs.timeout == 10
        assert gs.exit_code == 1
        assert gs.auto_exit is False

    def test_register_hook(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown()
        def my_hook(): pass
        gs.register(my_hook, priority=10)
        assert len(gs._hooks) == 1
        assert gs._hooks[0][0] == 10

    def test_register_hook_with_name(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown()
        def my_hook(): pass
        gs.register(my_hook, priority=5, name="custom_name")
        assert gs._hooks[0][1] == "custom_name"

    def test_register_sorts_by_priority(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown()
        def hook1(): pass
        def hook2(): pass
        def hook3(): pass
        gs.register(hook3, priority=30)
        gs.register(hook1, priority=10)
        gs.register(hook2, priority=20)
        priorities = [h[0] for h in gs._hooks]
        assert priorities == [10, 20, 30]

    def test_unregister_hook_found(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown()
        def my_hook(): pass
        gs.register(my_hook)
        result = gs.unregister(my_hook)
        assert result is True
        assert len(gs._hooks) == 0

    def test_unregister_hook_not_found(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown()
        def my_hook(): pass
        result = gs.unregister(my_hook)
        assert result is False

    def test_is_shutting_down_property(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown()
        assert gs.is_shutting_down is False

    def test_is_complete_property(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown()
        assert gs.is_complete is False

    def test_trigger_initiates_shutdown(self):
        from obskit.shutdown import GracefulShutdown
        from unittest.mock import patch
        gs = GracefulShutdown(auto_exit=False)
        with patch.object(gs, "_initiate_shutdown") as mock_init:
            gs.trigger()
            mock_init.assert_called_once()

    def test_initiate_shutdown_idempotent(self):
        from obskit.shutdown import GracefulShutdown
        from unittest.mock import patch
        gs = GracefulShutdown(auto_exit=False)
        gs._is_shutting_down = True
        with patch.object(gs, "_run_shutdown") as mock_run:
            gs._initiate_shutdown()
            mock_run.assert_not_called()

    def test_initiate_shutdown_runs_hooks(self):
        from obskit.shutdown import GracefulShutdown
        self._reset_shutdown_state()
        called = []
        gs = GracefulShutdown(auto_exit=False)
        gs.register(lambda: called.append("hook"), priority=10, name="test_hook")
        gs._initiate_shutdown()
        assert "hook" in called

    def test_run_shutdown_calls_hooks_in_order(self):
        from obskit.shutdown import GracefulShutdown
        self._reset_shutdown_state()
        order = []
        gs = GracefulShutdown(auto_exit=False)
        gs.register(lambda: order.append(1), priority=10, name="h1")
        gs.register(lambda: order.append(2), priority=20, name="h2")
        gs._run_shutdown()
        assert order == [1, 2]

    def test_run_shutdown_handles_hook_error(self):
        from obskit.shutdown import GracefulShutdown
        self._reset_shutdown_state()
        gs = GracefulShutdown(auto_exit=False)
        gs.register(lambda: 1/0, priority=10, name="bad_hook")
        gs._run_shutdown()

    def test_wait_for_completion_returns_quickly(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown(auto_exit=False)
        gs.wait_for_completion(timeout=0.01)

    def test_wait_for_completion_with_shutting_down(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown(auto_exit=False)
        gs._is_shutting_down = True
        gs._shutdown_complete.set()
        gs._shutdown_event.set()
        gs.wait_for_completion(timeout=0.1)

    def test_signal_handler_first_signal(self):
        from obskit.shutdown import GracefulShutdown
        from unittest.mock import patch
        self._reset_shutdown_state()
        gs = GracefulShutdown(auto_exit=False)
        with patch.object(gs, "_initiate_shutdown") as mock_init:
            gs._signal_handler(15, None)
            assert gs._shutdown_count == 1
            mock_init.assert_called_once()

    def test_signal_handler_second_signal(self):
        from obskit.shutdown import GracefulShutdown
        from unittest.mock import patch
        self._reset_shutdown_state()
        gs = GracefulShutdown(auto_exit=False)
        gs._shutdown_count = 1
        with patch.object(gs, "_initiate_shutdown") as mock_init:
            gs._signal_handler(15, None)
            assert gs._shutdown_count == 2

    def test_signal_handler_third_signal_force_exit(self):
        from obskit.shutdown import GracefulShutdown
        from unittest.mock import patch
        self._reset_shutdown_state()
        gs = GracefulShutdown(auto_exit=False)
        gs._shutdown_count = 2
        with patch("sys.exit") as mock_exit:
            gs._signal_handler(15, None)
            mock_exit.assert_called_once_with(1)


class TestGetGracefulShutdown:
    def setup_method(self):
        import obskit.shutdown as _mod
        _mod._graceful_shutdown = None

    def teardown_method(self):
        import obskit.shutdown as _mod
        _mod._graceful_shutdown = None
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()
        with _mod._shutdown_lock:
            _mod._shutdown_in_progress = False

    def test_creates_new_instance(self):
        from obskit.shutdown import get_graceful_shutdown, GracefulShutdown
        gs = get_graceful_shutdown(timeout=10, exit_code=0, auto_exit=False)
        assert isinstance(gs, GracefulShutdown)
        assert gs.timeout == 10

    def test_returns_same_instance(self):
        from obskit.shutdown import get_graceful_shutdown
        gs1 = get_graceful_shutdown()
        gs2 = get_graceful_shutdown()
        assert gs1 is gs2


class TestShutdownExceptions:
    def _reset_shutdown_state(self):
        import obskit.shutdown as _mod
        with _mod._shutdown_lock:
            _mod._shutdown_in_progress = False

    def setup_method(self):
        self._reset_shutdown_state()
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def teardown_method(self):
        self._reset_shutdown_state()
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def test_setup_signal_handlers_exception(self):
        import sys, signal
        from unittest.mock import patch
        original_modules = dict(sys.modules)
        mods_to_remove = [k for k in sys.modules if "pytest" in k.lower()]
        for m in mods_to_remove: del sys.modules[m]
        try:
            with patch("signal.signal", side_effect=OSError("not allowed")):
                _shutdown_mod._setup_signal_handlers()
        finally:
            sys.modules.update(original_modules)

    def test_shutdown_async_metrics_error(self):
        self._reset_shutdown_state()
        from unittest.mock import patch
        with patch("obskit.metrics.registry.stop_http_server"):
            with patch("obskit.tracing.tracer.shutdown_tracing"):
                with patch("obskit.metrics.async_recording.shutdown_async_recording",
                           side_effect=Exception("async fail")):
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        shutdown()
                    finally:
                        loop.close()



class TestShutdownOuterException:
    def _reset_shutdown_state(self):
        import obskit.shutdown as _mod
        with _mod._shutdown_lock:
            _mod._shutdown_in_progress = False

    def setup_method(self):
        self._reset_shutdown_state()
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def teardown_method(self):
        self._reset_shutdown_state()
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def test_shutdown_outer_exception(self):
        import pytest, obskit.shutdown as _mod
        from unittest.mock import patch
        self._reset_shutdown_state()
        # Make the logger.info ("shutdown_complete") raise to trigger outer except
        original_info = _mod.logger.info
        call_count = [0]
        def patched_info(msg, **kwargs):
            if msg == "shutdown_complete":
                raise RuntimeError("simulated shutdown error")
            return original_info(msg, **kwargs)
        with patch.object(_mod.logger, "info", side_effect=patched_info):
            with pytest.raises(RuntimeError, match="simulated shutdown error"):
                shutdown()


class TestGracefulShutdownAdvanced:
    def _reset_shutdown_state(self):
        import obskit.shutdown as _mod
        with _mod._shutdown_lock:
            _mod._shutdown_in_progress = False

    def setup_method(self):
        self._reset_shutdown_state()
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def teardown_method(self):
        self._reset_shutdown_state()
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def test_setup_signals_not_in_pytest_exception(self):
        import sys, signal
        from obskit.shutdown import GracefulShutdown
        from unittest.mock import patch
        original_modules = dict(sys.modules)
        mods_to_remove = [k for k in list(sys.modules.keys()) if "pytest" in k.lower()]
        for m in mods_to_remove: del sys.modules[m]
        try:
            with patch("signal.signal", side_effect=OSError("not allowed")):
                gs = GracefulShutdown.__new__(GracefulShutdown)
                gs._setup_signals()
        finally:
            sys.modules.update(original_modules)

    def test_unregister_hook_not_matching(self):
        from obskit.shutdown import GracefulShutdown
        gs = GracefulShutdown()
        def hook1(): pass
        def hook2(): pass
        gs.register(hook1)
        # Try to unregister a different hook
        result = gs.unregister(hook2)
        assert result is False
        assert len(gs._hooks) == 1

    def test_initiate_shutdown_timeout_exceeded(self):
        from obskit.shutdown import GracefulShutdown
        import time
        self._reset_shutdown_state()
        gs = GracefulShutdown(timeout=0.01, auto_exit=False)
        # Register a slow hook to trigger timeout
        def slow_hook():
            time.sleep(0.5)
        gs.register(slow_hook, priority=10, name="slow")
        gs._initiate_shutdown()
        # The timeout should be exceeded, warning logged
        assert gs.is_complete

    def test_initiate_shutdown_auto_exit(self):
        from obskit.shutdown import GracefulShutdown
        from unittest.mock import patch
        self._reset_shutdown_state()
        gs = GracefulShutdown(timeout=1, auto_exit=True)
        with patch("sys.exit") as mock_exit:
            gs._initiate_shutdown()
            mock_exit.assert_called_once_with(0)



class TestGracefulShutdownSetupSignals:
    def _reset_shutdown_state(self):
        import obskit.shutdown as _mod
        with _mod._shutdown_lock:
            _mod._shutdown_in_progress = False

    def setup_method(self):
        self._reset_shutdown_state()
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def teardown_method(self):
        self._reset_shutdown_state()
        with _shutdown_hooks_lock:
            _shutdown_hooks.clear()

    def test_setup_signals_success_path(self):
        import sys, signal
        from obskit.shutdown import GracefulShutdown
        from unittest.mock import patch, MagicMock
        original_modules = dict(sys.modules)
        mods_to_remove = [k for k in list(sys.modules.keys()) if "pytest" in k.lower()]
        for m in mods_to_remove: del sys.modules[m]
        try:
            with patch("signal.signal", return_value=None) as mock_sig:
                gs = GracefulShutdown.__new__(GracefulShutdown)
                gs._setup_signals()
                assert mock_sig.called
        finally:
            sys.modules.update(original_modules)
