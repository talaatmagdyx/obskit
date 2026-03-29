"""Additional coverage tests for obskit-resilience."""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


class TestCircuitDashboardCoverage:
    """Cover missing lines in circuit_dashboard.py."""

    def _make_mock_breaker(self, state_str="open"):
        """Create a properly configured mock breaker."""
        mock_breaker = MagicMock()
        mock_breaker.state = state_str
        mock_breaker.failure_count = 5
        mock_breaker.success_count = 10
        mock_breaker.recovery_timeout = 30.0
        mock_breaker.opened_at = None
        mock_breaker.last_failure_time = None
        return mock_breaker

    def test_extract_status_with_string_state(self):
        """Line 226: state_val is a string, get CircuitState from string."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard, CircuitState

        dashboard = CircuitBreakerDashboard()
        mock_breaker = self._make_mock_breaker("open")

        status = dashboard._extract_status("test-string-state", mock_breaker, "external")
        assert status.state == CircuitState.OPEN

    def test_extract_status_with_no_state_attr_closed(self):
        """Line 236: _state attribute resolves to CLOSED."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard, CircuitState

        dashboard = CircuitBreakerDashboard()

        mock_breaker = MagicMock()
        del mock_breaker.state  # Remove state so hasattr(breaker, state) is False
        mock_breaker._state = "closed"  # no open or half -> CLOSED
        mock_breaker.failure_count = 0
        mock_breaker.success_count = 0
        mock_breaker.recovery_timeout = 30.0
        mock_breaker.opened_at = None
        mock_breaker.last_failure_time = None

        status = dashboard._extract_status("test-closed-state", mock_breaker, "external")
        assert status.state == CircuitState.CLOSED


class TestDegradationCoverage:
    """Cover missing lines in degradation.py."""

    def test_degradation_state_to_dict(self):
        """Line 109: DegradationState.to_dict() returns dict."""
        from obskit.degradation import DegradationLevel, DegradationState

        state = DegradationState(
            level=DegradationLevel.MEDIUM,
            active_features=["feat1"],
            degraded_features=["feat2"],
            reason="test",
        )
        result = state.to_dict()
        assert result["level"] == DegradationLevel.MEDIUM.value
        assert result["level_name"] == DegradationLevel.MEDIUM.name
        assert result["active_features"] == ["feat1"]
        assert result["reason"] == "test"

    def test_execute_with_fallback_no_fallback_returns_none(self):
        """Line 263: execute_with_fallback returns None when no fallback."""
        from obskit.degradation import DegradationManager

        mgr = DegradationManager("test-fallback-none")
        mgr.register_feature("my_feat")
        # Use degrade_feature (the correct method) to degrade the feature
        mgr.degrade_feature("my_feat", reason="test")

        # Call without any fallback registered
        result = mgr.execute_with_fallback(
            "my_feat",
            primary=lambda: "primary_value",
            fallback=None,
        )
        assert result is None

    def test_set_level_with_high_int_uses_critical(self):
        """Lines 278-283: integer level > max enum value uses DegradationLevel.CRITICAL."""
        from obskit.degradation import DegradationLevel, DegradationManager

        mgr = DegradationManager("test-int-level")
        mgr.set_level(9999)  # Should set to CRITICAL (for-else branch)

        state = mgr.get_state()
        assert state.level == DegradationLevel.CRITICAL

    def test_evaluate_metrics_with_auto_degrade_false(self):
        """Line 373: evaluate_metrics returns early when auto_degrade is False."""
        from obskit.degradation import DegradationManager

        mgr = DegradationManager("test-no-auto-degrade", auto_degrade=False)
        mgr.evaluate_metrics(error_rate=0.9)

    def test_evaluate_metrics_medium_score(self):
        """Lines 403-404: score >= 25 but < 50 sets MEDIUM level."""
        from obskit.degradation import DegradationLevel, DegradationManager

        mgr = DegradationManager("test-medium-score", auto_degrade=True)
        # error_rate=0.15 -> score = min(50, (0.15/0.1)*25) = int(37.5) = 37 -> MEDIUM
        mgr.evaluate_metrics(error_rate=0.15)

        state = mgr.get_state()
        assert state.level == DegradationLevel.MEDIUM

    def test_evaluate_metrics_low_score(self):
        """Lines 405-406: score > 0 but < 25 sets LOW level."""
        from obskit.degradation import DegradationLevel, DegradationManager

        mgr = DegradationManager("test-low-score", auto_degrade=True)
        # cpu_percent=82 -> score = min(30, (82-80)/2) = 1.0 -> int(1) = 1 -> LOW
        mgr.evaluate_metrics(cpu_percent=82)

        state = mgr.get_state()
        assert state.level == DegradationLevel.LOW

    def test_evaluate_metrics_zero_score(self):
        """Lines 407-408: score == 0 sets NONE level."""
        from obskit.degradation import DegradationLevel, DegradationManager

        mgr = DegradationManager("test-zero-score", auto_degrade=True)
        mgr.evaluate_metrics(error_rate=0.0)

        state = mgr.get_state()
        assert state.level == DegradationLevel.NONE

    def test_get_all_features(self):
        """Lines 429-430: get_all_features returns list of features."""
        from obskit.degradation import DegradationManager

        mgr = DegradationManager("test-all-features")
        mgr.register_feature("feature1")
        mgr.register_feature("feature2")

        features = mgr.get_all_features()
        assert len(features) == 2
        assert any(f.name == "feature1" for f in features)


