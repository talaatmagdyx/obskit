"""Unit tests for obskit.integrations.resilience.rate_limiter."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestInstrumentRateLimiter:
    def test_returns_instrumentor(self):
        from obskit.integrations.resilience.rate_limiter import (
            RateLimiterInstrumentor,
            instrument_rate_limiter,
        )

        mock_limiter = MagicMock()
        instr = instrument_rate_limiter(mock_limiter, platform="twitter")
        assert isinstance(instr, RateLimiterInstrumentor)

    def test_default_platform(self):
        from obskit.integrations.resilience.rate_limiter import instrument_rate_limiter

        mock_limiter = MagicMock()
        instr = instrument_rate_limiter(mock_limiter)
        assert instr._platform == "default"

    def test_stores_platform(self):
        from obskit.integrations.resilience.rate_limiter import instrument_rate_limiter

        mock_limiter = MagicMock()
        instr = instrument_rate_limiter(mock_limiter, platform="facebook")
        assert instr._platform == "facebook"

    def test_stores_limiter_reference(self):
        from obskit.integrations.resilience.rate_limiter import instrument_rate_limiter

        mock_limiter = MagicMock()
        instr = instrument_rate_limiter(mock_limiter, platform="p0")
        assert instr._limiter is mock_limiter


class TestRateLimiterInstrumentorCheck:
    def test_check_success_no_counter_increment(self):
        from obskit.integrations.resilience.rate_limiter import (
            RATE_LIMIT_HITS_TOTAL,
            instrument_rate_limiter,
        )

        mock_limiter = MagicMock()
        mock_limiter.check.return_value = True
        before = RATE_LIMIT_HITS_TOTAL.labels(platform="p_ok")._value.get()
        instrument_rate_limiter(mock_limiter, platform="p_ok")
        mock_limiter.check()
        after = RATE_LIMIT_HITS_TOTAL.labels(platform="p_ok")._value.get()
        assert after == before  # no increment on success

    def test_check_exception_increments_hits(self):
        from obskit.integrations.resilience.rate_limiter import (
            RATE_LIMIT_HITS_TOTAL,
            instrument_rate_limiter,
        )

        mock_limiter = MagicMock()
        mock_limiter.check.side_effect = RuntimeError("rate limited")
        before = RATE_LIMIT_HITS_TOTAL.labels(platform="p_hit")._value.get()
        instrument_rate_limiter(mock_limiter, platform="p_hit")
        with pytest.raises(RuntimeError, match="rate limited"):
            mock_limiter.check()
        after = RATE_LIMIT_HITS_TOTAL.labels(platform="p_hit")._value.get()
        assert after == before + 1.0

    def test_check_exception_reraises(self):
        """The original exception is always re-raised after incrementing counter."""
        from obskit.integrations.resilience.rate_limiter import instrument_rate_limiter

        mock_limiter = MagicMock()
        mock_limiter.check.side_effect = ValueError("quota exceeded")
        instrument_rate_limiter(mock_limiter, platform="p_reraise")
        with pytest.raises(ValueError, match="quota exceeded"):
            mock_limiter.check()

    def test_check_exception_with_retry_after_sets_gauge(self):
        """retry_after attribute on exception updates reset-seconds gauge."""
        from obskit.integrations.resilience.rate_limiter import (
            RATE_LIMIT_RESET_SECONDS,
            instrument_rate_limiter,
        )

        exc = RuntimeError("rate limited")
        exc.retry_after = 847  # type: ignore[attr-defined]
        mock_limiter = MagicMock()
        mock_limiter.check.side_effect = exc
        instrument_rate_limiter(mock_limiter, platform="p_retry")
        with pytest.raises(RuntimeError):
            mock_limiter.check()
        assert RATE_LIMIT_RESET_SECONDS.labels(platform="p_retry")._value.get() == 847.0

    def test_check_exception_with_reset_after_sets_gauge(self):
        """reset_after attribute (alternative name) also updates the gauge."""
        from obskit.integrations.resilience.rate_limiter import (
            RATE_LIMIT_RESET_SECONDS,
            instrument_rate_limiter,
        )

        exc = RuntimeError("rate limited")
        exc.reset_after = 300  # type: ignore[attr-defined]
        mock_limiter = MagicMock()
        mock_limiter.check.side_effect = exc
        instrument_rate_limiter(mock_limiter, platform="p_reset")
        with pytest.raises(RuntimeError):
            mock_limiter.check()
        assert RATE_LIMIT_RESET_SECONDS.labels(platform="p_reset")._value.get() == 300.0

    def test_check_exception_without_reset_attr_no_gauge_update(self):
        """No reset attribute — gauge is not modified."""
        from obskit.integrations.resilience.rate_limiter import (
            RATE_LIMIT_RESET_SECONDS,
            instrument_rate_limiter,
        )

        mock_limiter = MagicMock()
        mock_limiter.check.side_effect = RuntimeError("limited")
        before = RATE_LIMIT_RESET_SECONDS.labels(platform="p_noreset")._value.get()
        instrument_rate_limiter(mock_limiter, platform="p_noreset")
        with pytest.raises(RuntimeError):
            mock_limiter.check()
        after = RATE_LIMIT_RESET_SECONDS.labels(platform="p_noreset")._value.get()
        assert after == before  # unchanged

    def test_check_passes_args_to_original(self):
        from obskit.integrations.resilience.rate_limiter import instrument_rate_limiter

        mock_limiter = MagicMock()
        original_check = mock_limiter.check
        instrument_rate_limiter(mock_limiter, platform="p_args")
        mock_limiter.check("arg1", key="val")
        original_check.assert_called_once_with("arg1", key="val")

    def test_check_is_patched(self):
        from obskit.integrations.resilience.rate_limiter import instrument_rate_limiter

        mock_limiter = MagicMock()
        original_check = mock_limiter.check
        instrument_rate_limiter(mock_limiter, platform="p_patch")
        assert mock_limiter.check is not original_check


class TestRateLimiterInstrumentorRecordLimit:
    def test_record_limit_increments_counter(self):
        from obskit.integrations.resilience.rate_limiter import (
            RATE_LIMIT_RECORDED_TOTAL,
            instrument_rate_limiter,
        )

        mock_limiter = MagicMock()
        mock_limiter.record_limit.return_value = None
        before = RATE_LIMIT_RECORDED_TOTAL.labels(platform="r_inc")._value.get()
        instrument_rate_limiter(mock_limiter, platform="r_inc")
        mock_limiter.record_limit()
        after = RATE_LIMIT_RECORDED_TOTAL.labels(platform="r_inc")._value.get()
        assert after == before + 1.0

    def test_record_limit_returns_original_value(self):
        from obskit.integrations.resilience.rate_limiter import instrument_rate_limiter

        mock_limiter = MagicMock()
        mock_limiter.record_limit.return_value = "token_123"
        instrument_rate_limiter(mock_limiter, platform="r_ret")
        result = mock_limiter.record_limit()
        assert result == "token_123"

    def test_record_limit_multiple_calls_accumulate(self):
        from obskit.integrations.resilience.rate_limiter import (
            RATE_LIMIT_RECORDED_TOTAL,
            instrument_rate_limiter,
        )

        mock_limiter = MagicMock()
        before = RATE_LIMIT_RECORDED_TOTAL.labels(platform="r_multi")._value.get()
        instrument_rate_limiter(mock_limiter, platform="r_multi")
        mock_limiter.record_limit()
        mock_limiter.record_limit()
        mock_limiter.record_limit()
        after = RATE_LIMIT_RECORDED_TOTAL.labels(platform="r_multi")._value.get()
        assert after == before + 3.0

    def test_record_limit_is_patched(self):
        from obskit.integrations.resilience.rate_limiter import instrument_rate_limiter

        mock_limiter = MagicMock()
        original_record = mock_limiter.record_limit
        instrument_rate_limiter(mock_limiter, platform="r_patch")
        assert mock_limiter.record_limit is not original_record


class TestRateLimiterPublicAPI:
    def test_all_exports_present(self):
        import obskit.integrations.resilience.rate_limiter as m

        for name in (
            "RateLimiterInstrumentor",
            "instrument_rate_limiter",
            "RATE_LIMIT_HITS_TOTAL",
            "RATE_LIMIT_RECORDED_TOTAL",
            "RATE_LIMIT_RESET_SECONDS",
        ):
            assert hasattr(m, name), f"missing export: {name}"
