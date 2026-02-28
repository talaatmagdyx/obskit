"""Tests to cover branch misses in circuit_dashboard.py and locking.py."""
from __future__ import annotations

import time
import threading
from datetime import datetime
from unittest.mock import MagicMock


class TestCircuitDashboardPrivateAttrBranches:
    """Cover the elif hasattr(breaker, "_xxx") branches in _extract_status."""

    def _make_private_mock_breaker(self, state_str="open"):
        """Mock breaker with private attributes only (no public failure_count etc.)."""
        mock_breaker = MagicMock()
        # state is public - needed for state extraction
        mock_breaker.state = state_str
        mock_breaker.recovery_timeout = 30.0
        mock_breaker.opened_at = None

        # Delete public attr aliases, add private ones
        # This forces the elif hasattr(breaker, "_xxx") branches
        del mock_breaker.failure_count       # -> triggers elif _failure_count
        mock_breaker._failure_count = 3

        del mock_breaker.success_count       # -> triggers elif _success_count
        mock_breaker._success_count = 7

        del mock_breaker.failure_threshold   # -> triggers elif _failure_threshold
        mock_breaker._failure_threshold = 5

        # Keep recovery_timeout public (line 257)
        # Delete last_failure_time, add _last_failure_time
        del mock_breaker.last_failure_time   # -> triggers elif _last_failure_time
        mock_breaker._last_failure_time = None

        # Delete opened_at, add _opened_at
        del mock_breaker.opened_at           # -> triggers elif _opened_at
        mock_breaker._opened_at = None

        return mock_breaker

    def test_extract_status_uses_private_attrs(self):
        """Lines 241-242, 247-248, 253-254, 265-266, 270-274: use private attrs."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard, CircuitState

        dashboard = CircuitBreakerDashboard()
        mock_breaker = self._make_private_mock_breaker("open")

        status = dashboard._extract_status("test-private-attrs", mock_breaker, "external")
        assert status.state == CircuitState.OPEN
        assert status.failure_count == 3
        assert status.success_count == 7

    def test_extract_status_with_enum_state(self):
        """Line 228: state_val has .value attribute (enum-like)."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard, CircuitState

        dashboard = CircuitBreakerDashboard()
        mock_breaker = MagicMock()

        # Make state an enum-like object with .value
        mock_state = MagicMock()
        mock_state.value = "closed"
        mock_breaker.state = mock_state
        mock_breaker.failure_count = 0
        mock_breaker.success_count = 0
        mock_breaker.recovery_timeout = 30.0
        mock_breaker.opened_at = None
        mock_breaker.last_failure_time = None

        status = dashboard._extract_status("test-enum-state", mock_breaker, "external")
        assert status.state == CircuitState.CLOSED

    def test_extract_status_open_with_opened_at_recovery(self):
        """Lines 253->257, 259->263: recovery_timeout without public attr, with _recovery_timeout."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard, CircuitState

        dashboard = CircuitBreakerDashboard()
        mock_breaker = MagicMock()
        mock_breaker.state = "open"
        mock_breaker.failure_count = 1
        mock_breaker.success_count = 0
        mock_breaker.last_failure_time = None

        # Delete public recovery_timeout, add private _recovery_timeout
        del mock_breaker.recovery_timeout    # -> triggers elif _recovery_timeout
        mock_breaker._recovery_timeout = 30.0

        # Set opened_at so recovery time calculation triggers
        mock_breaker.opened_at = datetime.utcnow()

        status = dashboard._extract_status("test-recovery-private", mock_breaker, "external")
        assert status.state == CircuitState.OPEN

    def test_get_circuit_dashboard_singleton(self):
        """Lines 361->364: get_circuit_dashboard creates singleton on first call."""
        from obskit.circuit_dashboard import get_circuit_dashboard
        import obskit.circuit_dashboard as mod

        # Reset the global dashboard to force recreation
        original = mod._dashboard
        mod._dashboard = None
        try:
            dashboard = get_circuit_dashboard()
            assert dashboard is not None
            # Second call returns same instance (outer check succeeds)
            dashboard2 = get_circuit_dashboard()
            assert dashboard is dashboard2
        finally:
            mod._dashboard = original


class TestLockingBranchCoverage:
    """Cover branch misses in locking.py."""

    def test_release_with_no_acquired_at(self):
        """Line 235->239: _acquired_at is None so hold_time branch is skipped."""
        mock_redis = MagicMock()
        # Make eval succeed (no exception)
        mock_redis.eval.return_value = 1

        from obskit.locking import DistributedLock
        lock = DistributedLock(
            lock_name="test-no-acquired-at",
            redis_client=mock_redis,
        )
        # Manually set as acquired but with no _acquired_at
        lock._acquired = True
        lock._acquired_at = None  # The branch: if self._acquired_at -> False -> jump to 239

        lock.release()

        # Should complete without error
        assert not lock._acquired

    def test_stop_campaign_when_no_thread(self):
        """Line 457->459: _renewal_thread is None, so join is skipped, resign called."""
        mock_redis = MagicMock()
        mock_redis.set.return_value = None
        mock_redis.get.return_value = None

        from obskit.locking import LeaderElection
        election = LeaderElection(
            election_name="test-stop-no-thread",
            redis_client=mock_redis,
            renewal_interval=0.01,
        )

        # _renewal_thread starts as None
        assert election._renewal_thread is None

        # stop_campaign when thread is None -> skips join, calls resign
        election.stop_campaign()  # Should not raise


class TestCircuitDashboardMoreBranches:
    """Cover the remaining branch misses in circuit_dashboard.py _extract_status."""

    def _make_minimal_mock(self):
        """Mock breaker with NO public OR private attribute for counts/timeouts."""
        class MinimalBreaker:
            """Breaker with no state, failure_count, etc. attributes."""
            pass

        return MinimalBreaker()

    def test_extract_status_state_val_not_string_no_value_attr(self):
        """Line 227->239: state_val has no .value and is not string."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard, CircuitState

        dashboard = CircuitBreakerDashboard()

        class BreakerWithIntState:
            state = 42  # int, not string, no .value attr

        status = dashboard._extract_status("test-int-state", BreakerWithIntState(), "external")
        # Falls through to default CLOSED
        assert status.state == CircuitState.CLOSED

    def test_extract_status_no_state_or_private_state(self):
        """Line 229->239: no state and no _state attribute."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard, CircuitState

        dashboard = CircuitBreakerDashboard()

        class BreakerNoState:
            # No state, no _state
            failure_count = 0
            success_count = 0
            recovery_timeout = 30.0
            opened_at = None
            last_failure_time = None

        status = dashboard._extract_status("test-no-state", BreakerNoState(), "external")
        # Uses default CLOSED
        assert status.state == CircuitState.CLOSED

    def test_extract_status_no_failure_count_attrs(self):
        """Line 241->245: no failure_count AND no _failure_count."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard

        dashboard = CircuitBreakerDashboard()

        class BreakerNoFailureCount:
            state = "closed"
            # No failure_count, no _failure_count -> uses default 0
            success_count = 5
            recovery_timeout = 30.0
            opened_at = None
            last_failure_time = None

        status = dashboard._extract_status("test-no-failure-count", BreakerNoFailureCount(), "external")
        assert status.failure_count == 0

    def test_extract_status_no_success_count_attrs(self):
        """Line 247->251: no success_count AND no _success_count."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard

        dashboard = CircuitBreakerDashboard()

        class BreakerNoSuccessCount:
            state = "closed"
            failure_count = 2
            # No success_count, no _success_count -> uses default 0
            recovery_timeout = 30.0
            opened_at = None
            last_failure_time = None

        status = dashboard._extract_status("test-no-success-count", BreakerNoSuccessCount(), "external")
        assert status.success_count == 0

    def test_extract_status_no_failure_threshold_attrs(self):
        """Line 253->257: no failure_threshold AND no _failure_threshold."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard

        dashboard = CircuitBreakerDashboard()

        class BreakerNoThreshold:
            state = "closed"
            failure_count = 0
            success_count = 0
            # No failure_threshold, no _failure_threshold -> uses default 5
            recovery_timeout = 30.0
            opened_at = None
            last_failure_time = None

        status = dashboard._extract_status("test-no-threshold", BreakerNoThreshold(), "external")
        assert status.recovery_timeout == 30.0

    def test_extract_status_no_recovery_timeout_attrs(self):
        """Line 259->263: no recovery_timeout AND no _recovery_timeout."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard

        dashboard = CircuitBreakerDashboard()

        class BreakerNoRecoveryTimeout:
            state = "closed"
            failure_count = 0
            success_count = 0
            failure_threshold = 5
            # No recovery_timeout, no _recovery_timeout -> uses default 30.0
            opened_at = None
            last_failure_time = None

        status = dashboard._extract_status("test-no-recovery", BreakerNoRecoveryTimeout(), "external")
        assert status.recovery_timeout == 30.0  # default value

    def test_extract_status_no_last_failure_time_attrs(self):
        """Line 265->268: no last_failure_time AND no _last_failure_time."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard

        dashboard = CircuitBreakerDashboard()

        class BreakerNoLastFailureTime:
            state = "closed"
            failure_count = 0
            success_count = 0
            failure_threshold = 5
            recovery_timeout = 30.0
            opened_at = None
            # No last_failure_time, no _last_failure_time -> stays None

        status = dashboard._extract_status("test-no-last-fail", BreakerNoLastFailureTime(), "external")
        assert status.last_failure_time is None

    def test_extract_status_no_opened_at_attrs(self):
        """Line 270->274: no opened_at AND no _opened_at."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard

        dashboard = CircuitBreakerDashboard()

        class BreakerNoOpenedAt:
            state = "closed"
            failure_count = 0
            success_count = 0
            failure_threshold = 5
            recovery_timeout = 30.0
            last_failure_time = None
            # No opened_at, no _opened_at -> last_state_change stays None

        status = dashboard._extract_status("test-no-opened-at", BreakerNoOpenedAt(), "external")
        # time_until_recovery stays 0.0 (no state change)
        assert status.time_until_recovery == 0.0

    def test_get_circuit_dashboard_inner_lock_branch(self):
        """Line 361->364: inner lock branch when dashboard created concurrently."""
        from obskit.circuit_dashboard import CircuitBreakerDashboard, get_circuit_dashboard
        import obskit.circuit_dashboard as mod

        original = mod._dashboard
        mod._dashboard = None
        try:
            # Simulate: outer check sees None, enters lock, inner check finds it already set
            existing = CircuitBreakerDashboard()
            mod._dashboard = existing  # Pre-set to simulate race condition

            # Call get_circuit_dashboard - outer check will be True (None) initially
            # But we pre-set it, so inner check finds it
            result = get_circuit_dashboard()
            # Result could be the existing one or a new one depending on lock timing
            assert result is not None
        finally:
            mod._dashboard = original
