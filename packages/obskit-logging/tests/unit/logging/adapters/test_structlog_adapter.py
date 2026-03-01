"""Tests for obskit.logging.adapters.structlog_adapter module."""

from obskit.logging.adapters.structlog_adapter import StructlogAdapter


class TestStructlogAdapter:
    """Tests for StructlogAdapter class."""

    def test_init(self):
        """Test adapter initialization."""
        adapter = StructlogAdapter()
        assert isinstance(adapter, StructlogAdapter)

    def test_configure(self):
        """Test configure method."""
        adapter = StructlogAdapter()
        adapter.configure(
            service_name="test-service",
            environment="development",
            version="1.0.0",
            log_level="INFO",
            log_format="json",
        )

    def _configure_adapter(self, adapter, **kwargs):
        """Helper to configure adapter with defaults."""
        defaults = {
            "service_name": "test",
            "environment": "development",
            "version": "1.0.0",
            "log_level": "INFO",
            "log_format": "json",
        }
        defaults.update(kwargs)
        adapter.configure(**defaults)

    def test_get_logger(self):
        """Test get_logger method."""
        adapter = StructlogAdapter()
        self._configure_adapter(adapter)
        logger = adapter.get_logger("test.module")
        assert logger is not None

    def test_info_logging(self):
        """Test info logging."""
        adapter = StructlogAdapter()
        self._configure_adapter(adapter)
        logger = adapter.get_logger("test")
        logger.info("Test message")

    def test_debug_logging(self):
        """Test debug logging."""
        adapter = StructlogAdapter()
        self._configure_adapter(adapter, log_level="DEBUG")
        logger = adapter.get_logger("test")
        logger.debug("Debug message")

    def test_warning_logging(self):
        """Test warning logging."""
        adapter = StructlogAdapter()
        self._configure_adapter(adapter)
        logger = adapter.get_logger("test")
        logger.warning("Warning message")

    def test_error_logging(self):
        """Test error logging."""
        adapter = StructlogAdapter()
        self._configure_adapter(adapter)
        logger = adapter.get_logger("test")
        logger.error("Error message")

    def test_critical_logging(self):
        """Test critical logging."""
        adapter = StructlogAdapter()
        self._configure_adapter(adapter)
        logger = adapter.get_logger("test")
        logger.critical("Critical message")

    def test_exception_logging(self):
        """Test exception logging."""
        adapter = StructlogAdapter()
        self._configure_adapter(adapter)
        logger = adapter.get_logger("test")
        try:
            raise ValueError("Test error")
        except ValueError:
            logger.exception("Exception occurred")

    def test_console_format(self):
        """Test console format configuration."""
        adapter = StructlogAdapter()
        self._configure_adapter(adapter, log_format="console")
        logger = adapter.get_logger("test")
        logger.info("Console format message")

    def test_with_context(self):
        """Test logging with context."""
        adapter = StructlogAdapter()
        self._configure_adapter(adapter)
        logger = adapter.get_logger("test")
        logger.info("Message with context", user_id=123, request_id="abc-123")
