"""Tests to cover remaining branch misses in shedding, degradation, failover, circuit_breaker."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone, UTC
from unittest.mock import MagicMock

import pytest


class TestSheddingBranchCoverage:
    """Cover missing branches in shedding.py."""

    def test_latency_samples_over_100_trims(self):
        """Line 210: latency_samples > 100 trims to last 100."""
        from obskit.shedding import LoadShedder

        shedder = LoadShedder(name="test-latency-trim", max_latency_ms=500.0)

        # Use should_process with latency_ms to trigger line 209-210
        for i in range(101):
            shedder.should_process(latency_ms=float(i))

        assert len(shedder._latency_samples) == 100

    def test_evaluate_shed_rate_zero_max_queue_size(self):
        """Lines 267->270, 271->275: max_queue_size=0 and max_latency_ms=0."""
        from datetime import timedelta

        from obskit.shedding import LoadShedder

        # max_queue_size=0 -> queue_load branch is False
        # max_latency_ms=0 -> latency_load branch is False
        shedder = LoadShedder(name="test-zero-queue", max_queue_size=0, max_latency_ms=0.0, adaptive=True)
        # Force evaluation window to 0 so it evaluates
        shedder.config.evaluation_window_seconds = 0.0
        # Force last eval to past
        shedder._last_evaluation = datetime.now(UTC) - timedelta(seconds=100)

        # Trigger _evaluate_shed_rate via should_process
        shedder.should_process(queue_size=100)
        # Should complete without error

    def test_get_stats_zero_max_sizes(self):
        """Lines 344->347, 348->351: max_queue_size=0 and max_latency_ms=0 in get_stats."""
        from obskit.shedding import LoadShedder

        shedder = LoadShedder(name="test-stats-zero", max_queue_size=0, max_latency_ms=0.0)
        stats = shedder.get_stats()

        assert stats.load_level == pytest.approx(0.0)

    def test_get_load_shedder_inner_lock_branch(self):
        """Lines 375->378: inner lock branch in get_load_shedder singleton."""
        import obskit.shedding as mod
        from obskit.shedding import get_load_shedder

        unique_name = "__inner_lock_shedder__"
        mod._shedders.pop(unique_name, None)

        class _FakeDict(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._first_call_done = False
                self._target_key = None

            def __contains__(self, key):
                if key == self._target_key and not self._first_call_done:
                    self._first_call_done = True
                    return False
                return super().__contains__(key)

        from obskit.shedding import LoadShedder
        existing = LoadShedder(name=unique_name)

        fake_dict = _FakeDict()
        fake_dict._target_key = unique_name
        fake_dict[unique_name] = existing

        original = mod._shedders
        mod._shedders = fake_dict
        try:
            result = get_load_shedder(unique_name)
            assert result is existing
        finally:
            mod._shedders = original
            mod._shedders.pop(unique_name, None)


class TestDegradationRemainingBranchCoverage:
    """Cover remaining missing branches in degradation.py."""

    def test_is_enabled_with_disabled_dependency(self):
        """Lines 223-224: dep_feature exists and is disabled -> returns False."""
        from obskit.degradation import DegradationManager

        mgr = DegradationManager("test-dep-disabled")
        mgr.register_feature("dep_feature")
        mgr.register_feature("main_feature", dependencies=["dep_feature"])

        # Disable the dependency
        mgr.degrade_feature("dep_feature", reason="test")

        # main_feature should be reported as disabled due to disabled dep
        enabled = mgr.is_enabled("main_feature")
        assert not enabled

    def test_is_enabled_with_dependency_loop_skips_none_dep(self):
        """Line 223->221: dep_feature is None (not registered) -> loop continues."""
        from obskit.degradation import DegradationManager

        mgr = DegradationManager("test-dep-none")
        # Register feature with a dependency that doesn't exist
        mgr.register_feature("main_feature", dependencies=["nonexistent_dep"])

        # dep_feature will be None -> condition is False -> loop continues to end
        enabled = mgr.is_enabled("main_feature")
        assert enabled  # Feature itself is enabled

    def test_set_level_with_matching_enum_value(self):
        """Lines 280-281: for-else loop finds a matching level and breaks."""
        from obskit.degradation import DegradationLevel, DegradationManager

        mgr = DegradationManager("test-set-level-25")
        # Use int 25 -> exactly matches DegradationLevel.LOW
        mgr.set_level(25)

        state = mgr.get_state()
        assert state.level == DegradationLevel.LOW

    def test_degrade_feature_not_registered(self):
        """Line 327->exit: feature_name not in features -> body skipped."""
        from obskit.degradation import DegradationManager

        mgr = DegradationManager("test-degrade-not-registered")
        # Feature not registered -> if check is False -> no-op
        mgr.degrade_feature("nonexistent_feature", reason="test")
        # No error should occur

    def test_restore_feature_not_registered(self):
        """Line 341->exit: feature_name not in features -> body skipped."""
        from obskit.degradation import DegradationManager

        mgr = DegradationManager("test-restore-not-registered")
        # Feature not registered -> if check is False -> no-op
        mgr.restore_feature("nonexistent_feature")

    def test_evaluate_metrics_high_score_critical(self):
        """Line 400: score >= 75 sets CRITICAL level."""
        from obskit.degradation import DegradationLevel, DegradationManager

        mgr = DegradationManager("test-critical-score", auto_degrade=True)
        # error_rate=1.0 -> score = min(50, (1.0/0.1)*25) = 50
        # plus latency_ms=2000 with default threshold=500 -> score += min(50, (2000/500)*25) = 50
        # total = 100 -> CRITICAL
        mgr.evaluate_metrics(error_rate=1.0, latency_ms=2000)

        state = mgr.get_state()
        assert state.level == DegradationLevel.CRITICAL

    def test_evaluate_metrics_high_latency_score(self):
        """Lines 384-385: latency above threshold adds score, line 402 HIGH level."""
        from obskit.degradation import DegradationLevel, DegradationManager

        mgr = DegradationManager("test-latency-score", auto_degrade=True)
        # latency threshold default 1000ms, 2200ms -> score = min(50, (2200/1000)*25) = 50 -> HIGH
        mgr.evaluate_metrics(latency_ms=2200)

        state = mgr.get_state()
        assert state.level == DegradationLevel.HIGH

    def test_evaluate_metrics_high_memory(self):
        """Lines 392-393: memory above threshold adds score."""
        from obskit.degradation import DegradationLevel, DegradationManager

        mgr = DegradationManager("test-memory-score", auto_degrade=True)
        # memory threshold default 90, memory_percent=92 -> score = min(30, (92-90)/2) = 1 -> LOW
        mgr.evaluate_metrics(memory_percent=92)

        state = mgr.get_state()
        assert state.level == DegradationLevel.LOW

    def test_get_degradation_manager_inner_lock_branch(self):
        """Lines 456->459: inner lock branch in singleton."""
        import obskit.degradation as mod

        unique_name = "__inner_lock_mgr__"
        mod._managers.pop(unique_name, None)

        class _FakeDict(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._first_call_done = False
                self._target_key = None

            def __contains__(self, key):
                if key == self._target_key and not self._first_call_done:
                    self._first_call_done = True
                    return False
                return super().__contains__(key)

        from obskit.degradation import DegradationManager, get_degradation_manager

        existing = DegradationManager(unique_name)

        fake_dict = _FakeDict()
        fake_dict._target_key = unique_name
        fake_dict[unique_name] = existing

        original = mod._managers
        mod._managers = fake_dict
        try:
            result = get_degradation_manager(unique_name)
            assert result is existing
        finally:
            mod._managers = original
            mod._managers.pop(unique_name, None)


class TestFailoverRemainingBranchCoverage:
    """Cover remaining missing branches in failover.py."""

    def test_check_health_primary_no_health_check(self):
        """Line 275->284: primary has no health_check function."""
        from obskit.failover import FailoverCoordinator

        coordinator = FailoverCoordinator("test-no-health-check")
        coordinator.register_primary("primary")  # No health_check
        coordinator.register_backup("backup")

        coordinator.check_health()  # Should skip health check -> 275 is False
        # Primary stays healthy since no check was performed
        assert coordinator._primary.is_healthy

    def test_update_endpoint_health_below_failure_threshold(self):
        """Line 305->308: consecutive_failures < failure_threshold -> is_healthy stays True."""
        from obskit.failover import FailoverCoordinator

        coordinator = FailoverCoordinator("test-below-threshold", failure_threshold=3)
        coordinator.register_primary("primary")

        # 2 failures, threshold=3 -> is_healthy should still be True
        coordinator._update_endpoint_health(coordinator._primary, False)
        coordinator._update_endpoint_health(coordinator._primary, False)

        assert coordinator._primary.is_healthy
        assert coordinator._primary.consecutive_failures == 2

    def test_evaluate_state_backup_to_primary_recovery(self):
        """Lines 325->335, 328-330: auto-recover from BACKUP to PRIMARY."""
        from datetime import datetime

        from obskit.failover import FailoverCoordinator, FailoverState

        coordinator = FailoverCoordinator(
            "test-recovery",
            auto_recover=True,
            recovery_threshold=1,
            failure_threshold=1,
        )
        coordinator.register_primary("primary")
        coordinator.register_backup("backup")

        # Force to BACKUP state with failover_time set
        coordinator._state = FailoverState.BACKUP
        coordinator._primary.is_healthy = True
        coordinator._backup.is_healthy = True
        coordinator._failover_time = datetime.now(UTC)

        # Trigger evaluate - recovery_successes will be incremented and >= threshold
        coordinator._evaluate_state()

    def test_do_recovery_with_failover_time_set(self):
        """Line 382->390: _do_recovery when _failover_time is set logs recovery."""
        from datetime import datetime

        from obskit.failover import FailoverCoordinator, FailoverState

        coordinator = FailoverCoordinator(
            "test-do-recovery",
            auto_recover=True,
            recovery_threshold=1,
            failure_threshold=1,
        )
        coordinator.register_primary("primary")
        coordinator.register_backup("backup")

        # Set up BACKUP state with failover_time
        coordinator._state = FailoverState.BACKUP
        coordinator._primary.is_healthy = True
        coordinator._failover_time = datetime.now(UTC)

        coordinator._do_recovery()

        assert coordinator._state == FailoverState.PRIMARY
        assert coordinator._failover_time is None

    def test_force_failover_when_not_in_primary_state(self):
        """Line 404->exit: force_failover when state is not PRIMARY."""
        from obskit.failover import FailoverCoordinator, FailoverState

        coordinator = FailoverCoordinator("test-force-failover-no-op")
        coordinator.register_primary("primary")
        coordinator.register_backup("backup")

        # Force to BACKUP state (not PRIMARY)
        coordinator._state = FailoverState.BACKUP

        coordinator.force_failover()  # Should be no-op (state != PRIMARY)
        assert coordinator._state == FailoverState.BACKUP  # Unchanged

    def test_force_recovery_when_not_in_backup_state(self):
        """Line 432->exit: force_recovery when state is not BACKUP."""
        from obskit.failover import FailoverCoordinator, FailoverState

        coordinator = FailoverCoordinator("test-force-recovery-no-op")
        coordinator.register_primary("primary")
        coordinator.register_backup("backup")

        # State is PRIMARY (not BACKUP)
        assert coordinator._state == FailoverState.PRIMARY

        coordinator.force_recovery()  # Should be no-op (state != BACKUP)
        assert coordinator._state == FailoverState.PRIMARY  # Unchanged

    def test_stop_monitoring_no_thread(self):
        """Line 449->452: _check_thread is None so join is skipped."""
        from obskit.failover import FailoverCoordinator

        coordinator = FailoverCoordinator("test-stop-no-thread")
        assert coordinator._check_thread is None

        coordinator.stop_monitoring()  # Should not raise


class TestCircuitBreakerBranchCoverage:
    """Cover remaining branch misses in resilience/circuit_breaker.py."""

    @pytest.mark.asyncio
    async def test_aexit_with_non_exception_basexception(self):
        """Line 601->605: exc_val is BaseException but not Exception -> skip failure."""
        from obskit.resilience.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(name="test-async-basexc", failure_threshold=5)

        # Create context manually and call __aexit__ with BaseException (not Exception)
        _ctx = cb.__aenter__
        await cb.__aenter__()

        # SystemExit is BaseException but NOT Exception
        result = await cb.__aexit__(SystemExit, SystemExit(0), None)
        # Should NOT record failure (isinstance check fails)
        assert result is False

    def test_exit_with_non_exception_basexception(self):
        """Line 686->690: exc_val is BaseException but not Exception -> skip failure."""
        from obskit.resilience.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(name="test-sync-basexc", failure_threshold=5)
        cb.__enter__()

        result = cb.__exit__(SystemExit, SystemExit(0), None)
        assert result is False

    def test_should_allow_request_sync_open_no_last_failure_time(self):
        """Line 707->721: OPEN state with last_failure_time=None -> returns False."""
        from obskit.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(name="test-sync-open-no-time", failure_threshold=1, recovery_timeout=100.0)

        # Force to OPEN state directly
        with cb._lock:
            cb._state = CircuitState.OPEN
            cb._last_failure_time = None  # No failure time recorded

        # Should return False (can't determine elapsed time)
        allowed = cb._should_allow_request_sync()
        assert not allowed

    def test_record_success_sync_in_closed_state(self):
        """Line 743->exit: CLOSED state on success resets failure count."""
        from obskit.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(name="test-sync-success-closed", failure_threshold=5)

        # Manually increment failure count
        cb._failure_count = 3

        # Record success in CLOSED state
        cb._record_success_sync()

        assert cb._failure_count == 0

    def test_record_failure_sync_in_half_open_state(self):
        """Line 773->exit: HALF_OPEN state on failure re-opens circuit."""
        from obskit.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(name="test-sync-fail-halfopen", failure_threshold=5)

        # Force to HALF_OPEN state
        with cb._lock:
            cb._state = CircuitState.HALF_OPEN
            cb._half_open_successes = 0

        cb._record_failure_sync(ValueError("half open fail"))

        assert cb._state == CircuitState.OPEN


class TestFailoverMoreBranches:
    """Cover remaining failover.py branch misses."""

    def test_evaluate_state_in_failing_over_state(self):
        """Line 325->335: state is FAILING_OVER (neither PRIMARY nor BACKUP)."""
        from datetime import datetime

        from obskit.failover import FailoverCoordinator, FailoverState

        coordinator = FailoverCoordinator("test-failing-over")
        coordinator.register_primary("primary")
        coordinator.register_backup("backup")

        # Set to FAILING_OVER state (not PRIMARY, not BACKUP)
        coordinator._state = FailoverState.FAILING_OVER
        coordinator._failover_time = datetime.now(UTC)

        coordinator._evaluate_state()  # Should hit 325->335 (neither if nor elif matches)
        # failover_time is set so line 335 should also execute

    def test_evaluate_state_backup_recovery_below_threshold(self):
        """Line 329->335: auto_recover True, primary healthy, but recovery_successes < threshold."""
        from obskit.failover import FailoverCoordinator, FailoverState

        coordinator = FailoverCoordinator(
            "test-below-recovery-thresh",
            auto_recover=True,
            recovery_threshold=5,  # High threshold
        )
        coordinator.register_primary("primary")
        coordinator.register_backup("backup")

        coordinator._state = FailoverState.BACKUP
        coordinator._primary.is_healthy = True
        coordinator._recovery_successes = 0  # Below threshold 5

        coordinator._evaluate_state()
        # recovery_successes incremented but still < threshold -> _do_recovery not called
        assert coordinator._state == FailoverState.BACKUP
        assert coordinator._recovery_successes == 1

    def test_do_recovery_without_failover_time(self):
        """Line 382->390: _do_recovery when _failover_time is None."""
        from obskit.failover import FailoverCoordinator, FailoverState

        coordinator = FailoverCoordinator("test-recovery-no-time")
        coordinator.register_primary("primary")
        coordinator.register_backup("backup")

        # Set up BACKUP state WITHOUT failover_time
        coordinator._state = FailoverState.BACKUP
        coordinator._failover_time = None  # No failover time

        coordinator._do_recovery()

        assert coordinator._state == FailoverState.PRIMARY
        assert coordinator._failover_time is None  # Stays None


class TestCombinedMoreBranches:
    """Cover remaining combined.py branch misses."""

    @pytest.mark.asyncio
    async def test_execute_circuit_open_without_callback(self):
        """Line 202->204: circuit open but no on_circuit_open callback."""
        import obskit
        from obskit.resilience.circuit_breaker import CircuitBreaker, CircuitOpenError
        from obskit.resilience.combined import ResilientExecutor

        obskit.CircuitOpenError = CircuitOpenError

        # Use real circuit breaker in OPEN state
        cb = CircuitBreaker(name="test-open-no-cb", failure_threshold=1, recovery_timeout=100.0)
        try:
            with cb:  # NOSONAR
                raise ValueError("force open")
        except ValueError:
            pass  # NOSONAR

        executor = ResilientExecutor(
            circuit_breaker=cb,
            max_retries=1,
            base_delay=0.001,
            on_circuit_open=None,  # No callback -> line 202 is False -> 204
        )

        with pytest.raises(CircuitOpenError):
            await executor.execute(lambda: "result")

    @pytest.mark.asyncio
    async def test_execute_async_empty_loop_raises_runtime(self):
        """Lines 256-258: empty loop (max_retries=0) -> raise RuntimeError."""
        from obskit.resilience.combined import ResilientExecutor

        executor = ResilientExecutor(
            circuit_breaker=None,
            max_retries=0,  # range(1, 1) = empty
            base_delay=0.001,
        )

        with pytest.raises(RuntimeError, match="completed without returning"):
            await executor.execute(lambda: "result")

    def test_execute_sync_empty_loop_raises_runtime(self):
        """Lines 318-320: empty loop (max_retries=0) -> raise RuntimeError."""
        from obskit.resilience.combined import ResilientExecutor

        executor = ResilientExecutor(
            circuit_breaker=None,
            max_retries=0,  # range(1, 1) = empty
            base_delay=0.001,
        )

        with pytest.raises(RuntimeError, match="completed without returning"):
            executor.execute_sync(lambda: "result")