class TestFailoverCoverage:
    """Cover missing lines in failover.py."""

    def test_failover_event_to_dict(self):
        """Line 116: FailoverEvent.to_dict() returns dict."""
        from obskit.failover import FailoverEvent

        event = FailoverEvent(
            coordinator="coord-1",
            from_endpoint="primary",
            to_endpoint="backup",
            reason="test",
        )
        result = event.to_dict()
        assert result["coordinator"] == "coord-1"
        assert result["from_endpoint"] == "primary"
        assert result["to_endpoint"] == "backup"

    def test_check_health_primary_health_check_exception(self):
        """Lines 279-281: primary health_check raises exception, marked unhealthy."""
        from obskit.failover import FailoverCoordinator

        def failing_health():
            raise ConnectionError("connection failed")

        # failure_threshold=1 so one failure marks unhealthy immediately
        coordinator = FailoverCoordinator("test-primary-fail-2", failure_threshold=1)
        coordinator.register_primary("primary", health_check=failing_health)
        coordinator.register_backup("backup")

        coordinator.check_health()  # Should catch exception and mark unhealthy

        assert not coordinator._primary.is_healthy

    def test_check_health_backup_health_check_exception(self):
        """Lines 288-290: backup health_check raises exception, marked unhealthy."""
        from obskit.failover import FailoverCoordinator

        def ok_health():
            return True

        def failing_backup_health():
            raise ConnectionError("backup failed")

        # failure_threshold=1 so one failure marks unhealthy immediately
        coordinator = FailoverCoordinator("test-backup-fail-2", failure_threshold=1)
        coordinator.register_primary("primary", health_check=ok_health)
        coordinator.register_backup("backup", health_check=failing_backup_health)

        coordinator.check_health()

        assert not coordinator._backup.is_healthy

    def test_evaluate_state_no_primary(self):
        """Line 316: _evaluate_state returns early when no primary."""
        from obskit.failover import FailoverCoordinator

        coordinator = FailoverCoordinator("test-no-primary")
        coordinator._evaluate_state()  # Should return early without error

    def test_evaluate_state_backup_auto_recover_not_healthy(self):
        """Line 332: recovery_successes reset to 0 when primary not healthy."""
        from obskit.failover import FailoverCoordinator, FailoverState

        coordinator = FailoverCoordinator("test-backup-no-recover", auto_recover=True)
        coordinator.register_primary("primary")
        coordinator.register_backup("backup")

        coordinator._state = FailoverState.BACKUP
        coordinator._primary.is_healthy = False
        coordinator._recovery_successes = 5

        coordinator._evaluate_state()

        assert coordinator._recovery_successes == 0

    def test_start_monitoring_when_thread_already_alive(self):
        """Lines 437-438: start_monitoring returns early if thread is alive."""
        from obskit.failover import FailoverCoordinator

        coordinator = FailoverCoordinator("test-monitoring-alive")

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        coordinator._check_thread = mock_thread

        coordinator.start_monitoring()  # Should return early

        mock_thread.start.assert_not_called()

    def test_start_and_stop_monitoring(self):
        """Lines 440-444, 448-452: start and stop monitoring threads."""
        from obskit.failover import FailoverCoordinator

        coordinator = FailoverCoordinator(
            "test-monitoring-full",
            check_interval_seconds=0.01,
        )
        coordinator.register_primary("primary", health_check=lambda: True)

        coordinator.start_monitoring()
        time.sleep(0.05)
        coordinator.stop_monitoring()

        assert not coordinator._check_thread.is_alive()

    def test_monitoring_loop_exception_caught(self):
        """Lines 459-460: exception in monitoring loop is caught."""
        from obskit.failover import FailoverCoordinator

        coordinator = FailoverCoordinator(
            "test-monitoring-exception",
            check_interval_seconds=0.01,
        )

        call_count = [0]

        def failing_check_health():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("monitoring error")

        coordinator.check_health = failing_check_health
        coordinator.start_monitoring()
        time.sleep(0.05)
        coordinator.stop_monitoring()

        assert call_count[0] >= 1

    def test_get_failover_coordinator_inner_lock_branch(self):
        """Line 499->502: inner lock branch of get_failover_coordinator."""
        import obskit.failover as module

        unique_name = "__inner_lock_failover__"
        module._coordinators.pop(unique_name, None)

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

        from obskit.failover import FailoverCoordinator

        existing = FailoverCoordinator(unique_name)

        fake_dict = _FakeDict()
        fake_dict._target_key = unique_name
        fake_dict[unique_name] = existing

        original = module._coordinators
        module._coordinators = fake_dict
        try:
            result = module.get_failover_coordinator(unique_name)
            assert result is existing
        finally:
            module._coordinators = original
            module._coordinators.pop(unique_name, None)


