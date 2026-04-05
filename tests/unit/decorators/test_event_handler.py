"""Unit tests for obskit.decorators.event_handler."""

from __future__ import annotations

import asyncio

import pytest


class TestInstrumentEventHandlerBasics:
    def test_returns_callable(self):
        from obskit.decorators.event_handler import instrument_event_handler

        decorator = instrument_event_handler(name="test_basic")
        assert callable(decorator)

    def test_wraps_async_function(self):
        from obskit.decorators.event_handler import instrument_event_handler

        @instrument_event_handler(name="test_wrap")
        async def handle(event: dict) -> str:
            return "ok"

        assert asyncio.iscoroutinefunction(handle)

    def test_preserves_function_name(self):
        from obskit.decorators.event_handler import instrument_event_handler

        @instrument_event_handler(name="test_name_preserve")
        async def handle(event: dict) -> None:
            pass

        assert handle.__name__ == "handle"

    def test_returns_function_result(self):
        from obskit.decorators.event_handler import instrument_event_handler

        @instrument_event_handler(name="test_result")
        async def handle(event: dict) -> str:
            return "processed"

        result = asyncio.run(handle({}))
        assert result == "processed"


class TestEventHandlerDurationHistogram:
    def test_duration_recorded_on_success(self):
        from obskit.decorators.event_handler import (
            EVENT_HANDLER_DURATION_SECONDS,
            instrument_event_handler,
        )

        @instrument_event_handler(name="t_dur_ok")
        async def handle(event: dict) -> None:
            pass

        before = EVENT_HANDLER_DURATION_SECONDS.labels(
            name="t_dur_ok"
        )._sum.get()
        asyncio.run(handle({}))
        after = EVENT_HANDLER_DURATION_SECONDS.labels(name="t_dur_ok")._sum.get()
        assert after > before

    def test_duration_recorded_on_exception(self):
        """Duration is always recorded even when handler raises."""
        from obskit.decorators.event_handler import (
            EVENT_HANDLER_DURATION_SECONDS,
            instrument_event_handler,
        )

        @instrument_event_handler(name="t_dur_err")
        async def handle(event: dict) -> None:
            raise ValueError("oops")

        before = EVENT_HANDLER_DURATION_SECONDS.labels(
            name="t_dur_err"
        )._sum.get()
        with pytest.raises(ValueError):
            asyncio.run(handle({}))
        after = EVENT_HANDLER_DURATION_SECONDS.labels(name="t_dur_err")._sum.get()
        assert after > before

    def test_duration_accumulates_across_calls(self):
        from obskit.decorators.event_handler import (
            EVENT_HANDLER_DURATION_SECONDS,
            instrument_event_handler,
        )

        @instrument_event_handler(name="t_dur_count")
        async def handle(event: dict) -> None:
            pass

        hist = EVENT_HANDLER_DURATION_SECONDS.labels(name="t_dur_count")
        before = hist._sum.get()
        asyncio.run(handle({}))
        asyncio.run(handle({}))
        after = hist._sum.get()
        # Two observations — sum must have increased
        assert after > before


class TestEventHandlerErrorCounter:
    def test_error_counter_increments_on_exception(self):
        from obskit.decorators.event_handler import (
            EVENT_HANDLER_ERRORS_TOTAL,
            instrument_event_handler,
        )

        @instrument_event_handler(name="t_err_inc")
        async def handle(event: dict) -> None:
            raise RuntimeError("handler failed")

        before = EVENT_HANDLER_ERRORS_TOTAL.labels(name="t_err_inc")._value.get()
        with pytest.raises(RuntimeError):
            asyncio.run(handle({}))
        after = EVENT_HANDLER_ERRORS_TOTAL.labels(name="t_err_inc")._value.get()
        assert after == before + 1.0

    def test_error_counter_not_incremented_on_success(self):
        from obskit.decorators.event_handler import (
            EVENT_HANDLER_ERRORS_TOTAL,
            instrument_event_handler,
        )

        @instrument_event_handler(name="t_err_ok")
        async def handle(event: dict) -> None:
            pass

        before = EVENT_HANDLER_ERRORS_TOTAL.labels(name="t_err_ok")._value.get()
        asyncio.run(handle({}))
        after = EVENT_HANDLER_ERRORS_TOTAL.labels(name="t_err_ok")._value.get()
        assert after == before

    def test_exception_is_reraised(self):
        from obskit.decorators.event_handler import instrument_event_handler

        @instrument_event_handler(name="t_reraise")
        async def handle(event: dict) -> None:
            raise ValueError("original error")

        with pytest.raises(ValueError, match="original error"):
            asyncio.run(handle({}))

    def test_multiple_errors_accumulate(self):
        from obskit.decorators.event_handler import (
            EVENT_HANDLER_ERRORS_TOTAL,
            instrument_event_handler,
        )

        @instrument_event_handler(name="t_err_multi")
        async def handle(event: dict) -> None:
            raise RuntimeError("fail")

        before = EVENT_HANDLER_ERRORS_TOTAL.labels(name="t_err_multi")._value.get()
        for _ in range(3):
            with pytest.raises(RuntimeError):
                asyncio.run(handle({}))
        after = EVENT_HANDLER_ERRORS_TOTAL.labels(name="t_err_multi")._value.get()
        assert after == before + 3.0


class TestEventHandlerSpan:
    def test_span_name_uses_event_handler_prefix(self):
        """Span is named 'event_handler.<name>' — verify via async_trace_span mock."""
        from unittest.mock import patch

        from obskit.decorators.event_handler import instrument_event_handler

        span_names = []

        class _FakeCtx:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *args):
                pass

        def _fake_span(name, **kwargs):
            span_names.append(name)
            return _FakeCtx()

        @instrument_event_handler(name="order_created")
        async def handle(event: dict) -> None:
            pass

        with patch("obskit.tracing.tracer.async_trace_span", side_effect=_fake_span):
            asyncio.run(handle({}))

        assert "event_handler.order_created" in span_names

    def test_works_with_self_argument(self):
        """Decorator works correctly on class methods."""
        from obskit.decorators.event_handler import (
            EVENT_HANDLER_ERRORS_TOTAL,
            instrument_event_handler,
        )

        class Handler:
            @instrument_event_handler(name="t_method")
            async def handle(self, event: dict) -> str:
                return "done"

        h = Handler()
        result = asyncio.run(h.handle({"key": "val"}))
        assert result == "done"


class TestPublicAPI:
    def test_all_exports_present(self):
        import obskit.decorators.event_handler as m

        for name in (
            "instrument_event_handler",
            "EVENT_HANDLER_DURATION_SECONDS",
            "EVENT_HANDLER_ERRORS_TOTAL",
        ):
            assert hasattr(m, name), f"missing: {name}"

    def test_top_level_export(self):
        import obskit

        assert "instrument_event_handler" in obskit.__all__
