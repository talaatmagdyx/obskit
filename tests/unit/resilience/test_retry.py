"""Tests for obskit.resilience.retry module."""

import pytest

from obskit.resilience.retry import (
    RetryConfig,
    RetryError,
    _is_permanent_http_failure,
    retry,
    retry_sync,
    should_retry,
)


class TestRetryDecorator:
    """Tests for retry decorator."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        """Test successful call doesn't retry."""
        call_count = [0]

        @retry(max_attempts=3)
        async def successful():
            call_count[0] += 1
            return "success"

        result = await successful()
        assert result == "success"
        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test retry on transient failure."""
        call_count = [0]

        @retry(max_attempts=3, base_delay=0.01)
        async def eventually_succeeds():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("Transient error")
            return "success"

        result = await eventually_succeeds()
        assert result == "success"
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_exhausts_retries(self):
        """Test that retries are exhausted."""
        call_count = [0]

        @retry(max_attempts=3, base_delay=0.01)
        async def always_fails():
            call_count[0] += 1
            raise ValueError("Persistent error")

        with pytest.raises(RetryError):
            await always_fails()

        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_retry_on_specific_exceptions(self):
        """Test retry only on specific exceptions."""
        call_count = [0]

        @retry(
            max_attempts=3,
            base_delay=0.01,
            retry_on=(ConnectionError,),
        )
        async def fails_with_value_error():
            call_count[0] += 1
            raise ValueError("Not retriable")

        with pytest.raises(ValueError):
            await fails_with_value_error()

        # Should not retry on ValueError
        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_excluded(self):
        """Test no retry on excluded exceptions."""
        call_count = [0]

        @retry(
            max_attempts=3,
            base_delay=0.01,
            no_retry_on=(ValueError,),
        )
        async def fails_with_value_error():
            call_count[0] += 1
            raise ValueError("Excluded")

        with pytest.raises(ValueError):
            await fails_with_value_error()

        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_preserves_function_return(self):
        """Test that return value is preserved."""

        @retry(max_attempts=3)
        async def returns_dict():
            return {"key": "value", "count": 42}

        result = await returns_dict()
        assert result == {"key": "value", "count": 42}

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """Test that decorated function name is preserved."""

        @retry(max_attempts=3)
        async def my_named_function():
            return "test"

        assert my_named_function.__name__ == "my_named_function"


class TestRetryError:
    """Tests for RetryError exception."""

    def test_error_message(self):
        """Test RetryError message."""
        last_exc = ValueError("Test error")
        error = RetryError(
            message="All attempts exhausted",
            last_exception=last_exc,
            attempts=3,
            total_delay=2.5,
        )
        assert "exhausted" in str(error).lower()
        assert error.attempts == 3
        assert error.total_delay == pytest.approx(2.5)


class TestRetryConfiguration:
    """Tests for retry configuration."""

    @pytest.mark.asyncio
    async def test_custom_max_attempts(self):
        """Test custom max attempts."""
        call_count = [0]

        @retry(max_attempts=5, base_delay=0.001)
        async def always_fails():
            call_count[0] += 1
            raise ValueError()

        with pytest.raises(RetryError):
            await always_fails()

        assert call_count[0] == 5

    @pytest.mark.asyncio
    async def test_delay_between_retries(self):
        """Test that delays occur between retries."""
        import time

        timestamps = []

        @retry(max_attempts=3, base_delay=0.05, jitter=False)
        async def fails_twice():
            timestamps.append(time.time())
            if len(timestamps) < 3:
                raise ValueError()
            return "success"

        await fails_twice()

        # Check delays exist (with some tolerance)
        if len(timestamps) >= 2:
            delay = timestamps[1] - timestamps[0]
            assert delay >= 0.01  # At least some delay


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_from_settings(self):
        """Test RetryConfig.from_settings creates config from settings."""
        config = RetryConfig.from_settings()
        assert config.max_attempts > 0
        assert config.base_delay > 0
        assert config.max_delay >= config.base_delay

    def test_default_values(self):
        """Test RetryConfig default values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == pytest.approx(1.0)
        assert config.jitter is True


class TestRetrySyncDecorator:
    """Tests for retry_sync decorator."""

    def test_sync_success_no_retry(self):
        """Test successful sync call doesn't retry."""
        call_count = [0]

        @retry_sync(max_attempts=3)
        def successful():
            call_count[0] += 1
            return "success"

        result = successful()
        assert result == "success"
        assert call_count[0] == 1

    def test_sync_retry_on_failure(self):
        """Test sync retry on transient failure."""
        call_count = [0]

        @retry_sync(max_attempts=3, base_delay=0.01)
        def eventually_succeeds():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("Transient error")
            return "success"

        result = eventually_succeeds()
        assert result == "success"
        assert call_count[0] == 2

    def test_sync_exhausts_retries(self):
        """Test that sync retries are exhausted."""
        call_count = [0]

        @retry_sync(max_attempts=3, base_delay=0.01)
        def always_fails():
            call_count[0] += 1
            raise ValueError("Persistent error")

        with pytest.raises(RetryError):
            always_fails()

        assert call_count[0] == 3

    def test_sync_no_retry_on_excluded(self):
        """Test sync no retry on excluded exceptions."""
        call_count = [0]

        @retry_sync(
            max_attempts=3,
            base_delay=0.01,
            no_retry_on=(ValueError,),
        )
        def fails_with_value_error():
            call_count[0] += 1
            raise ValueError("Excluded")

        with pytest.raises(ValueError):
            fails_with_value_error()

        assert call_count[0] == 1

    def test_sync_preserves_function_name(self):
        """Test that sync decorated function name is preserved."""

        @retry_sync(max_attempts=3)
        def my_sync_function():
            return "test"

        assert my_sync_function.__name__ == "my_sync_function"


