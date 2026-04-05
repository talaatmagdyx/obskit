"""Unit tests for obskit.logging.event_context — with_event_context decorator."""

from __future__ import annotations

import pytest
from structlog.contextvars import clear_contextvars


@pytest.fixture(autouse=True)
def _clean_ctx():
    clear_contextvars()
    yield
    clear_contextvars()


class TestWithEventContext:
    @pytest.mark.asyncio
    async def test_binds_context_inside_handler(self):
        from structlog.contextvars import get_contextvars

        from obskit.logging.event_context import with_event_context

        @with_event_context(lambda e: {"company_id": e.get("company_id")})
        async def handle(event: dict) -> dict:
            return get_contextvars()

        result = await handle({"company_id": "acme"})
        assert result["company_id"] == "acme"

    @pytest.mark.asyncio
    async def test_unbinds_context_after_handler(self):
        from structlog.contextvars import get_contextvars

        from obskit.logging.event_context import with_event_context

        @with_event_context(lambda e: {"company_id": e.get("company_id")})
        async def handle(event: dict) -> None:
            pass

        await handle({"company_id": "acme"})
        assert "company_id" not in get_contextvars()

    @pytest.mark.asyncio
    async def test_unbinds_on_exception(self):
        from structlog.contextvars import get_contextvars

        from obskit.logging.event_context import with_event_context

        @with_event_context(lambda e: {"company_id": e.get("company_id")})
        async def handle(event: dict) -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await handle({"company_id": "acme"})

        assert "company_id" not in get_contextvars()

    @pytest.mark.asyncio
    async def test_works_with_method_handler(self):
        """Typical usage: async def handle(self, event) → event is second arg."""
        from structlog.contextvars import get_contextvars

        from obskit.logging.event_context import with_event_context

        class Worker:
            @with_event_context(
                lambda e: {
                    "company_id": str(e.get("company_id", "")),
                    "schema": e.get("schema", ""),
                }
            )
            async def handle(self, event: dict) -> dict:
                return get_contextvars()

        w = Worker()
        result = await w.handle({"company_id": "42", "schema": "acme_db"})
        assert result["company_id"] == "42"
        assert result["schema"] == "acme_db"

    @pytest.mark.asyncio
    async def test_event_from_kwarg(self):
        """If event is not a positional dict, fall back to kwarg 'event'."""
        from structlog.contextvars import get_contextvars

        from obskit.logging.event_context import with_event_context

        @with_event_context(lambda e: {"tenant": e.get("tenant")})
        async def handle(*, event: dict) -> dict:
            return get_contextvars()

        result = await handle(event={"tenant": "globex"})
        assert result["tenant"] == "globex"

    @pytest.mark.asyncio
    async def test_empty_extractor_result_skips_binding(self):
        """If extractor returns {} or None, no binding happens."""
        from structlog.contextvars import get_contextvars

        from obskit.logging.event_context import with_event_context

        @with_event_context(lambda e: {})
        async def handle(event: dict) -> dict:
            return get_contextvars()

        result = await handle({"company_id": "acme"})
        assert result == {}

    @pytest.mark.asyncio
    async def test_none_extractor_result_skips_binding(self):
        """If extractor returns None, no binding happens."""
        from structlog.contextvars import get_contextvars

        from obskit.logging.event_context import with_event_context

        @with_event_context(lambda e: None)
        async def handle(event: dict) -> dict:
            return get_contextvars()

        result = await handle({"company_id": "acme"})
        assert result == {}

    @pytest.mark.asyncio
    async def test_does_not_unbind_unrelated_keys(self):
        """Keys bound before the handler are NOT removed on exit."""
        from structlog.contextvars import bind_contextvars, get_contextvars

        from obskit.logging.event_context import with_event_context

        bind_contextvars(persistent="outer")

        @with_event_context(lambda e: {"scoped": e.get("scoped")})
        async def handle(event: dict) -> None:
            pass

        await handle({"scoped": "temp"})

        ctx = get_contextvars()
        assert ctx["persistent"] == "outer"
        assert "scoped" not in ctx

    @pytest.mark.asyncio
    async def test_return_value_passed_through(self):
        from obskit.logging.event_context import with_event_context

        @with_event_context(lambda e: {"k": "v"})
        async def handle(event: dict) -> str:
            return "result"

        assert await handle({}) == "result"

    @pytest.mark.asyncio
    async def test_extractor_called_with_event_dict(self):
        from obskit.logging.event_context import with_event_context

        received = []

        def extractor(e):
            received.append(e)
            return {}

        @with_event_context(extractor)
        async def handle(event: dict) -> None:
            pass

        payload = {"company_id": "123", "action": "create"}
        await handle(payload)
        assert received == [payload]

    @pytest.mark.asyncio
    async def test_empty_args_uses_empty_event(self):
        """Handler called with no args uses empty dict for extractor."""
        from obskit.logging.event_context import with_event_context

        received = []

        @with_event_context(lambda e: received.append(e) or {})
        async def handle() -> None:
            pass

        await handle()
        assert received == [{}]


class TestWithEventContextPublicAPI:
    def test_importable(self):
        from obskit.logging.event_context import with_event_context

        assert callable(with_event_context)

    def test_all_exports(self):
        import obskit.logging.event_context as m

        assert "with_event_context" in m.__all__
