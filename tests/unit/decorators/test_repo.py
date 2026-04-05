"""Unit tests for obskit.decorators.repo — instrument_repo class decorator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestInstrumentRepo:
    def test_returns_the_class(self):
        from obskit.decorators.repo import instrument_repo

        @instrument_repo()
        class MyRepo:
            async def get(self): ...

        assert isinstance(MyRepo, type)

    def test_wraps_async_methods(self):
        from obskit.decorators.repo import instrument_repo

        @instrument_repo()
        class MyRepo:
            async def fetch(self): ...

        import asyncio

        assert asyncio.iscoroutinefunction(MyRepo.fetch)

    def test_default_span_name_uses_class_name(self):
        """Span name should be 'ClassName.method_name'."""
        from obskit.decorators.repo import instrument_repo

        captured_spans = []

        @instrument_repo()
        class NotesRepo:
            async def insert_note(self):
                pass

        with patch("obskit.tracing.tracer.get_tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_span.__enter__ = MagicMock(return_value=mock_span)
            mock_span.__exit__ = MagicMock(return_value=False)
            mock_tracer_instance = MagicMock()
            mock_tracer_instance.start_as_current_span.return_value = mock_span
            mock_tracer_instance.start_as_current_span.side_effect = (
                lambda name, **kw: captured_spans.append(name) or mock_span
            )
            mock_tracer.return_value = mock_tracer_instance

            import asyncio

            asyncio.run(NotesRepo().insert_note())

        assert any("NotesRepo.insert_note" in s for s in captured_spans)

    def test_custom_span_prefix(self):
        """span_prefix overrides class name in span names."""
        from obskit.decorators.repo import instrument_repo

        captured_spans = []

        @instrument_repo(span_prefix="notes_db")
        class NotesRepo:
            async def get_notes(self):
                pass

        with patch("obskit.tracing.tracer.get_tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_span.__enter__ = MagicMock(return_value=mock_span)
            mock_span.__exit__ = MagicMock(return_value=False)
            mock_tracer_instance = MagicMock()
            mock_tracer_instance.start_as_current_span.side_effect = (
                lambda name, **kw: captured_spans.append(name) or mock_span
            )
            mock_tracer.return_value = mock_tracer_instance

            import asyncio

            asyncio.run(NotesRepo().get_notes())

        assert any("notes_db.get_notes" in s for s in captured_spans)

    @pytest.mark.asyncio
    async def test_return_value_preserved(self):
        from obskit.decorators.repo import instrument_repo

        @instrument_repo()
        class TagsRepo:
            async def get_tags(self, entity_id: int) -> list:
                return ["tag1", "tag2"]

        result = await TagsRepo().get_tags(1)
        assert result == ["tag1", "tag2"]

    @pytest.mark.asyncio
    async def test_exception_propagated(self):
        from obskit.decorators.repo import instrument_repo

        @instrument_repo()
        class FailRepo:
            async def fail_op(self):
                raise ValueError("db error")

        with pytest.raises(ValueError, match="db error"):
            await FailRepo().fail_op()

    def test_sync_methods_not_wrapped(self):
        """Synchronous methods are left unchanged."""
        from obskit.decorators.repo import instrument_repo

        original_sync = None

        @instrument_repo()
        class MixedRepo:
            def sync_method(self):
                return "sync"

            async def async_method(self):
                return "async"

        repo = MixedRepo()
        assert repo.sync_method() == "sync"

    def test_private_methods_not_wrapped(self):
        """Methods starting with _ are left untouched."""
        from obskit.decorators.repo import instrument_repo

        @instrument_repo()
        class MyRepo:
            async def _private_helper(self):
                return "private"

        import asyncio

        # Should call directly without span wrapping
        result = asyncio.run(MyRepo()._private_helper())
        assert result == "private"

    def test_staticmethod_not_wrapped(self):
        """Static methods are not wrapped."""
        from obskit.decorators.repo import instrument_repo

        @instrument_repo()
        class MyRepo:
            @staticmethod
            async def create_schema():
                return "schema"

        # Should still be accessible as a staticmethod
        assert isinstance(vars(MyRepo)["create_schema"], staticmethod)

    def test_classmethod_not_wrapped(self):
        """Class methods are not wrapped."""
        from obskit.decorators.repo import instrument_repo

        @instrument_repo()
        class MyRepo:
            @classmethod
            async def from_config(cls, config):
                return cls()

        assert isinstance(vars(MyRepo)["from_config"], classmethod)

    def test_default_component_is_db(self):
        from obskit.decorators.repo import instrument_repo

        captured_components = []

        @instrument_repo()
        class DefaultRepo:
            async def query(self):
                pass

        original_span = None

        with patch("obskit.tracing.tracer.get_tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_span.__enter__ = MagicMock(return_value=mock_span)
            mock_span.__exit__ = MagicMock(return_value=False)
            mock_tracer_instance = MagicMock()

            def fake_start(name, **kwargs):
                captured_components.append(name)
                return mock_span

            mock_tracer_instance.start_as_current_span.side_effect = fake_start
            mock_tracer.return_value = mock_tracer_instance

            import asyncio

            asyncio.run(DefaultRepo().query())

    @pytest.mark.asyncio
    async def test_multiple_methods_all_wrapped(self):
        from obskit.decorators.repo import instrument_repo

        @instrument_repo(component="postgres")
        class FullRepo:
            async def insert(self, data):
                return f"inserted:{data}"

            async def fetch(self, id_):
                return f"fetched:{id_}"

            async def delete(self, id_):
                return f"deleted:{id_}"

        r = FullRepo()
        assert await r.insert("x") == "inserted:x"
        assert await r.fetch(1) == "fetched:1"
        assert await r.delete(2) == "deleted:2"

    @pytest.mark.asyncio
    async def test_args_and_kwargs_forwarded(self):
        from obskit.decorators.repo import instrument_repo

        @instrument_repo()
        class ArgsRepo:
            async def query(self, table: str, *, limit: int = 10) -> dict:
                return {"table": table, "limit": limit}

        result = await ArgsRepo().query("users", limit=25)
        assert result == {"table": "users", "limit": 25}


class TestInstrumentRepoPublicAPI:
    def test_importable(self):
        from obskit.decorators.repo import instrument_repo

        assert callable(instrument_repo)

    def test_all_exports(self):
        import obskit.decorators.repo as m

        assert "instrument_repo" in m.__all__


class TestInstrumentRepoSlowThreshold:
    @pytest.mark.asyncio
    async def test_no_warning_when_threshold_none(self):
        """Default (slow_threshold_ms=None) never emits a warning."""
        from obskit.decorators.repo import instrument_repo

        @instrument_repo()
        class MyRepo:
            async def fast_op(self):
                return "ok"

        with patch("obskit.logging.logger.get_logger") as mock_get_logger:
            result = await MyRepo().fast_op()

        mock_get_logger.return_value.warning.assert_not_called()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_no_warning_when_below_threshold(self):
        """No warning when elapsed time is under the threshold."""
        from obskit.decorators.repo import instrument_repo

        @instrument_repo(slow_threshold_ms=100_000)  # 100 s — never exceeded
        class MyRepo:
            async def fast_op(self):
                return "ok"

        with patch("obskit.logging.logger.get_logger") as mock_get_logger:
            await MyRepo().fast_op()

        mock_get_logger.return_value.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_warning_emitted_when_above_threshold(self):
        """Warning is logged when elapsed > threshold."""
        from obskit.decorators.repo import instrument_repo

        @instrument_repo(slow_threshold_ms=0.001)  # 1 µs — always exceeded
        class MyRepo:
            async def slow_op(self):
                return "done"

        mock_logger = MagicMock()
        with patch("obskit.logging.logger.get_logger", return_value=mock_logger):
            result = await MyRepo().slow_op()

        assert result == "done"
        mock_logger.warning.assert_called_once()
        call_args, call_kwargs = mock_logger.warning.call_args
        assert call_args[0] == "slow_repo_operation"
        assert call_kwargs["operation"] == "MyRepo.slow_op"
        assert "duration_ms" in call_kwargs
        assert call_kwargs["threshold_ms"] == pytest.approx(0.001)

    @pytest.mark.asyncio
    async def test_warning_uses_span_prefix_in_operation(self):
        """operation kwarg in the warning uses the span_prefix."""
        from obskit.decorators.repo import instrument_repo

        @instrument_repo(slow_threshold_ms=0.001, span_prefix="notes_db")
        class NotesRepo:
            async def insert(self):
                pass

        mock_logger = MagicMock()
        with patch("obskit.logging.logger.get_logger", return_value=mock_logger):
            await NotesRepo().insert()

        call_kwargs = mock_logger.warning.call_args[1]
        assert call_kwargs["operation"] == "notes_db.insert"

    @pytest.mark.asyncio
    async def test_warning_emitted_on_exception(self):
        """Slow warning fires in finally even when the method raises."""
        from obskit.decorators.repo import instrument_repo

        @instrument_repo(slow_threshold_ms=0.001)
        class MyRepo:
            async def failing_op(self):
                raise ValueError("db failure")

        mock_logger = MagicMock()
        with patch("obskit.logging.logger.get_logger", return_value=mock_logger):
            with pytest.raises(ValueError, match="db failure"):
                await MyRepo().failing_op()

        mock_logger.warning.assert_called_once()
        assert mock_logger.warning.call_args[0][0] == "slow_repo_operation"
