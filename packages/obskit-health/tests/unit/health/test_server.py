"""
Tests for obskit.health.server module.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

import obskit.health.server as server_module
from obskit.health.server import (
    HealthRequestHandler,
    get_health_server,
    is_health_server_running,
    register_health_endpoint,
    start_health_server,
    stop_health_server,
)

# =============================================================================
# Helper: MockRequest handler for testing without real HTTP
# =============================================================================


def _make_handler(path="/health"):
    """Create a HealthRequestHandler without actually opening a socket."""
    handler = HealthRequestHandler.__new__(HealthRequestHandler)
    handler.path = path
    handler._response_code = None
    handler._response_headers = {}
    handler._response_body = b""
    handler.wfile = BytesIO()
    return handler


class TestHealthRequestHandler:
    """Test the HealthRequestHandler with mocked request/response."""

    def setup_method(self):
        # Reset custom handlers before each test
        server_module._custom_handlers.clear()

    def _invoke_handler(self, path):
        """Create a handler and call do_GET."""
        handler = HealthRequestHandler.__new__(HealthRequestHandler)
        handler.path = path
        handler.wfile = BytesIO()
        handler._headers_buffer = BytesIO()

        responses = []
        errors = []

        def mock_send_response(code):
            responses.append(code)

        def mock_send_header(key, val):
            pass

        def mock_end_headers():
            pass

        def mock_send_error(code, msg=None):
            errors.append((code, msg))

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers
        handler.send_error = mock_send_error

        response_data = []

        def mock_send_json(status_code, data):
            response_data.append((status_code, data))

        handler._send_json = mock_send_json
        handler.do_GET()
        return response_data, errors

    def test_liveness_endpoint(self):
        data, errors = self._invoke_handler("/health/live")
        assert len(data) == 1
        status_code, body = data[0]
        assert status_code == 200
        assert body["healthy"] is True
        assert body["status"] == "alive"

    def test_liveness_healthz(self):
        data, _ = self._invoke_handler("/healthz")
        assert data[0][0] == 200

    def test_liveness_livez(self):
        data, _ = self._invoke_handler("/livez")
        assert data[0][0] == 200

    def test_readiness_endpoint_no_slo(self):
        with patch("obskit.health.server.HealthRequestHandler._get_slo_status") as mock_slo:
            mock_slo.return_value = {"healthy": True, "status": "unknown"}
            data, _ = self._invoke_handler("/health/ready")
        assert data[0][0] == 200
        assert data[0][1]["healthy"] is True

    def test_readiness_endpoint_slo_critical(self):
        with patch("obskit.health.server.HealthRequestHandler._get_slo_status") as mock_slo:
            mock_slo.return_value = {"healthy": False, "status": "critical"}
            data, _ = self._invoke_handler("/health/ready")
        assert data[0][0] == 503
        assert data[0][1]["healthy"] is False

    def test_readiness_readyz_alias(self):
        with patch("obskit.health.server.HealthRequestHandler._get_slo_status") as mock_slo:
            mock_slo.return_value = {"healthy": True, "status": "healthy"}
            data, _ = self._invoke_handler("/readyz")
        assert data[0][0] == 200

    def test_health_endpoint_healthy(self):
        with patch("obskit.health.server.HealthRequestHandler._get_slo_status") as mock_slo:
            mock_slo.return_value = {"healthy": True, "status": "healthy"}
            data, _ = self._invoke_handler("/health")
        assert data[0][0] == 200

    def test_health_endpoint_slo_critical(self):
        with patch("obskit.health.server.HealthRequestHandler._get_slo_status") as mock_slo:
            mock_slo.return_value = {"status": "critical", "healthy": False}
            data, _ = self._invoke_handler("/health")
        assert data[0][0] == 503

    def test_slo_endpoint(self):
        with patch("obskit.health.server.HealthRequestHandler._get_slo_status") as mock_slo:
            mock_slo.return_value = {"healthy": True, "status": "healthy"}
            data, _ = self._invoke_handler("/health/slo")
        assert data[0][0] == 200

    def test_slo_endpoint_unhealthy(self):
        with patch("obskit.health.server.HealthRequestHandler._get_slo_status") as mock_slo:
            mock_slo.return_value = {"healthy": False, "status": "critical"}
            data, _ = self._invoke_handler("/health/slo")
        assert data[0][0] == 503

    def test_unknown_path(self):
        _, errors = self._invoke_handler("/unknown/path")
        assert len(errors) == 1
        assert errors[0][0] == 404

    def test_custom_handler_healthy(self):
        def my_check():
            return {"healthy": True, "message": "Custom OK"}

        register_health_endpoint("/health/custom", my_check)
        data, _ = self._invoke_handler("/health/custom")
        assert data[0][0] == 200
        assert data[0][1]["healthy"] is True

    def test_custom_handler_unhealthy(self):
        def my_check():
            return {"healthy": False, "message": "Custom FAIL"}

        register_health_endpoint("/health/custom_fail", my_check)
        data, _ = self._invoke_handler("/health/custom_fail")
        assert data[0][0] == 503

    def test_custom_handler_exception(self):
        def bad_check():
            raise RuntimeError("Check crashed")

        register_health_endpoint("/health/broken", bad_check)
        data, _ = self._invoke_handler("/health/broken")
        assert data[0][0] == 500
        assert data[0][1]["healthy"] is False

    def test_get_slo_status_uses_slo_check(self):
        """Test _get_slo_status calls get_slo_health_status (local import)."""
        handler = HealthRequestHandler.__new__(HealthRequestHandler)
        # The method does a local import inside _get_slo_status, so patch the source
        with patch("obskit.health.slo_check.get_slo_health_status") as mock_get_slo:
            mock_get_slo.return_value = {"healthy": True, "status": "healthy"}
            result = handler._get_slo_status()
        assert result["healthy"] is True

    def test_get_slo_status_import_error(self):
        """Test _get_slo_status returns safe fallback when exception occurs."""
        handler = HealthRequestHandler.__new__(HealthRequestHandler)
        # Patch the slo_check module function so the local import raises
        with patch(
            "obskit.health.slo_check.get_slo_health_status",
            side_effect=Exception("import error"),
        ):
            result = handler._get_slo_status()
        assert result["healthy"] is True
        assert result["status"] == "unknown"

    def test_handle_readiness_exception(self):
        handler = HealthRequestHandler.__new__(HealthRequestHandler)
        handler.wfile = BytesIO()
        responses = []

        def mock_send_json(code, data):
            responses.append((code, data))

        handler._send_json = mock_send_json
        # Force _get_slo_status to raise
        handler._get_slo_status = MagicMock(side_effect=Exception("Readiness error"))
        handler._handle_readiness()
        assert responses[0][0] == 503
        assert responses[0][1]["healthy"] is False

    def test_handle_health_exception(self):
        handler = HealthRequestHandler.__new__(HealthRequestHandler)
        responses = []

        def mock_send_json(code, data):
            responses.append((code, data))

        handler._send_json = mock_send_json
        handler._get_slo_status = MagicMock(side_effect=Exception("Health error"))
        with patch("obskit.health.server.get_health_checker", side_effect=Exception("init error")):
            handler._handle_health()
        assert responses[0][0] == 503

    def test_handle_slo_exception(self):
        handler = HealthRequestHandler.__new__(HealthRequestHandler)
        responses = []

        def mock_send_json(code, data):
            responses.append((code, data))

        handler._send_json = mock_send_json
        handler._get_slo_status = MagicMock(side_effect=Exception("SLO error"))
        handler._handle_slo()
        assert responses[0][0] == 500


# =============================================================================
# start_health_server / stop_health_server Tests
# =============================================================================


class TestHealthServerStartStop:
    def setup_method(self):
        stop_health_server()  # Ensure clean state

    def teardown_method(self):
        stop_health_server()

    def test_start_returns_server_instance(self):
        from http.server import HTTPServer

        server = start_health_server(port=18989, host="127.0.0.1", daemon=True)
        assert server is not None
        assert is_health_server_running() is True
        stop_health_server()

    def test_start_already_running(self):
        start_health_server(port=18990, host="127.0.0.1", daemon=True)
        # Start again on same port - should return existing instance
        server2 = start_health_server(port=18990, host="127.0.0.1", daemon=True)
        assert server2 is server_module._health_server
        stop_health_server()

    def test_stop_when_not_running(self):
        # Should not raise
        stop_health_server()
        assert is_health_server_running() is False

    def test_get_health_server_not_running(self):
        result = get_health_server()
        assert result is None

    def test_is_health_server_running_false_when_stopped(self):
        assert is_health_server_running() is False

    def test_server_responds_to_health_endpoint(self):
        start_health_server(port=18991, host="127.0.0.1", daemon=True)
        time.sleep(0.1)
        try:
            with urllib.request.urlopen("http://127.0.0.1:18991/health/live", timeout=3) as resp:
                data = json.loads(resp.read().decode())
                assert data["healthy"] is True
        finally:
            stop_health_server()


# =============================================================================
# register_health_endpoint Tests
# =============================================================================


class TestRegisterHealthEndpoint:
    def setup_method(self):
        server_module._custom_handlers.clear()

    def test_register_with_leading_slash(self):
        register_health_endpoint("/health/custom_x", lambda: {"healthy": True})
        assert "/health/custom_x" in server_module._custom_handlers

    def test_register_without_leading_slash(self):
        register_health_endpoint("health/custom_y", lambda: {"healthy": True})
        assert "/health/custom_y" in server_module._custom_handlers

    def test_registered_handler_callable(self):
        def my_handler():
            return {"healthy": True, "message": "test"}

        register_health_endpoint("/health/test_cb", my_handler)
        handler = server_module._custom_handlers["/health/test_cb"]
        result = handler()
        assert result["message"] == "test"
