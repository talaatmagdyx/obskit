"""Unit tests for obskit.integrations.http — httpx instrumentation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestInstrumentHttpx:
    def test_returns_instrumented_client(self):
        from obskit.integrations.http import InstrumentedHttpxClient, instrument_httpx

        client = MagicMock()
        wrapped = instrument_httpx(client, name="test")
        assert isinstance(wrapped, InstrumentedHttpxClient)

    def test_default_name(self):
        from obskit.integrations.http import instrument_httpx

        wrapped = instrument_httpx(MagicMock())
        assert wrapped._name == "default"

    def test_stores_name(self):
        from obskit.integrations.http import instrument_httpx

        wrapped = instrument_httpx(MagicMock(), name="twitter")
        assert wrapped._name == "twitter"

    def test_non_http_attr_passed_through(self):
        from obskit.integrations.http import instrument_httpx

        client = MagicMock()
        client.base_url = "https://example.com"
        wrapped = instrument_httpx(client, name="t")
        assert wrapped.base_url == "https://example.com"

    def test_sync_attr_passed_through(self):
        """A callable that is NOT a coroutine function is returned as-is."""
        from obskit.integrations.http import instrument_httpx

        client = MagicMock()
        # 'get' is in _HTTP_METHODS, but make it non-async
        client.some_sync_method = MagicMock(return_value="sync")
        wrapped = instrument_httpx(client, name="t")
        assert wrapped.some_sync_method() == "sync"


class TestInstrumentedHttpxAsyncMethods:
    @pytest.mark.asyncio
    async def test_get_success_increments_counter(self):
        from obskit.integrations.http import HTTP_CLIENT_REQUESTS_TOTAL, instrument_httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        client = MagicMock()
        client.get = AsyncMock(return_value=mock_response)
        wrapped = instrument_httpx(client, name="c1")

        before = HTTP_CLIENT_REQUESTS_TOTAL.labels(
            name="c1", method="GET", status_code="200"
        )._value.get()
        await wrapped.get("https://example.com")
        after = HTTP_CLIENT_REQUESTS_TOTAL.labels(
            name="c1", method="GET", status_code="200"
        )._value.get()
        assert after == before + 1.0

    @pytest.mark.asyncio
    async def test_post_increments_counter(self):
        from obskit.integrations.http import HTTP_CLIENT_REQUESTS_TOTAL, instrument_httpx

        mock_response = MagicMock()
        mock_response.status_code = 201
        client = MagicMock()
        client.post = AsyncMock(return_value=mock_response)
        wrapped = instrument_httpx(client, name="c2")

        before = HTTP_CLIENT_REQUESTS_TOTAL.labels(
            name="c2", method="POST", status_code="201"
        )._value.get()
        await wrapped.post("https://example.com", json={})
        after = HTTP_CLIENT_REQUESTS_TOTAL.labels(
            name="c2", method="POST", status_code="201"
        )._value.get()
        assert after == before + 1.0

    @pytest.mark.asyncio
    async def test_exception_records_error_status(self):
        from obskit.integrations.http import HTTP_CLIENT_REQUESTS_TOTAL, instrument_httpx

        client = MagicMock()
        client.get = AsyncMock(side_effect=ConnectionError("network down"))
        wrapped = instrument_httpx(client, name="c3")

        before = HTTP_CLIENT_REQUESTS_TOTAL.labels(
            name="c3", method="GET", status_code="error"
        )._value.get()
        with pytest.raises(ConnectionError):
            await wrapped.get("https://example.com")
        after = HTTP_CLIENT_REQUESTS_TOTAL.labels(
            name="c3", method="GET", status_code="error"
        )._value.get()
        assert after == before + 1.0

    @pytest.mark.asyncio
    async def test_duration_recorded(self):
        from obskit.integrations.http import HTTP_CLIENT_DURATION_SECONDS, instrument_httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        client = MagicMock()
        client.put = AsyncMock(return_value=mock_response)
        wrapped = instrument_httpx(client, name="c4")

        hist = HTTP_CLIENT_DURATION_SECONDS.labels(name="c4", method="PUT")
        before = hist._sum.get()
        await wrapped.put("https://example.com", json={})
        after = hist._sum.get()
        assert after > before

    @pytest.mark.asyncio
    async def test_result_passed_through(self):
        from obskit.integrations.http import instrument_httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        client = MagicMock()
        client.get = AsyncMock(return_value=mock_response)
        wrapped = instrument_httpx(client, name="c5")

        result = await wrapped.get("https://example.com")
        assert result is mock_response

    @pytest.mark.asyncio
    async def test_request_method_extracted_from_first_arg(self):
        """The generic request(method, url, ...) form uses args[0] as method label."""
        from obskit.integrations.http import HTTP_CLIENT_REQUESTS_TOTAL, instrument_httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        client = MagicMock()
        client.request = AsyncMock(return_value=mock_response)
        wrapped = instrument_httpx(client, name="c6")

        before = HTTP_CLIENT_REQUESTS_TOTAL.labels(
            name="c6", method="DELETE", status_code="200"
        )._value.get()
        await wrapped.request("DELETE", "https://example.com/resource/1")
        after = HTTP_CLIENT_REQUESTS_TOTAL.labels(
            name="c6", method="DELETE", status_code="200"
        )._value.get()
        assert after == before + 1.0

    @pytest.mark.asyncio
    async def test_headers_dict_created_when_absent(self):
        """If headers not in kwargs, an empty dict is created for injection."""
        from obskit.integrations.http import instrument_httpx

        captured_kwargs: dict = {}

        async def fake_get(*args, **kwargs):
            captured_kwargs.update(kwargs)
            resp = MagicMock()
            resp.status_code = 200
            return resp

        client = MagicMock()
        client.get = fake_get
        wrapped = instrument_httpx(client, name="c7")

        await wrapped.get("https://example.com")
        assert "headers" in captured_kwargs
        assert isinstance(captured_kwargs["headers"], dict)

    @pytest.mark.asyncio
    async def test_non_dict_headers_converted(self):
        """Headers passed as list-of-tuples are converted to dict."""
        from obskit.integrations.http import instrument_httpx

        captured_kwargs: dict = {}

        async def fake_get(*args, **kwargs):
            captured_kwargs.update(kwargs)
            resp = MagicMock()
            resp.status_code = 200
            return resp

        client = MagicMock()
        client.get = fake_get
        wrapped = instrument_httpx(client, name="c8")

        await wrapped.get("https://example.com", headers=[("x-custom", "val")])
        assert isinstance(captured_kwargs["headers"], dict)
        assert captured_kwargs["headers"]["x-custom"] == "val"

    @pytest.mark.asyncio
    async def test_traceparent_injected(self):
        """inject_trace_context is called with the headers dict."""
        from obskit.integrations.http import instrument_httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        client = MagicMock()
        client.get = AsyncMock(return_value=mock_response)
        wrapped = instrument_httpx(client, name="c9")

        with patch("obskit.tracing.tracer.inject_trace_context") as mock_inject:
            await wrapped.get("https://example.com")
            mock_inject.assert_called_once()
            # First arg to inject must be a dict
            injected_headers = mock_inject.call_args[0][0]
            assert isinstance(injected_headers, dict)

    @pytest.mark.asyncio
    async def test_all_http_methods_wrapped(self):
        """put, patch, delete, head, options are all instrumented."""
        from obskit.integrations.http import HTTP_CLIENT_REQUESTS_TOTAL, instrument_httpx

        for http_method in ("put", "patch", "delete", "head", "options"):
            mock_response = MagicMock()
            mock_response.status_code = 200
            client = MagicMock()
            setattr(client, http_method, AsyncMock(return_value=mock_response))
            wrapped = instrument_httpx(client, name=f"m-{http_method}")

            before = HTTP_CLIENT_REQUESTS_TOTAL.labels(
                name=f"m-{http_method}",
                method=http_method.upper(),
                status_code="200",
            )._value.get()
            await getattr(wrapped, http_method)("https://example.com")
            after = HTTP_CLIENT_REQUESTS_TOTAL.labels(
                name=f"m-{http_method}",
                method=http_method.upper(),
                status_code="200",
            )._value.get()
            assert after == before + 1.0


class TestInstrumentedHttpxContextManager:
    @pytest.mark.asyncio
    async def test_aenter_returns_instrumented_client(self):
        from obskit.integrations.http import InstrumentedHttpxClient, instrument_httpx

        inner_client = AsyncMock()
        inner_client.__aenter__ = AsyncMock(return_value=inner_client)
        inner_client.__aexit__ = AsyncMock(return_value=None)

        wrapped = instrument_httpx(inner_client, name="ctx")

        async with wrapped as c:
            assert isinstance(c, InstrumentedHttpxClient)

    @pytest.mark.asyncio
    async def test_aexit_calls_underlying_aexit(self):
        from obskit.integrations.http import instrument_httpx

        inner_client = AsyncMock()
        inner_client.__aenter__ = AsyncMock(return_value=inner_client)
        inner_client.__aexit__ = AsyncMock(return_value=None)

        wrapped = instrument_httpx(inner_client, name="ctx2")

        async with wrapped:
            pass

        inner_client.__aexit__.assert_called_once()


class TestHttpxPublicAPI:
    def test_all_exports_present(self):
        import obskit.integrations.http as m

        for name in (
            "InstrumentedHttpxClient",
            "instrument_httpx",
            "HTTP_CLIENT_REQUESTS_TOTAL",
            "HTTP_CLIENT_DURATION_SECONDS",
        ):
            assert hasattr(m, name), f"missing export: {name}"
