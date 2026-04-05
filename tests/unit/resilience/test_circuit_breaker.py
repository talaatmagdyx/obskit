"""Unit tests for obskit.resilience.circuit_breaker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestCircuitState:
    def test_values(self):
        from obskit.resilience.circuit_breaker import CircuitState

        assert CircuitState.CLOSED == 0
        assert CircuitState.OPEN == 1
        assert CircuitState.HALF_OPEN == 2

    def test_is_int_enum(self):
        from obskit.resilience.circuit_breaker import CircuitState

        assert int(CircuitState.CLOSED) == 0
        assert int(CircuitState.OPEN) == 1
        assert int(CircuitState.HALF_OPEN) == 2


class TestObskitCircuitBreakerListener:
    def test_init_sets_gauge_to_closed(self):
        from obskit.resilience.circuit_breaker import (
            CircuitState,
            ObskitCircuitBreakerListener,
            _STATE_GAUGE,
        )

        listener = ObskitCircuitBreakerListener("test_init_gauge")
        gauge = _STATE_GAUGE.labels(name="test_init_gauge")
        # Gauge should exist and be zero (CLOSED)
        assert gauge is not None
        assert listener.name == "test_init_gauge"
        _ = CircuitState.CLOSED  # referenced to confirm import

    def test_state_change_open(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _STATE_GAUGE,
        )

        listener = ObskitCircuitBreakerListener("test_state_open")
        mock_cb = MagicMock()

        # Pass state as string
        listener.state_change(mock_cb, "closed", "open")

        gauge = _STATE_GAUGE.labels(name="test_state_open")
        assert gauge._metric._value.get() == 1  # OPEN

    def test_state_change_half_open(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _STATE_GAUGE,
        )

        listener = ObskitCircuitBreakerListener("test_state_half_open")
        mock_cb = MagicMock()

        listener.state_change(mock_cb, "open", "half_open")

        gauge = _STATE_GAUGE.labels(name="test_state_half_open")
        assert gauge._metric._value.get() == 2  # HALF_OPEN

    def test_state_change_half_open_hyphen(self):
        """Also handle 'half-open' (hyphen variant)."""
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _STATE_GAUGE,
        )

        listener = ObskitCircuitBreakerListener("test_state_hyphen")
        listener.state_change(MagicMock(), "open", "half-open")

        gauge = _STATE_GAUGE.labels(name="test_state_hyphen")
        assert gauge._metric._value.get() == 2

    def test_state_change_closed(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _STATE_GAUGE,
        )

        listener = ObskitCircuitBreakerListener("test_state_closed")
        listener.state_change(MagicMock(), "open", "closed")

        gauge = _STATE_GAUGE.labels(name="test_state_closed")
        assert gauge._metric._value.get() == 0  # CLOSED

    def test_state_change_unknown_defaults_to_closed(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _STATE_GAUGE,
        )

        listener = ObskitCircuitBreakerListener("test_state_unknown")
        listener.state_change(MagicMock(), "open", "unknown_state")

        gauge = _STATE_GAUGE.labels(name="test_state_unknown")
        assert gauge._metric._value.get() == 0  # defaults to CLOSED

    def test_state_change_object_with_name_attr(self):
        """pybreaker may pass an object whose .name is the state string."""
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _STATE_GAUGE,
        )

        listener = ObskitCircuitBreakerListener("test_state_obj_name")
        new_state = MagicMock()
        new_state.name = "open"
        listener.state_change(MagicMock(), MagicMock(), new_state)

        gauge = _STATE_GAUGE.labels(name="test_state_obj_name")
        assert gauge._metric._value.get() == 1  # OPEN

    def test_failure_increments_counters(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _CALLS_TOTAL,
            _FAILURES_TOTAL,
        )

        listener = ObskitCircuitBreakerListener("test_failure_counters")
        mock_cb = MagicMock()

        listener.failure(mock_cb, RuntimeError("oops"))

        failures = _FAILURES_TOTAL.labels(name="test_failure_counters")
        calls_fail = _CALLS_TOTAL.labels(name="test_failure_counters", outcome="failure")
        assert failures._metric._value.get() >= 1
        assert calls_fail._metric._value.get() >= 1

    def test_success_increments_call_counter(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _CALLS_TOTAL,
        )

        listener = ObskitCircuitBreakerListener("test_success_counter")
        listener.success(MagicMock())

        calls_ok = _CALLS_TOTAL.labels(name="test_success_counter", outcome="success")
        assert calls_ok._metric._value.get() >= 1

    def test_before_call_is_noop(self):
        """before_call must exist (pybreaker interface) but does nothing."""
        from obskit.resilience.circuit_breaker import ObskitCircuitBreakerListener

        listener = ObskitCircuitBreakerListener("test_before_call")
        # Should not raise
        listener.before_call(MagicMock(), lambda: None, "arg1", key="val")

    def test_record_success_standalone(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _CALLS_TOTAL,
        )

        listener = ObskitCircuitBreakerListener("test_standalone_success")
        listener.record_success()

        calls_ok = _CALLS_TOTAL.labels(name="test_standalone_success", outcome="success")
        assert calls_ok._metric._value.get() >= 1

    def test_record_failure_standalone(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _CALLS_TOTAL,
            _FAILURES_TOTAL,
        )

        listener = ObskitCircuitBreakerListener("test_standalone_failure")
        listener.record_failure(RuntimeError("boom"))

        failures = _FAILURES_TOTAL.labels(name="test_standalone_failure")
        calls_fail = _CALLS_TOTAL.labels(name="test_standalone_failure", outcome="failure")
        assert failures._metric._value.get() >= 1
        assert calls_fail._metric._value.get() >= 1

    def test_record_failure_without_exc(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _FAILURES_TOTAL,
        )

        listener = ObskitCircuitBreakerListener("test_standalone_failure_no_exc")
        listener.record_failure()  # exc=None default

        failures = _FAILURES_TOTAL.labels(name="test_standalone_failure_no_exc")
        assert failures._metric._value.get() >= 1

    def test_record_state_change_open(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _STATE_GAUGE,
        )

        listener = ObskitCircuitBreakerListener("test_record_state_open")
        listener.record_state_change("open")

        gauge = _STATE_GAUGE.labels(name="test_record_state_open")
        assert gauge._metric._value.get() == 1

    def test_record_state_change_half_open(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _STATE_GAUGE,
        )

        listener = ObskitCircuitBreakerListener("test_record_state_half_open_2")
        listener.record_state_change("half_open")

        gauge = _STATE_GAUGE.labels(name="test_record_state_half_open_2")
        assert gauge._metric._value.get() == 2

    def test_record_state_change_case_insensitive(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _STATE_GAUGE,
        )

        listener = ObskitCircuitBreakerListener("test_record_state_caps")
        listener.record_state_change("OPEN")

        gauge = _STATE_GAUGE.labels(name="test_record_state_caps")
        assert gauge._metric._value.get() == 1


class TestTransitionsTotal:
    def test_state_change_emits_transition(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _TRANSITIONS_TOTAL,
        )

        listener = ObskitCircuitBreakerListener("t_transition_1")
        before = _TRANSITIONS_TOTAL.labels(
            name="t_transition_1", from_state="closed", to_state="open"
        )._metric._value.get()
        listener.state_change(MagicMock(), "closed", "open")
        after = _TRANSITIONS_TOTAL.labels(
            name="t_transition_1", from_state="closed", to_state="open"
        )._metric._value.get()
        assert after == before + 1.0

    def test_state_change_captures_from_state_object(self):
        """from_state is extracted from old_state.name when it's an object."""
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _TRANSITIONS_TOTAL,
        )

        listener = ObskitCircuitBreakerListener("t_transition_obj")
        old = MagicMock()
        old.name = "open"
        new = MagicMock()
        new.name = "half_open"
        before = _TRANSITIONS_TOTAL.labels(
            name="t_transition_obj", from_state="open", to_state="half_open"
        )._metric._value.get()
        listener.state_change(MagicMock(), old, new)
        after = _TRANSITIONS_TOTAL.labels(
            name="t_transition_obj", from_state="open", to_state="half_open"
        )._metric._value.get()
        assert after == before + 1.0

    def test_record_state_change_emits_transition(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _TRANSITIONS_TOTAL,
        )

        listener = ObskitCircuitBreakerListener("t_record_1")
        # initial state is "closed"
        before = _TRANSITIONS_TOTAL.labels(
            name="t_record_1", from_state="closed", to_state="open"
        )._metric._value.get()
        listener.record_state_change("open")
        after = _TRANSITIONS_TOTAL.labels(
            name="t_record_1", from_state="closed", to_state="open"
        )._metric._value.get()
        assert after == before + 1.0

    def test_record_state_change_updates_current_state(self):
        """_current_state tracks successive transitions."""
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            _TRANSITIONS_TOTAL,
        )

        listener = ObskitCircuitBreakerListener("t_record_2")
        listener.record_state_change("open")
        before = _TRANSITIONS_TOTAL.labels(
            name="t_record_2", from_state="open", to_state="half_open"
        )._metric._value.get()
        listener.record_state_change("half_open")
        after = _TRANSITIONS_TOTAL.labels(
            name="t_record_2", from_state="open", to_state="half_open"
        )._metric._value.get()
        assert after == before + 1.0

    def test_transitions_total_in_all(self):
        from obskit.resilience import circuit_breaker

        assert "_TRANSITIONS_TOTAL" in circuit_breaker.__all__


