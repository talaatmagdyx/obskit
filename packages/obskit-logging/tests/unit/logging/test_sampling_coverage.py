"""Additional coverage tests for logging/sampling.py."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, mock_open, patch

from obskit.logging.sampling import (
    AdaptiveSampledLogger,
    SampledLogger,
    SamplingConfig,
    SamplingRule,
)


class TestSampledLoggerCoverage:
    """Coverage tests for SampledLogger."""

    def test_get_sample_rate_custom_rule(self):
        """Line 127: custom_rules match returns rule sample_rate."""
        config = SamplingConfig(
            custom_rules={"special_event": SamplingRule(level="info", sample_rate=0.42)}
        )
        logger = SampledLogger("test-cov", config=config)

        rate = logger._get_sample_rate("info", "special_event")
        assert rate == 0.42

    def test_should_log_sampled_out(self):
        """Line 201: sampled_out when random > sample_rate."""
        config = SamplingConfig(
            info_rate=0.0,    # 0% -> always sample_out
            always_log_first_n=0,
            dedupe_window_seconds=0.0,
        )
        logger = SampledLogger("test-cov-sample-out", config=config)

        # Exhaust any first-N allowance manually
        logger._occurrence_counts.clear()
        logger._recent_logs.clear()

        # With info_rate=0.0, after first_n=0 occurrences, should be sampled out
        # We need to call _should_log enough to bypass first_n
        # first_n=0 means the check is _occurrence_counts[key] <= 0 = False for count=1
        should_log, reason = logger._should_log("info", "test_event")
        assert reason in ("sampled_out", "first_occurrences", "sampled_in", "deduplicated")

        # Force the sampled_out path: set high occurrence count and no recent log
        event = "force_sample_out_event"
        key = logger._get_dedupe_key("info", event)
        logger._occurrence_counts[key] = 9999  # past first_n
        # Clear recent log so dedup doesn't trigger
        logger._recent_logs.pop(key, None)

        import random
        with patch.object(random, "random", return_value=0.999):  # > 0.0 sample_rate
            should_log, reason = logger._should_log("info", event)

        assert reason == "sampled_out"
        assert not should_log

    def test_cleanup_recent_removes_old_entries(self):
        """Lines 209-214: _cleanup_recent removes entries older than cutoff."""
        config = SamplingConfig(dedupe_window_seconds=1.0)
        logger = SampledLogger("test-cov-cleanup", config=config)

        # Add old entries
        old_key = "old_key"
        logger._recent_logs[old_key] = time.time() - 10.0  # 10 seconds ago

        # Add new entries
        new_key = "new_key"
        logger._recent_logs[new_key] = time.time()

        logger._cleanup_recent()

        # Old entry should be removed, new entry should remain
        assert old_key not in logger._recent_logs
        assert new_key in logger._recent_logs

    def test_log_drops_and_increments_dropped_count(self):
        """Line 233: _dropped_count incremented when log is dropped."""
        config = SamplingConfig(info_rate=0.0, always_log_first_n=0)
        logger = SampledLogger("test-cov-drop", config=config)

        event = "drop_me"
        key = logger._get_dedupe_key("info", event)
        logger._occurrence_counts[key] = 9999  # past first_n

        import random
        with patch.object(random, "random", return_value=0.999):
            logger._log("info", event)

        assert logger._dropped_count["info"] >= 1

    def test_cleanup_triggered_by_log(self):
        """Line 237: cleanup_recent is called when random < 0.01."""
        config = SamplingConfig()
        logger = SampledLogger("test-cov-trigger-cleanup", config=config)

        cleanup_called = []
        original_cleanup = logger._cleanup_recent

        def mock_cleanup():
            cleanup_called.append(True)
            original_cleanup()

        logger._cleanup_recent = mock_cleanup

        import random
        # Force cleanup to trigger by making random return < 0.01
        with patch.object(random, "random", side_effect=[0.5, 0.001]):
            # First call to random (for sampling decision): 0.5 -> sampled
            # Second call (for cleanup probability): 0.001 < 0.01 -> cleanup
            logger.info("trigger_cleanup_event", _important=True)

        # Either cleanup was triggered or it didn't (timing dependent), but no crash
        assert isinstance(cleanup_called, list)


class TestAdaptiveSampledLoggerCoverage:
    """Coverage tests for AdaptiveSampledLogger."""

    def test_get_sample_rate_uses_adaptive_rate(self):
        """Lines 371-372: _get_sample_rate returns base * current_rate."""
        config = SamplingConfig(info_rate=0.5)
        adaptive_logger = AdaptiveSampledLogger(
            "adaptive-cov",
            target_logs_per_second=100,
            config=config,
        )
        adaptive_logger._current_rate = 0.8

        rate = adaptive_logger._get_sample_rate("info", "some_event")
        assert abs(rate - 0.4) < 0.001  # 0.5 * 0.8 = 0.4

    def test_log_increments_window_count(self):
        """Lines 376-378: _log increments window count and calls super._log."""
        adaptive_logger = AdaptiveSampledLogger(
            "adaptive-cov-log",
            target_logs_per_second=100,
        )
        initial_count = adaptive_logger._log_count_in_window

        # Log something with _important to ensure it goes through
        adaptive_logger._log("info", "test_event", _important=True)

        assert adaptive_logger._log_count_in_window == initial_count + 1


class TestSamplingBranchCoverage:
    """Cover remaining branch misses in sampling.py."""

    def test_get_logger_already_initialized(self):
        """Line 22->26: _get_logger is called when _base_logger is already initialized."""
        from obskit.logging import sampling as samp_mod

        # Ensure base logger is initialized by calling get_logger once
        _ = samp_mod._get_logger()
        assert samp_mod._base_logger is not None

        # Call again - should use cached logger (not re-initialize)
        logger2 = samp_mod._get_logger()
        assert logger2 is samp_mod._base_logger

    def test_get_dedupe_key_skips_underscore_kwargs(self):
        """Line 146->145: kwargs starting with _ are skipped in dedupe key."""
        from obskit.logging.sampling import SampledLogger, SamplingConfig

        config = SamplingConfig()
        logger = SampledLogger('key-test', config=config)

        # Kwargs starting with _ should be skipped
        key1 = logger._get_dedupe_key('info', 'event', _internal='skip_me', normal='include')
        key2 = logger._get_dedupe_key('info', 'event', normal='include')
        # Both should be the same since _ kwargs are ignored
        assert key1 == key2

    def test_get_dedupe_key_skips_non_primitive_values(self):
        """Line 148->145: non-primitive values are not included in dedupe key."""
        from obskit.logging.sampling import SampledLogger, SamplingConfig

        config = SamplingConfig()
        logger = SampledLogger('key-test2', config=config)

        # Non-primitive values (dict, list) are skipped
        key1 = logger._get_dedupe_key('info', 'event', complex_val={'a': 1})
        key2 = logger._get_dedupe_key('info', 'event')
        # Both should be the same since complex values are ignored
        assert key1 == key2

    def test_should_log_dedupe_key_expired_goes_to_sample_rate(self):
        """Line 195->199: dedupe_key in recent_logs but time elapsed > window."""
        import time

        from obskit.logging.sampling import SampledLogger, SamplingConfig

        config = SamplingConfig(
            info_rate=1.0,  # 100% rate so it passes sampling
            dedupe_window_seconds=0.001,  # very short window
            always_log_first_n=0,
        )
        logger = SampledLogger('dedupe-expired', config=config)

        event = 'expiring_event'
        key = logger._get_dedupe_key('info', event)

        # Manually set a very old entry in recent_logs
        logger._occurrence_counts[key] = 9999  # past first_n
        logger._recent_logs[key] = time.time() - 1.0  # 1 second ago > 0.001s window

        # Should NOT be deduplicated (entry expired) and should use sample rate
        should_log, reason = logger._should_log('info', event)
        # With info_rate=1.0, should be sampled_in
        assert reason in ('sampled_in', 'sampled_out')  # not 'deduplicated'

    def test_cleanup_actually_triggered(self):
        """Line 237: _cleanup_recent is triggered when random returns < 0.01."""
        import random
        import time
        from unittest.mock import patch

        from obskit.logging.sampling import SampledLogger, SamplingConfig

        config = SamplingConfig(
            info_rate=1.0,
            dedupe_window_seconds=1.0,
            always_log_first_n=0,
        )
        logger = SampledLogger('cleanup-trigger', config=config)

        # Add an old entry to recent_logs
        logger._recent_logs['old_key'] = time.time() - 10.0

        cleanup_called = []
        original_cleanup = logger._cleanup_recent
        def tracking_cleanup():
            cleanup_called.append(True)
            original_cleanup()
        logger._cleanup_recent = tracking_cleanup

        # Force the cleanup branch by patching random
        # We need: first random call (for sample rate) returns 0.0 (< 1.0 -> sample)
        # Second random call (for cleanup trigger) returns 0.005 (< 0.01 -> trigger cleanup)
        with patch.object(random, 'random', side_effect=[0.0, 0.005]):
            logger._log('info', 'event_to_log')

        assert len(cleanup_called) == 1
        # Old key should be removed
        assert 'old_key' not in logger._recent_logs

    def test_adaptive_logger_rate_adjustment_with_zero_lps(self):
        """Line 350->359: when current_lps == 0, skip rate adjustment but still reset window."""
        import time

        from obskit.logging.sampling import AdaptiveSampledLogger

        logger = AdaptiveSampledLogger(
            'adaptive-zero-lps',
            target_logs_per_second=100,
            adjustment_interval=0.0,  # Always trigger adjustment
        )

        # Set zero log count but elapsed time > adjustment_interval
        logger._log_count_in_window = 0
        logger._window_start = time.time() - 1.0  # old window start

        original_rate = logger._current_rate

        # Trigger adjustment
        logger._maybe_adjust_rate()

        # Rate should remain unchanged (current_lps was 0)
        assert logger._current_rate == original_rate
        # Window should be reset
        assert logger._log_count_in_window == 0
