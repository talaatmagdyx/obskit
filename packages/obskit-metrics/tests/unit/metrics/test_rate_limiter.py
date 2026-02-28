"""Tests for metrics endpoint rate limiting."""

from __future__ import annotations

import time
from io import BytesIO
from unittest.mock import MagicMock, patch

# Use module import consistently to avoid import/from-import mixing
import obskit.metrics.auth as auth_module


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_allows_requests_within_limit(self) -> None:
        """Test rate limiter allows requests within limit."""
        limiter = auth_module.RateLimiter(max_requests=5, window_seconds=60)

        for _ in range(5):
            assert limiter.is_allowed()

    def test_blocks_requests_over_limit(self) -> None:
        """Test rate limiter blocks requests over limit."""
        limiter = auth_module.RateLimiter(max_requests=3, window_seconds=60)

        # Use up the limit
        for _ in range(3):
            assert limiter.is_allowed()

        # Next request should be blocked
        assert not limiter.is_allowed()

    def test_get_remaining(self) -> None:
        """Test get_remaining returns correct count."""
        limiter = auth_module.RateLimiter(max_requests=5, window_seconds=60)

        assert limiter.get_remaining() == 5

        limiter.is_allowed()
        assert limiter.get_remaining() == 4

        limiter.is_allowed()
        limiter.is_allowed()
        assert limiter.get_remaining() == 2

    def test_window_sliding(self) -> None:
        """Test requests expire after window."""
        limiter = auth_module.RateLimiter(max_requests=2, window_seconds=0.1)

        # Use up limit
        assert limiter.is_allowed()
        assert limiter.is_allowed()
        assert not limiter.is_allowed()

        # Wait for window to expire
        time.sleep(0.15)

        # Should be allowed again
        assert limiter.is_allowed()


class TestGetRateLimiter:
    """Tests for _get_rate_limiter function."""

    def test_returns_none_when_disabled(self) -> None:
        """Test returns None when rate limiting disabled."""
        from obskit.config import configure, reset_settings

        reset_settings()
        configure(metrics_rate_limit_enabled=False)

        limiter = auth_module._get_rate_limiter()
        assert limiter is None

        reset_settings()

    def test_returns_limiter_when_enabled(self) -> None:
        """Test returns limiter when enabled."""
        from obskit.config import configure, reset_settings

        # Reset global state
        reset_settings()

        # Need to reset the module-level rate limiter
        auth_module._metrics_rate_limiter = None

        configure(
            metrics_rate_limit_enabled=True,
            metrics_rate_limit_requests=100,
        )

        limiter = auth_module._get_rate_limiter()
        assert limiter is not None

        # Should return same instance
        limiter2 = auth_module._get_rate_limiter()
        assert limiter is limiter2

        reset_settings()
        auth_module._metrics_rate_limiter = None


class TestAuthenticatedMetricsHandlerRateLimiting:
    """Tests for rate limiting in AuthenticatedMetricsHandler."""

    def test_rate_limited_request(self) -> None:
        """Test request is rate limited."""
        from obskit.config import reset_settings

        reset_settings()

        # Mock a rate limiter that always blocks
        mock_limiter = auth_module.RateLimiter(max_requests=0, window_seconds=60)

        with patch("obskit.metrics.auth._get_rate_limiter", return_value=mock_limiter):
            # Create mock request
            handler = MagicMock(spec=auth_module.AuthenticatedMetricsHandler)
            handler.auth_token = None
            handler.path = "/metrics"
            handler.wfile = BytesIO()
            handler.client_address = ("127.0.0.1", 12345)

            # Mock methods
            handler.send_response = MagicMock()
            handler.send_header = MagicMock()
            handler.end_headers = MagicMock()

            # Call do_GET
            auth_module.AuthenticatedMetricsHandler.do_GET(handler)

            # Should send 429
            handler.send_response.assert_called_with(429)
            handler.send_header.assert_any_call("Retry-After", "60")

        reset_settings()
