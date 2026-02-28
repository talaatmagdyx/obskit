"""
Tests for obskit.circuit_dashboard module.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from obskit.circuit_dashboard import (
    CircuitBreakerDashboard,
    CircuitBreakerStatus,
    CircuitState,
    DashboardData,
    get_all_circuit_states,
    get_circuit_dashboard,
    register_circuit_breaker,
)


# =============================================================================
# CircuitState Tests
# =============================================================================


class TestCircuitState:
    def test_closed_value(self):
        assert CircuitState.CLOSED.value == "closed"

    def test_open_value(self):
        assert CircuitState.OPEN.value == "open"

    def test_half_open_value(self):
        assert CircuitState.HALF_OPEN.value == "half_open"


# =============================================================================
# CircuitBreakerStatus Tests
# =============================================================================


class TestCircuitBreakerStatus:
    def _make_status(self, state=CircuitState.CLOSED, **kwargs):
        defaults = dict(
            name="test",
            dependency_type="database",
            state=state,
            failure_count=0,
            success_count=0,
            failure_threshold=5,
            recovery_timeout=30.0,
        )
        defaults.update(kwargs)
        return CircuitBreakerStatus(**defaults)

    def test_to_dict_basic(self):
        status = self._make_status()
        d = status.to_dict()
        assert d["name"] == "test"
        assert d["state"] == "closed"
        assert d["failure_count"] == 0
        assert d["is_healthy"] is True

    def test_to_dict_with_timestamps(self):
        now = datetime.utcnow()
        status = self._make_status(last_failure_time=now, last_state_change=now)
        d = status.to_dict()
        assert d["last_failure_time"] is not None
        assert d["last_state_change"] is not None

    def test_to_dict_without_timestamps(self):
        status = self._make_status()
        d = status.to_dict()
        assert d["last_failure_time"] is None
        assert d["last_state_change"] is None

    def test_is_healthy_when_closed(self):
        status = self._make_status(state=CircuitState.CLOSED, is_healthy=True)
        assert status.is_healthy is True

    def test_is_not_healthy_when_open(self):
        status = self._make_status(state=CircuitState.OPEN, is_healthy=False)
        assert status.is_healthy is False

    def test_time_until_recovery(self):
        status = self._make_status(time_until_recovery=15.0)
        assert status.to_dict()["time_until_recovery"] == 15.0


# =============================================================================
# DashboardData Tests
# =============================================================================


class TestDashboardData:
    def _make_data(self, breakers=None):
        breakers = breakers or []
        return DashboardData(
            breakers=breakers,
            total_breakers=len(breakers),
            healthy_breakers=sum(1 for b in breakers if b.is_healthy),
            open_breakers=sum(1 for b in breakers if b.state == CircuitState.OPEN),
            half_open_breakers=sum(1 for b in breakers if b.state == CircuitState.HALF_OPEN),
            overall_health=all(b.is_healthy for b in breakers) if breakers else True,
        )

    def test_to_dict_empty(self):
        data = self._make_data()
        d = data.to_dict()
        assert d["total_breakers"] == 0
        assert d["healthy_breakers"] == 0
        assert d["overall_health"] is True
        assert isinstance(d["timestamp"], str)

    def test_to_dict_with_breakers(self):
        status = CircuitBreakerStatus(
            name="db",
            dependency_type="database",
            state=CircuitState.CLOSED,
            failure_count=0,
            success_count=5,
            failure_threshold=5,
            recovery_timeout=30.0,
            is_healthy=True,
        )
        data = self._make_data([status])
        d = data.to_dict()
        assert d["total_breakers"] == 1
        assert len(d["breakers"]) == 1
        assert d["breakers"][0]["name"] == "db"


# =============================================================================
# CircuitBreakerDashboard Tests
# =============================================================================


class TestCircuitBreakerDashboard:
    def setup_method(self):
        self.dashboard = CircuitBreakerDashboard()

    def _make_mock_breaker(
        self,
        state_value="closed",
        failure_count=0,
        success_count=0,
        failure_threshold=5,
        recovery_timeout=30.0,
    ):
        breaker = MagicMock()
        mock_state = MagicMock()
        mock_state.value = state_value
        breaker.state = mock_state
        breaker.failure_count = failure_count
        breaker.success_count = success_count
        breaker.failure_threshold = failure_threshold
        breaker.recovery_timeout = recovery_timeout
        breaker.last_failure_time = None
        breaker.opened_at = None
        return breaker

    def test_register_breaker(self):
        breaker = self._make_mock_breaker()
        self.dashboard.register_breaker("db", breaker, "database")
        assert "db" in self.dashboard._breakers
        assert self.dashboard._dependency_types["db"] == "database"

    def test_register_breaker_default_type(self):
        breaker = self._make_mock_breaker()
        self.dashboard.register_breaker("service", breaker)
        assert self.dashboard._dependency_types["service"] == "external"

    def test_unregister_breaker(self):
        breaker = self._make_mock_breaker()
        self.dashboard.register_breaker("db", breaker)
        self.dashboard.unregister_breaker("db")
        assert "db" not in self.dashboard._breakers

    def test_unregister_nonexistent_breaker(self):
        # Should not raise
        self.dashboard.unregister_breaker("nonexistent")

    def test_get_breaker_status_returns_none_for_unknown(self):
        result = self.dashboard.get_breaker_status("nonexistent")
        assert result is None

    def test_get_breaker_status_closed(self):
        breaker = self._make_mock_breaker(state_value="closed")
        self.dashboard.register_breaker("db", breaker, "database")
        status = self.dashboard.get_breaker_status("db")
        assert status is not None
        assert status.state == CircuitState.CLOSED
        assert status.is_healthy is True

    def test_get_breaker_status_open(self):
        breaker = self._make_mock_breaker(state_value="open")
        self.dashboard.register_breaker("db", breaker, "database")
        status = self.dashboard.get_breaker_status("db")
        assert status.state == CircuitState.OPEN
        assert status.is_healthy is False

    def test_get_breaker_status_half_open(self):
        breaker = self._make_mock_breaker(state_value="half_open")
        self.dashboard.register_breaker("db", breaker, "database")
        status = self.dashboard.get_breaker_status("db")
        assert status.state == CircuitState.HALF_OPEN

    def test_get_all_states_empty(self):
        data = self.dashboard.get_all_states()
        assert data.total_breakers == 0
        assert data.overall_health is True

    def test_get_all_states_with_closed_breakers(self):
        b1 = self._make_mock_breaker(state_value="closed")
        b2 = self._make_mock_breaker(state_value="closed")
        self.dashboard.register_breaker("db1", b1)
        self.dashboard.register_breaker("db2", b2)
        data = self.dashboard.get_all_states()
        assert data.total_breakers == 2
        assert data.healthy_breakers == 2
        assert data.overall_health is True

    def test_get_all_states_with_open_breaker(self):
        b1 = self._make_mock_breaker(state_value="closed")
        b2 = self._make_mock_breaker(state_value="open")
        self.dashboard.register_breaker("db1", b1)
        self.dashboard.register_breaker("db2", b2)
        data = self.dashboard.get_all_states()
        assert data.open_breakers == 1
        assert data.overall_health is False

    def test_is_all_healthy_true(self):
        breaker = self._make_mock_breaker(state_value="closed")
        self.dashboard.register_breaker("db", breaker)
        assert self.dashboard.is_all_healthy() is True

    def test_is_all_healthy_false(self):
        breaker = self._make_mock_breaker(state_value="open")
        self.dashboard.register_breaker("db", breaker)
        assert self.dashboard.is_all_healthy() is False

    def test_get_open_breakers(self):
        b1 = self._make_mock_breaker(state_value="open")
        b2 = self._make_mock_breaker(state_value="closed")
        self.dashboard.register_breaker("open_db", b1)
        self.dashboard.register_breaker("closed_db", b2)
        open_list = self.dashboard.get_open_breakers()
        assert "open_db" in open_list
        assert "closed_db" not in open_list

    def test_extract_status_with_private_state_attr(self):
        """Test extraction when breaker uses _state attribute."""
        breaker = MagicMock(spec=[])
        breaker._state = "OPEN STATE"
        breaker._failure_count = 3
        breaker._success_count = 0
        breaker._failure_threshold = 5
        breaker._recovery_timeout = 30.0
        breaker._last_failure_time = None
        breaker._opened_at = None
        status = self.dashboard._extract_status("test", breaker, "database")
        assert status.state == CircuitState.OPEN

    def test_extract_status_half_open_state_str(self):
        """Test extraction when _state string contains 'half'."""
        breaker = MagicMock(spec=[])
        breaker._state = "half open"
        breaker._failure_count = 1
        breaker._success_count = 0
        breaker._failure_threshold = 5
        breaker._recovery_timeout = 30.0
        breaker._last_failure_time = None
        breaker._opened_at = None
        status = self.dashboard._extract_status("test", breaker, "database")
        assert status.state == CircuitState.HALF_OPEN

    def test_extract_status_with_open_state_and_timestamp(self):
        """Test time_until_recovery calculation for open circuit."""
        breaker = MagicMock()
        mock_state = MagicMock()
        mock_state.value = "open"
        breaker.state = mock_state
        breaker.failure_count = 5
        breaker.success_count = 0
        breaker.failure_threshold = 5
        breaker.recovery_timeout = 30.0
        breaker.last_failure_time = None
        breaker.opened_at = datetime.utcnow()
        status = self.dashboard._extract_status("test", breaker, "database")
        assert status.time_until_recovery >= 0.0

    def test_half_open_count_in_dashboard_data(self):
        breaker = self._make_mock_breaker(state_value="half_open")
        self.dashboard.register_breaker("db", breaker)
        data = self.dashboard.get_all_states()
        assert data.half_open_breakers == 1


# =============================================================================
# Singleton and Global Functions Tests
# =============================================================================


class TestGlobalFunctions:
    def test_get_circuit_dashboard_returns_instance(self):
        dashboard = get_circuit_dashboard()
        assert isinstance(dashboard, CircuitBreakerDashboard)

    def test_get_circuit_dashboard_singleton(self):
        d1 = get_circuit_dashboard()
        d2 = get_circuit_dashboard()
        assert d1 is d2

    def test_register_circuit_breaker(self):
        breaker = MagicMock()
        mock_state = MagicMock()
        mock_state.value = "closed"
        breaker.state = mock_state
        breaker.failure_count = 0
        breaker.success_count = 0
        breaker.failure_threshold = 5
        breaker.recovery_timeout = 30.0
        breaker.last_failure_time = None
        breaker.opened_at = None
        register_circuit_breaker("global_test_breaker", breaker, "api")
        dashboard = get_circuit_dashboard()
        assert "global_test_breaker" in dashboard._breakers

    def test_get_all_circuit_states(self):
        data = get_all_circuit_states()
        assert isinstance(data, DashboardData)