class TestIsPermanentHttpFailure:
    """Tests for _is_permanent_http_failure helper."""

    def test_returns_false_for_generic_exception(self):
        """Generic exceptions are not permanent HTTP failures."""
        assert _is_permanent_http_failure(ValueError("oops")) is False

    def test_returns_false_for_runtime_error(self):
        """RuntimeError is not a permanent HTTP failure."""
        assert _is_permanent_http_failure(RuntimeError("oops")) is False

    def test_httpstatuserror_with_permanent_status(self):
        """HTTPStatusError with 400-class status is permanent."""
        from unittest.mock import MagicMock

        class HTTPStatusError(Exception):
            pass

        exc = HTTPStatusError("request error")
        exc.response = MagicMock()
        exc.response.status_code = 404
        assert _is_permanent_http_failure(exc) is True

    def test_httpstatuserror_with_transient_status(self):
        """HTTPStatusError with 503 status is not permanent."""
        from unittest.mock import MagicMock

        class HTTPStatusError(Exception):
            pass

        exc = HTTPStatusError("server error")
        exc.response = MagicMock()
        exc.response.status_code = 503
        assert _is_permanent_http_failure(exc) is False

    def test_httpstatuserror_with_429_not_permanent(self):
        """HTTPStatusError with 429 (rate limit) is not permanent."""
        from unittest.mock import MagicMock

        class HTTPStatusError(Exception):
            pass

        exc = HTTPStatusError("rate limit")
        exc.response = MagicMock()
        exc.response.status_code = 429
        assert _is_permanent_http_failure(exc) is False

    def test_httpstatuserror_attribute_error_on_response(self):
        """HTTPStatusError where response.status_code raises AttributeError → not permanent."""
        from unittest.mock import MagicMock, PropertyMock

        class HTTPStatusError(Exception):
            pass

        exc = HTTPStatusError("bad response")
        response_mock = MagicMock()
        type(response_mock).status_code = PropertyMock(side_effect=AttributeError("no attr"))
        exc.response = response_mock
        result = _is_permanent_http_failure(exc)
        assert result is False

    def test_httperror_with_permanent_status(self):
        """HTTPError (requests) with permanent status returns True."""
        from unittest.mock import MagicMock

        class HTTPError(Exception):
            pass

        exc = HTTPError("request error")
        exc.response = MagicMock()
        exc.response.status_code = 422
        assert _is_permanent_http_failure(exc) is True

    def test_httperror_with_transient_status(self):
        """HTTPError with 500 is not permanent."""
        from unittest.mock import MagicMock

        class HTTPError(Exception):
            pass

        exc = HTTPError("server error")
        exc.response = MagicMock()
        exc.response.status_code = 500
        assert _is_permanent_http_failure(exc) is False

    def test_httperror_no_response(self):
        """HTTPError with no response attribute → not permanent."""

        class HTTPError(Exception):
            pass

        exc = HTTPError("error")
        exc.response = None
        assert _is_permanent_http_failure(exc) is False

    def test_httperror_attribute_error_on_response(self):
        """HTTPError where response attribute raises AttributeError → not permanent."""
        from unittest.mock import MagicMock, PropertyMock

        class HTTPError(Exception):
            pass

        exc = HTTPError("bad response")
        # Make getattr(exc, "response", None) work but status_code raise
        resp_mock = MagicMock()
        type(resp_mock).status_code = PropertyMock(side_effect=AttributeError("no attr"))
        exc.response = resp_mock
        result = _is_permanent_http_failure(exc)
        assert result is False


class TestShouldRetry:
    """Tests for should_retry helper."""

    def test_permanent_http_failure_returns_false(self):
        """should_retry returns False for permanent HTTP client errors."""
        from unittest.mock import MagicMock

        class HTTPStatusError(Exception):
            pass

        exc = HTTPStatusError("403 Forbidden")
        exc.response = MagicMock()
        exc.response.status_code = 403
        config = RetryConfig(retry_on=(Exception,))
        # Even though retry_on=(Exception,), permanent HTTP errors short-circuit
        assert should_retry(exc, config) is False

    def test_transient_error_returns_true(self):
        """should_retry returns True for transient errors in retry_on."""
        config = RetryConfig(retry_on=(ConnectionError,))
        assert should_retry(ConnectionError("timeout"), config) is True

    def test_no_retry_on_excluded(self):
        """should_retry returns False for excluded exceptions."""
        config = RetryConfig(retry_on=(Exception,), no_retry_on=(ValueError,))
        assert should_retry(ValueError("excluded"), config) is False

    def test_not_in_retry_on_returns_false(self):
        """should_retry returns False for errors not in retry_on."""
        config = RetryConfig(retry_on=(ConnectionError,))
        assert should_retry(ValueError("not in list"), config) is False