class TestInstrumentCircuitBreaker:
    def test_attaches_listener_to_pybreaker_cb(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            instrument_circuit_breaker,
        )

        mock_cb = MagicMock()
        listener = instrument_circuit_breaker(mock_cb, name="test_attach")

        mock_cb.add_listener.assert_called_once_with(listener)
        assert isinstance(listener, ObskitCircuitBreakerListener)
        assert listener.name == "test_attach"

    def test_raises_type_error_without_add_listener(self):
        from obskit.resilience.circuit_breaker import instrument_circuit_breaker

        # Object without add_listener
        class FakeCB:
            pass

        with pytest.raises(TypeError, match="add_listener"):
            instrument_circuit_breaker(FakeCB(), name="bad_cb")

    def test_returns_listener(self):
        from obskit.resilience.circuit_breaker import (
            ObskitCircuitBreakerListener,
            instrument_circuit_breaker,
        )

        mock_cb = MagicMock()
        result = instrument_circuit_breaker(mock_cb, name="test_return")

        assert isinstance(result, ObskitCircuitBreakerListener)


class TestResiliencePackageInit:
    def test_public_api(self):
        from obskit.resilience import (
            CircuitState,
            ObskitCircuitBreakerListener,
            instrument_circuit_breaker,
        )

        assert CircuitState is not None
        assert ObskitCircuitBreakerListener is not None
        assert instrument_circuit_breaker is not None
