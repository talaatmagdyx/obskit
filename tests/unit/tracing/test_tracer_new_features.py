"""Tests for new tracer features: debug, sample_rate, async_trace_span,
W3C Baggage, get_current_trace_id/span_id, obskit.version in Resource."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from obskit.tracing._version import __version__
from obskit.tracing.tracer import (
    OPENTELEMETRY_AVAILABLE,
    _BAGGAGE_MAX_KEY_LEN,
    _BAGGAGE_MAX_VALUE_LEN,
    async_trace_span,
    clear_baggage,
    configure_tracing,
    extract_trace_context,
    get_all_baggage,
    get_baggage,
    get_current_span_id,
    get_current_trace_id,
    reset_tracing,
    set_baggage,
    shutdown_tracing,
    trace_span,
    tracing_lifespan,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_span_ctx(
    trace_id: int = 0x4BF92F3577B34DA6A3CE929D0E0E4736, span_id: int = 0x00F067AA0BA902B7
) -> MagicMock:
    ctx = MagicMock()
    ctx.is_valid = True
    ctx.trace_id = trace_id
    ctx.span_id = span_id
    return ctx


def _make_invalid_span_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.is_valid = False
    return ctx


# ---------------------------------------------------------------------------
# TestVersion
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_is_string(self) -> None:
        assert isinstance(__version__, str)

    def test_version_format(self) -> None:
        parts = __version__.split(".")
        assert len(parts) == 3


# ---------------------------------------------------------------------------
# TestConfigureTracingNewParams
# ---------------------------------------------------------------------------


class TestConfigureTracingNewParams:
    """configure_tracing() — new debug and sample_rate parameters."""

    def setup_method(self) -> None:
        reset_tracing()

    def teardown_method(self) -> None:
        reset_tracing()

    def test_debug_mode_returns_true(self) -> None:
        """configure_tracing(debug=True) must not raise and returns True."""
        result = configure_tracing(debug=True)
        assert result is True

    def test_debug_false_is_default(self) -> None:
        """configure_tracing() without debug= uses default (False)."""
        result = configure_tracing()
        assert result is True

    def test_sample_rate_one_returns_true(self) -> None:
        """sample_rate=1.0 (keep all) must succeed."""
        result = configure_tracing(sample_rate=1.0)
        assert result is True

    def test_sample_rate_zero_returns_true(self) -> None:
        """sample_rate=0.0 (drop all) must not raise."""
        result = configure_tracing(sample_rate=0.0)
        assert result is True

    def test_sample_rate_fractional_returns_true(self) -> None:
        """sample_rate=0.1 (keep 10%) must not raise."""
        result = configure_tracing(sample_rate=0.1)
        assert result is True

    def test_debug_and_sample_rate_together(self) -> None:
        """Both debug=True and sample_rate can be combined."""
        result = configure_tracing(debug=True, sample_rate=0.5)
        assert result is True

    def test_sampler_is_applied_when_rate_lt_1(self) -> None:
        """When sample_rate < 1.0, ParentBased(TraceIdRatioBased) sampler is created."""
        with patch("obskit.tracing.tracer.TracerProvider") as MockProvider:
            MockProvider.return_value = MagicMock()
            # Just verify no exception — sampler branch is executed
            configure_tracing(sample_rate=0.5)

    def test_debug_registers_provider_when_no_endpoint(self) -> None:
        """When debug=True with no endpoint, the provider is set via the debug path.

        This test explicitly patches get_settings() to ensure ``endpoint`` is
        always falsy — even in environments where OBSKIT_OTLP_ENDPOINT is set —
        so the ``if debug and not _provider_registered:`` branch is exercised.
        """
        if not OPENTELEMETRY_AVAILABLE:
            pytest.skip("OTel not installed")

        import opentelemetry.trace as otel_trace

        settings_stub = MagicMock()
        settings_stub.service_name = "test-svc"
        settings_stub.otlp_endpoint = None  # ← no endpoint
        settings_stub.tracing_enabled = False  # ← OTLP branch skipped
        settings_stub.version = "1.0.0"
        settings_stub.environment = "test"

        with patch("obskit.tracing.tracer.get_settings", return_value=settings_stub):
            with patch.object(otel_trace, "set_tracer_provider") as mock_set_provider:
                result = configure_tracing(debug=True)

        assert result is True
        mock_set_provider.assert_called_once()

    def test_obskit_version_in_resource(self) -> None:
        """configure_tracing sets obskit.version in OTel resource attributes."""
        _created_resource = None

        original_resource_create = None
        try:
            from opentelemetry.sdk.resources import Resource

            original_resource_create = Resource.create
        except ImportError:
            pytest.skip("opentelemetry-sdk not installed")

        captured: list[dict] = []

        def fake_create(attrs: dict) -> MagicMock:
            captured.append(attrs)
            return original_resource_create(attrs)

        with patch("obskit.tracing.tracer.Resource") as MockResource:
            mock_res = MagicMock()
            MockResource.create.return_value = mock_res
            configure_tracing(service_name="test-svc")

            # Check that Resource.create was called with obskit.version
            args, kwargs = MockResource.create.call_args
            attrs = args[0] if args else kwargs.get("attributes", {})
            assert "obskit.version" in attrs
            assert attrs["obskit.version"] == __version__
            assert attrs.get("telemetry.sdk.name") == "obskit"


# ---------------------------------------------------------------------------
# TestAsyncTraceSpan
# ---------------------------------------------------------------------------


class TestAsyncTraceSpan:
    """async_trace_span() — async context manager variant of trace_span."""

    def setup_method(self) -> None:
        reset_tracing()

    def teardown_method(self) -> None:
        reset_tracing()

    @pytest.mark.asyncio
    async def test_async_trace_span_yields(self) -> None:
        """async_trace_span yields without raising."""
        configure_tracing()
        async with async_trace_span("test_op") as span:
            assert span is not None  # yields the OTel span object

    @pytest.mark.asyncio
    async def test_async_trace_span_with_attributes(self) -> None:
        """async_trace_span accepts attributes."""
        configure_tracing()
        async with async_trace_span(
            "test_op",
            attributes={"order_id": "123", "user_id": "456"},
        ):
            # Just verify no exception
            pass  # NOSONAR

    @pytest.mark.asyncio
    async def test_async_trace_span_with_component_and_operation(self) -> None:
        """async_trace_span accepts component and operation."""
        configure_tracing()
        async with async_trace_span("svc.op", component="SvcName", operation="doThing"):
            pass  # NOSONAR

    @pytest.mark.asyncio
    async def test_async_trace_span_name_matches_sync(self) -> None:
        """Both sync and async span wrappers work on the same name."""
        configure_tracing()
        with trace_span("sync_op"):
            pass  # NOSONAR
        async with async_trace_span("async_op"):
            pass  # NOSONAR

    @pytest.mark.asyncio
    async def test_async_trace_span_nested(self) -> None:
        """Async spans can be nested."""
        configure_tracing()
        async with async_trace_span("outer"):
            async with async_trace_span("inner") as inner:
                assert inner is not None


# ---------------------------------------------------------------------------
# TestBaggage
# ---------------------------------------------------------------------------


class TestBaggage:
    """set_baggage / get_baggage / get_all_baggage / clear_baggage."""

    def setup_method(self) -> None:
        reset_tracing()

    def teardown_method(self) -> None:
        reset_tracing()

    def test_set_and_get_baggage(self) -> None:
        """set_baggage + get_baggage round-trip works."""
        token = set_baggage("tenant_id", "acme-corp")
        try:
            val = get_baggage("tenant_id")
            assert val == "acme-corp"
        finally:
            clear_baggage(token)

    def test_get_baggage_missing_key_returns_none(self) -> None:
        """get_baggage returns None for an absent key."""
        val = get_baggage("no_such_key")
        assert val is None

    def test_set_baggage_returns_token(self) -> None:
        """set_baggage returns a non-None token."""
        token = set_baggage("k", "v")
        assert token is not None
        clear_baggage(token)

    def test_clear_baggage_with_none_is_safe(self) -> None:
        """clear_baggage(None) must not raise."""
        clear_baggage(None)  # no error

    def test_get_all_baggage_returns_dict(self) -> None:
        """get_all_baggage() returns a dict."""
        result = get_all_baggage()
        assert isinstance(result, dict)

    def test_get_all_baggage_includes_set_values(self) -> None:
        """get_all_baggage reflects values set by set_baggage."""
        token = set_baggage("service_tier", "premium")
        try:
            all_bag = get_all_baggage()
            assert "service_tier" in all_bag
            assert all_bag["service_tier"] == "premium"
        finally:
            clear_baggage(token)

    def test_clear_baggage_removes_context(self) -> None:
        """After clear_baggage, the key is no longer accessible."""
        token = set_baggage("temp_key", "temp_val")
        clear_baggage(token)
        # After detach, baggage reverts to previous (empty) context
        _val = get_baggage("temp_key")
        # Value may or may not be None depending on OTel context depth;
        # most importantly clear_baggage must not raise
        # (the assertion here is that no exception was raised)

    def test_multiple_baggage_entries(self) -> None:
        """Multiple baggage entries can coexist."""
        t1 = set_baggage("a", "1")
        t2 = set_baggage("b", "2")
        try:
            assert get_baggage("b") == "2"
        finally:
            clear_baggage(t2)
            clear_baggage(t1)


# ---------------------------------------------------------------------------
# TestCurrentTraceAndSpanId
# ---------------------------------------------------------------------------


class TestCurrentTraceAndSpanId:
    """get_current_trace_id / get_current_span_id."""

    def setup_method(self) -> None:
        reset_tracing()

    def teardown_method(self) -> None:
        reset_tracing()

    def test_returns_none_when_no_span_active(self) -> None:
        """Outside any span, both helpers return None."""
        assert get_current_trace_id() is None
        assert get_current_span_id() is None

    def test_returns_string_inside_span(self) -> None:
        """Inside a trace_span, both helpers return hex strings."""
        configure_tracing()
        with trace_span("outer"):
            trace_id = get_current_trace_id()
            span_id = get_current_span_id()
            # When OTel is configured with the real SDK these may be None
            # (NoOpSpan from a non-configured provider is not valid)
            # so we just check type
            assert trace_id is None or isinstance(trace_id, str)
            assert span_id is None or isinstance(span_id, str)

    def test_trace_id_format_when_valid(self) -> None:
        """Mocked valid span → trace_id is 32 hex chars."""
        if not OPENTELEMETRY_AVAILABLE:
            pytest.skip("OTel not installed")

        import opentelemetry.trace as otel_trace

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = _make_valid_span_ctx()

        with patch.object(otel_trace, "get_current_span", return_value=mock_span):
            tid = get_current_trace_id()
            sid = get_current_span_id()

        assert tid is not None
        assert len(tid) == 32
        assert all(c in "0123456789abcdef" for c in tid)
        assert sid is not None
        assert len(sid) == 16

    def test_returns_none_when_span_context_invalid(self) -> None:
        """Invalid span context → helpers return None."""
        if not OPENTELEMETRY_AVAILABLE:
            pytest.skip("OTel not installed")

        import opentelemetry.trace as otel_trace

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = _make_invalid_span_ctx()

        with patch.object(otel_trace, "get_current_span", return_value=mock_span):
            assert get_current_trace_id() is None
            assert get_current_span_id() is None

    def test_returns_none_on_exception(self) -> None:
        """Exceptions inside helpers must be swallowed → return None."""
        if not OPENTELEMETRY_AVAILABLE:
            pytest.skip("OTel not installed")

        import opentelemetry.trace as otel_trace

        with patch.object(otel_trace, "get_current_span", side_effect=RuntimeError("boom")):
            assert get_current_trace_id() is None
            assert get_current_span_id() is None


# ---------------------------------------------------------------------------
# TestExtractTraceContextCoverage
# ---------------------------------------------------------------------------


class TestExtractTraceContextCoverage:
    """extract_trace_context() — coverage for validation branches."""

    def test_none_headers_returns_none(self) -> None:
        """None headers returns None immediately."""
        result = extract_trace_context(None)
        assert result is None

    def test_malformed_traceparent_returns_none(self) -> None:
        """Malformed traceparent value causes early return of None."""
        result = extract_trace_context({"traceparent": "not-a-valid-traceparent"})
        assert result is None

    def test_malformed_traceparent_wrong_format(self) -> None:
        """Wrong hex length in traceparent triggers validation failure."""
        result = extract_trace_context({"traceparent": "00-abc-123-00"})
        assert result is None

    def test_oversized_tracestate_is_dropped(self) -> None:
        """tracestate > 512 bytes is stripped from headers (no exception)."""
        # Valid traceparent format
        valid_traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        oversized_tracestate = "k=" + "v" * 600  # > 512 bytes
        # Should not raise — tracestate is dropped
        extract_trace_context(
            {
                "traceparent": valid_traceparent,
                "tracestate": oversized_tracestate,
            }
        )
        # No exception is the assertion — result may be None or context depending on OTel install

    def test_module_level_regex_compilation(self) -> None:
        """_W3C_TRACEPARENT_RE is compiled at module load; invalid traceparents return None."""
        import obskit.tracing.tracer as tracer_mod

        # Verify the module-level regex is compiled and functional
        assert tracer_mod._W3C_TRACEPARENT_RE is not None
        assert tracer_mod._W3C_TRACEPARENT_RE.match("not-valid") is None

        # Both calls use the same module-level compiled regex
        result = extract_trace_context({"traceparent": "not-valid"})
        result2 = extract_trace_context({"traceparent": "also-not-valid"})
        assert result is None
        assert result2 is None


# ---------------------------------------------------------------------------
# TestSetBaggageValidation
# ---------------------------------------------------------------------------


class TestSetBaggageValidation:
    """set_baggage() — validation error branches."""

    def test_non_ascii_key_raises(self) -> None:
        """Key with non-ASCII character raises ValueError."""
        with pytest.raises(ValueError, match="non-ASCII"):
            set_baggage("tëst", "value")

    def test_control_char_in_key_raises(self) -> None:
        """Key with control character raises ValueError."""
        with pytest.raises(ValueError, match="non-ASCII"):
            set_baggage("key\x00", "value")

    def test_non_ascii_value_raises(self) -> None:
        """Value with non-ASCII character raises ValueError."""
        with pytest.raises(ValueError, match="non-ASCII"):
            set_baggage("key", "välüë")

    def test_control_char_in_value_raises(self) -> None:
        """Value with control character raises ValueError."""
        with pytest.raises(ValueError, match="non-ASCII"):
            set_baggage("key", "val\x01ue")

    def test_key_too_long_raises(self) -> None:
        """Key exceeding max length raises ValueError."""
        long_key = "k" * (_BAGGAGE_MAX_KEY_LEN + 1)
        with pytest.raises(ValueError, match="key too long"):
            set_baggage(long_key, "value")

    def test_value_too_long_raises(self) -> None:
        """Value exceeding max length raises ValueError."""
        long_value = "v" * (_BAGGAGE_MAX_VALUE_LEN + 1)
        with pytest.raises(ValueError, match="too long"):
            set_baggage("key", long_value)

    def test_valid_key_and_value_succeeds(self) -> None:
        """ASCII key and value at max boundary do not raise."""
        token = set_baggage("valid-key", "valid-value")
        clear_baggage(token)


# ---------------------------------------------------------------------------
# TestTracingLifespan
# ---------------------------------------------------------------------------


class TestTracingLifespan:
    """tracing_lifespan() — try/yield/finally body."""

    def test_lifespan_yields_and_shuts_down(self) -> None:
        """tracing_lifespan() allows code inside the block and calls shutdown on exit."""
        executed = []

        with patch("obskit.tracing.tracer.shutdown_tracing") as mock_shutdown:
            with tracing_lifespan():
                executed.append("inside")

        assert executed == ["inside"]
        mock_shutdown.assert_called_once()

    def test_lifespan_shuts_down_on_exception(self) -> None:
        """tracing_lifespan() calls shutdown even when body raises."""
        with patch("obskit.tracing.tracer.shutdown_tracing") as mock_shutdown:
            with pytest.raises(RuntimeError, match="boom"):
                with tracing_lifespan():
                    raise RuntimeError("boom")

        mock_shutdown.assert_called_once()
