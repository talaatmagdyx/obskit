"""Unit tests for obskit.integrations.resilience.pybreaker."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestInstrumentPybreaker:
    def test_returns_listener(self):
        from obskit.integrations.resilience.pybreaker import instrument_pybreaker
        from obskit.resilience.circuit_breaker import ObskitCircuitBreakerListener

        mock_cb = MagicMock()
        listener = instrument_pybreaker(mock_cb, name="twitter")
        assert isinstance(listener, ObskitCircuitBreakerListener)

    def test_attaches_listener_to_cb(self):
        from obskit.integrations.resilience.pybreaker import instrument_pybreaker

        mock_cb = MagicMock()
        listener = instrument_pybreaker(mock_cb, name="payments")
        mock_cb.add_listener.assert_called_once_with(listener)

    def test_stores_name(self):
        from obskit.integrations.resilience.pybreaker import instrument_pybreaker

        mock_cb = MagicMock()
        listener = instrument_pybreaker(mock_cb, name="redis")
        assert listener.name == "redis"

    def test_raises_type_error_without_add_listener(self):
        from obskit.integrations.resilience.pybreaker import instrument_pybreaker

        class NoCB:
            pass

        with pytest.raises(TypeError, match="add_listener"):
            instrument_pybreaker(NoCB(), name="bad")

    def test_state_change_emits_transition_counter(self):
        """Transition counter is populated via the shared listener."""
        from obskit.integrations.resilience.pybreaker import instrument_pybreaker
        from obskit.resilience.circuit_breaker import _TRANSITIONS_TOTAL

        mock_cb = MagicMock()
        listener = instrument_pybreaker(mock_cb, name="svc_pb")
        before = _TRANSITIONS_TOTAL.labels(
            name="svc_pb", from_state="closed", to_state="open"
        )._metric._value.get()
        listener.state_change(mock_cb, "closed", "open")
        after = _TRANSITIONS_TOTAL.labels(
            name="svc_pb", from_state="closed", to_state="open"
        )._metric._value.get()
        assert after == before + 1.0

    def test_all_exports(self):
        import obskit.integrations.resilience.pybreaker as m

        assert "instrument_pybreaker" in m.__all__
