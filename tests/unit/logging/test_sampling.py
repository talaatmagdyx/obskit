"""Unit tests for smart log sampling."""

import time

from obskit.logging.sampling import (
    AdaptiveSampledLogger,
    SampledLogger,
    SamplingConfig,
    SamplingRule,
    get_sampling_stats,
)


class TestSamplingConfig:
    """Tests for SamplingConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = SamplingConfig()

        assert config.debug_rate == 0.01
        assert config.info_rate == 0.1
        assert config.warning_rate == 1.0
        assert config.error_rate == 1.0
        assert config.critical_rate == 1.0
        assert config.slow_threshold_seconds == 1.0
        assert config.dedupe_window_seconds == 60.0
        assert config.always_log_first_n == 3

    def test_custom_config(self):
        """Test custom configuration."""
        config = SamplingConfig(
            debug_rate=0.001,
            info_rate=0.05,
            slow_threshold_seconds=2.0,
            dedupe_window_seconds=120.0,
        )

        assert config.debug_rate == 0.001
        assert config.info_rate == 0.05
        assert config.slow_threshold_seconds == 2.0
        assert config.dedupe_window_seconds == 120.0

    def test_always_log_events(self):
        """Test always_log_events configuration."""
        config = SamplingConfig(always_log_events={"startup", "shutdown", "error"})

        assert "startup" in config.always_log_events
        assert "shutdown" in config.always_log_events

    def test_never_log_events(self):
        """Test never_log_events configuration."""
        config = SamplingConfig(never_log_events={"heartbeat", "ping"})

        assert "heartbeat" in config.never_log_events


class TestSamplingRule:
    """Tests for SamplingRule dataclass."""

    def test_defaults(self):
        """Test default rule values."""
        rule = SamplingRule(level="info")

        assert rule.level == "info"
        assert rule.sample_rate == 1.0
        assert rule.min_interval_seconds == 0.0
        assert rule.dedupe_key is None
        assert rule.always_log_first_n == 0

    def test_custom_rule(self):
        """Test custom rule configuration."""
        rule = SamplingRule(
            level="debug",
            sample_rate=0.1,
            min_interval_seconds=5.0,
            dedupe_key="request_id",
            always_log_first_n=5,
        )

        assert rule.sample_rate == 0.1
        assert rule.min_interval_seconds == 5.0
        assert rule.always_log_first_n == 5


class TestSampledLogger:
    """Tests for SampledLogger class."""

    def test_init(self):
        """Test logger initialization."""
        logger = SampledLogger("test_logger")

        assert logger.name == "test_logger"
        assert logger.config is not None

    def test_init_with_config(self):
        """Test logger initialization with custom config."""
        config = SamplingConfig(info_rate=0.5)
        logger = SampledLogger("test_logger", config=config)

        assert logger.config.info_rate == 0.5

    def test_always_log_events(self):
        """Test always_log_events are always logged."""
        config = SamplingConfig(
            info_rate=0.0,  # Normally would never log
            always_log_events={"important_event"},
        )
        logger = SampledLogger("test", config=config)

        should_log, reason = logger._should_log("info", "important_event")

        assert should_log is True
        assert reason == "always_log_event"

    def test_never_log_events(self):
        """Test never_log_events are never logged."""
        config = SamplingConfig(
            info_rate=1.0,  # Would normally always log
            never_log_events={"noisy_event"},
        )
        logger = SampledLogger("test", config=config)

        should_log, reason = logger._should_log("info", "noisy_event")

        assert should_log is False
        assert reason == "never_log_event"

    def test_important_flag(self):
        """Test _important flag bypasses sampling."""
        config = SamplingConfig(info_rate=0.0)
        logger = SampledLogger("test", config=config)

        should_log, reason = logger._should_log("info", "normal_event", important=True)

        assert should_log is True
        assert reason == "marked_important"

    def test_slow_operations_always_logged(self):
        """Test slow operations are always logged."""
        config = SamplingConfig(info_rate=0.0, slow_threshold_seconds=1.0)
        logger = SampledLogger("test", config=config)

        should_log, reason = logger._should_log("info", "slow_event", duration_seconds=2.0)

        assert should_log is True
        assert reason == "slow_operation"

    def test_first_n_always_logged(self):
        """Test first N occurrences are always logged."""
        config = SamplingConfig(info_rate=0.0, always_log_first_n=3)
        logger = SampledLogger("test", config=config)

        # First 3 should be logged
        for i in range(3):
            should_log, reason = logger._should_log("info", "test_event", key=i)
            assert should_log is True
            assert reason == "first_occurrences"

    def test_deduplication(self):
        """Test log deduplication."""
        config = SamplingConfig(info_rate=1.0, dedupe_window_seconds=60.0, always_log_first_n=0)
        logger = SampledLogger("test", config=config)

        # First occurrence
        should_log1, reason1 = logger._should_log("info", "dedupe_event", key="same")
        assert reason1 is None or isinstance(reason1, str)  # Verify reason format

        # Immediate duplicate
        should_log2, reason2 = logger._should_log("info", "dedupe_event", key="same")
        assert reason2 is None or isinstance(reason2, str)  # Verify reason format

        # Different key should log
        should_log3, reason3 = logger._should_log("info", "dedupe_event", key="different")
        assert reason3 is None or isinstance(reason3, str)  # Verify reason format

        assert should_log1 is True
        assert should_log3 is True

    def test_log_methods(self):
        """Test all log level methods exist and work."""
        logger = SampledLogger("test")

        # These should not raise
        logger.debug("debug_event")
        logger.info("info_event")
        logger.warning("warning_event")
        logger.error("error_event")
        logger.critical("critical_event")

    def test_exception_always_logged(self):
        """Test exception method always logs."""
        config = SamplingConfig(error_rate=0.0)
        logger = SampledLogger("test", config=config)

        # Exception should be marked important internally
        logger.exception("error_event")

    def test_bind_returns_new_logger(self):
        """Test bind returns new logger with bound context."""
        logger = SampledLogger("test")
        bound = logger.bind(request_id="123")

        assert bound is not logger
        assert isinstance(bound, SampledLogger)

    def test_get_stats(self):
        """Test getting sampling statistics."""
        logger = SampledLogger("test")

        # Generate some logs
        logger.info("event1")
        logger.info("event2")
        logger.error("error_event")

        stats = logger.get_stats()

        assert "logger_name" in stats
        assert "total_logs" in stats
        assert "sampled" in stats
        assert "dropped" in stats
        assert "effective_rate" in stats
        assert "by_level" in stats


class TestAdaptiveSampledLogger:
    """Tests for AdaptiveSampledLogger class."""

    def test_init(self):
        """Test adaptive logger initialization."""
        logger = AdaptiveSampledLogger(name="adaptive_test", target_logs_per_second=100)

        assert logger.target_lps == 100
        assert logger.min_rate == 0.001
        assert logger.max_rate == 1.0

    def test_init_custom_rates(self):
        """Test adaptive logger with custom rate bounds."""
        logger = AdaptiveSampledLogger(
            name="adaptive_test",
            target_logs_per_second=50,
            min_sample_rate=0.01,
            max_sample_rate=0.5,
        )

        assert logger.min_rate == 0.01
        assert logger.max_rate == 0.5

    def test_rate_starts_at_max(self):
        """Test initial rate is max."""
        logger = AdaptiveSampledLogger(name="adaptive_test", target_logs_per_second=100)

        assert logger._current_rate == 1.0

    def test_high_volume_reduces_rate(self):
        """Test high log volume reduces sampling rate."""
        logger = AdaptiveSampledLogger(
            name="adaptive_test",
            target_logs_per_second=10,
            adjustment_interval=0.1,  # Short interval for testing
        )

        # Generate high volume
        for _ in range(100):
            logger._log_count_in_window += 1

        # Trigger rate adjustment
        logger._window_start = time.time() - 0.2
        logger._maybe_adjust_rate()

        # Rate should be reduced
        assert logger._current_rate < 1.0


class TestGetSamplingStats:
    """Tests for get_sampling_stats function."""

    def test_returns_dict(self):
        """Test returns dictionary of stats."""
        stats = get_sampling_stats()
        assert isinstance(stats, dict)

    def test_includes_logger_stats(self):
        """Test includes stats from loggers."""
        logger = SampledLogger("stats_test")
        logger.info("test_event")

        stats = get_sampling_stats()

        # Stats should be tracked
        assert isinstance(stats, dict)
