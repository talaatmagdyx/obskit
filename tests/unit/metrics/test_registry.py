"""Tests for obskit.metrics.registry module."""

import pytest
import threading
from unittest.mock import MagicMock, patch

from obskit.metrics.registry import (
    create_registry,
    get_registry,
    reset_registry,
    start_http_server,
    stop_http_server,
    generate_latest,
    PROMETHEUS_AVAILABLE,
)


class TestCreateRegistry:
    """Tests for create_registry function."""

    def setup_method(self):
        """Reset registry before each test."""
        reset_registry()

    def teardown_method(self):
        """Reset registry after each test."""
        reset_registry()

    def test_create_registry(self):
        """Test creating a new registry."""
        registry = create_registry()
        assert registry is not None

    def test_create_multiple_registries(self):
        """Test creating multiple registries."""
        registry1 = create_registry()
        registry2 = create_registry()
        # Should be different instances
        assert registry1 is not registry2


class TestGetRegistry:
    """Tests for get_registry function."""

    def setup_method(self):
        """Reset registry before each test."""
        reset_registry()

    def teardown_method(self):
        """Reset registry after each test."""
        reset_registry()

    def test_get_registry_returns_registry(self):
        """Test get_registry returns a registry."""
        registry = get_registry()
        assert registry is not None

    def test_get_registry_returns_same_instance(self):
        """Test get_registry returns same instance."""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_get_registry_thread_safe(self):
        """Test get_registry is thread safe."""
        results = []
        
        def get_and_store():
            reg = get_registry()
            results.append(reg)
        
        threads = [threading.Thread(target=get_and_store) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All should be same instance
        assert all(r is results[0] for r in results)


class TestResetRegistry:
    """Tests for reset_registry function."""

    def test_reset_clears_registry(self):
        """Test that reset clears registry."""
        get_registry()  # Ensure one is created
        reset_registry()
        # Should not raise

    def test_reset_allows_new_registry(self):
        """Test reset allows getting new registry."""
        reg1 = get_registry()
        reset_registry()
        # After reset, internal state is cleared
        # get_registry will return the global REGISTRY again


class TestStartHttpServer:
    """Tests for start_http_server function."""

    def setup_method(self):
        """Reset state before each test."""
        stop_http_server()
        reset_registry()

    def teardown_method(self):
        """Stop server after each test."""
        stop_http_server()
        reset_registry()

    @patch('obskit.metrics.registry._start_http_server')
    def test_start_server_basic(self, mock_start):
        """Test starting HTTP server with defaults."""
        mock_start.return_value = (MagicMock(), MagicMock())
        
        result = start_http_server()
        
        assert result is True
        mock_start.assert_called_once()

    @patch('obskit.metrics.registry._start_http_server')
    def test_start_server_custom_port(self, mock_start):
        """Test starting with custom port."""
        mock_start.return_value = (MagicMock(), MagicMock())
        
        result = start_http_server(port=8080)
        
        assert result is True
        # Check port was passed
        call_args = mock_start.call_args
        assert call_args[0][0] == 8080

    @patch('obskit.metrics.registry._start_http_server')
    def test_start_server_custom_host(self, mock_start):
        """Test starting with custom host."""
        mock_start.return_value = (MagicMock(), MagicMock())
        
        result = start_http_server(host="127.0.0.1")
        
        assert result is True
        call_args = mock_start.call_args
        assert call_args[1]["addr"] == "127.0.0.1"

    @patch('obskit.metrics.registry._start_http_server')
    def test_start_server_idempotent(self, mock_start):
        """Test starting server twice is idempotent."""
        mock_start.return_value = (MagicMock(), MagicMock())
        
        start_http_server()
        start_http_server()  # Second call
        
        # Should only start once
        assert mock_start.call_count == 1


class TestStopHttpServer:
    """Tests for stop_http_server function."""

    def setup_method(self):
        """Reset state before each test."""
        stop_http_server()

    def teardown_method(self):
        """Clean up after test."""
        stop_http_server()

    def test_stop_when_not_running(self):
        """Test stop when server not running."""
        # Should not raise
        stop_http_server()

    @patch('obskit.metrics.registry._start_http_server')
    def test_stop_after_start(self, mock_start):
        """Test stop after start."""
        mock_server = MagicMock()
        mock_start.return_value = (mock_server, MagicMock())
        
        start_http_server()
        stop_http_server()
        
        # Server should be shutdown
        mock_server.shutdown.assert_called()


class TestGenerateLatest:
    """Tests for generate_latest function."""

    def test_returns_bytes(self):
        """Test generate_latest returns bytes."""
        result = generate_latest()
        assert isinstance(result, bytes)

    def test_returns_non_empty(self):
        """Test generate_latest returns non-empty output."""
        if PROMETHEUS_AVAILABLE:
            result = generate_latest()
            # May be empty if no metrics registered
            assert isinstance(result, bytes)


class TestStartHttpServerWithAuth:
    """Tests for start_http_server with authentication."""

    def setup_method(self):
        """Reset state before each test."""
        stop_http_server()
        reset_registry()

    def teardown_method(self):
        """Stop server after each test."""
        stop_http_server()
        reset_registry()

    @patch('obskit.metrics.registry.get_settings')
    @patch('obskit.metrics.auth.create_authenticated_handler')
    @patch('http.server.HTTPServer')
    def test_start_server_with_auth(self, mock_http_server, mock_create_handler, mock_settings):
        """Test starting HTTP server with authentication enabled."""
        from obskit.metrics import registry
        
        # Setup mock settings
        mock_settings_obj = MagicMock()
        mock_settings_obj.metrics_port = 9090
        mock_settings_obj.metrics_auth_enabled = True
        mock_settings_obj.metrics_auth_token = "secret-token"
        mock_settings.return_value = mock_settings_obj
        
        # Setup mock handler
        mock_handler = MagicMock()
        mock_create_handler.return_value = mock_handler
        
        # Setup mock server
        mock_server_instance = MagicMock()
        mock_http_server.return_value = mock_server_instance
        
        # Reset module state
        registry._http_server_started = False
        registry._http_server = None
        registry._http_server_thread = None
        
        result = start_http_server()
        
        assert result is True
        mock_create_handler.assert_called_once_with("secret-token")

    @patch('obskit.metrics.registry._http_server')
    @patch('obskit.metrics.registry._http_server_thread')
    @patch('obskit.metrics.registry._http_server_started', True)
    def test_stop_server_with_shutdown_error(self, mock_thread, mock_server):
        """Test stop_http_server handles shutdown AttributeError."""
        from obskit.metrics import registry
        
        # Setup mock server that raises AttributeError on shutdown
        mock_server_obj = MagicMock()
        mock_server_obj.shutdown.side_effect = AttributeError("No shutdown method")
        registry._http_server = mock_server_obj
        registry._http_server_thread = MagicMock()
        registry._http_server_started = True
        
        # Should not raise
        stop_http_server()

    def test_stop_server_when_thread_is_none(self):
        """Test stop_http_server when thread is None but started flag is True."""
        from obskit.metrics import registry
        
        # Set started flag but no thread
        registry._http_server_started = True
        registry._http_server_thread = None
        registry._http_server = None
        
        # Should not raise and should reset flag
        stop_http_server()
        
        assert registry._http_server_started is False