class TestLockingCoverage:
    """Cover missing lines in locking.py."""

    def test_campaign_loop_exception_caught(self):
        """Lines 466-467: exception in campaign_loop is caught."""
        mock_redis = MagicMock()
        mock_redis.set.return_value = None
        mock_redis.get.return_value = None

        from obskit.locking import LeaderElection

        election = LeaderElection(
            election_name="test-campaign-exception",
            redis_client=mock_redis,
            renewal_interval=0.01,
        )

        call_count = [0]
        original_try = election.try_become_leader

        def failing_try_become_leader():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("election error")
            return original_try()

        election.try_become_leader = failing_try_become_leader
        election.start_campaign()
        time.sleep(0.05)
        election.stop_campaign()

        assert call_count[0] >= 1


class TestCircuitBreakerSyncOpenStateBranches:
    """Cover the elif->exit branches in _record_success_sync/_record_failure_sync."""

    def test_record_success_sync_when_open(self):
        """Line 743->exit: elif CLOSED not taken when state is OPEN."""
        from obskit.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_open_success", failure_threshold=5)
        cb._state = CircuitState.OPEN  # force OPEN state
        original_count = cb._failure_count
        cb._record_success_sync()  # neither HALF_OPEN nor CLOSED branch taken
        assert cb._state == CircuitState.OPEN  # unchanged
        assert cb._failure_count == original_count  # unchanged

    def test_record_failure_sync_when_open(self):
        """Line 773->exit: elif CLOSED not taken when state is OPEN."""
        from obskit.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_open_failure", failure_threshold=100)
        cb._state = CircuitState.OPEN  # force OPEN state
        cb._record_failure_sync(Exception("test"))  # neither HALF_OPEN nor CLOSED branch
        assert (
            cb._state == CircuitState.OPEN
        )  # unchanged (failure_count incremented but no state change)


class TestCircuitDashboardDoubleLock:
    """Cover get_circuit_dashboard inner double-check locking branch (361->364)."""

    def test_get_circuit_dashboard_inner_lock_already_set(self):
        """Simulate race: _dashboard gets set between outer if-None check and lock acquire."""
        import obskit.circuit_dashboard as cd
        from obskit.circuit_dashboard import CircuitBreakerDashboard

        saved = cd._dashboard
        saved_lock = cd._dashboard_lock
        try:
            cd._dashboard = None  # start with None

            sentinel = CircuitBreakerDashboard()

            class _RaceLock:
                def __enter__(self):
                    # another thread beat us — set _dashboard before we check inside lock
                    cd._dashboard = sentinel
                    return self

                def __exit__(self, *args):
                    pass  # NOSONAR

            cd._dashboard_lock = _RaceLock()
            result = cd.get_circuit_dashboard()
            # inner if _dashboard is None: is False → skips creation → returns sentinel
            assert result is sentinel
        finally:
            cd._dashboard = saved
            cd._dashboard_lock = saved_lock
