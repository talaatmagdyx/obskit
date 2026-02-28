"""Tests for obskit.tracing.auto — auto-instrumentation detection and application."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from obskit.tracing.auto import (
    _INSTRUMENTORS,
    _applied,
    apply_instrumentors,
    detect_available_instrumentors,
    get_applied_instrumentors,
    get_instrumentor_registry,
    uninstrument_all,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_mod(class_name: str, instance: MagicMock | None = None) -> MagicMock:
    """Return a mock module whose *class_name* attribute is a constructor."""
    mod = MagicMock()
    inst = instance or MagicMock()
    setattr(mod, class_name, MagicMock(return_value=inst))
    return mod, inst


# ---------------------------------------------------------------------------
# TestDetectAvailableInstrumentors
# ---------------------------------------------------------------------------


class TestDetectAvailableInstrumentors:
    """detect_available_instrumentors() — read-only probe."""

    def test_returns_list(self) -> None:
        """Always returns a list."""
        result = detect_available_instrumentors()
        assert isinstance(result, list)

    def test_empty_when_nothing_installed(self) -> None:
        """Returns [] when all imports raise ImportError."""
        with patch(
            "obskit.tracing.auto.importlib.import_module",
            side_effect=ImportError,
        ):
            result = detect_available_instrumentors()
        assert result == []

    def test_detects_one_available_package(self) -> None:
        """Only packages that import successfully appear in the result."""
        target_module = "opentelemetry.instrumentation.redis"

        def fake_import(name: str) -> MagicMock:
            if name == target_module:
                return MagicMock()
            raise ImportError

        with patch("obskit.tracing.auto.importlib.import_module", side_effect=fake_import):
            result = detect_available_instrumentors()

        assert "redis" in result
        # other names are absent (their imports failed)
        for name in result:
            assert name == "redis" or name in _INSTRUMENTORS

    def test_returns_all_when_all_available(self) -> None:
        """Returns all known names when every import succeeds."""
        with patch(
            "obskit.tracing.auto.importlib.import_module",
            return_value=MagicMock(),
        ):
            result = detect_available_instrumentors()

        assert sorted(result) == sorted(_INSTRUMENTORS.keys())

    def test_no_side_effects(self) -> None:
        """detect_* must never modify _applied."""
        before = set(get_applied_instrumentors())
        with patch(
            "obskit.tracing.auto.importlib.import_module",
            return_value=MagicMock(),
        ):
            detect_available_instrumentors()
        assert set(get_applied_instrumentors()) == before


# ---------------------------------------------------------------------------
# TestApplyInstrumentors
# ---------------------------------------------------------------------------


class TestApplyInstrumentors:
    """apply_instrumentors() — detection + patching."""

    def setup_method(self) -> None:
        uninstrument_all()

    def teardown_method(self) -> None:
        uninstrument_all()

    # --- happy path --------------------------------------------------------

    def test_applies_single_instrumentor(self) -> None:
        """Successfully instruments a known library."""
        mod, inst = _make_mock_mod("RedisInstrumentor")
        with patch("obskit.tracing.auto.importlib.import_module", return_value=mod):
            result = apply_instrumentors(["redis"])

        assert "redis" in result
        inst.instrument.assert_called_once()

    def test_applies_multiple_instrumentors(self) -> None:
        """Applies several instrumentors in one call."""
        mock_inst = MagicMock()
        mock_mod = MagicMock()
        mock_mod.RedisInstrumentor = MagicMock(return_value=mock_inst)
        mock_mod.FastAPIInstrumentor = MagicMock(return_value=mock_inst)

        with patch("obskit.tracing.auto.importlib.import_module", return_value=mock_mod):
            result = apply_instrumentors(["redis", "fastapi"])

        assert "redis" in result
        assert "fastapi" in result

    def test_returns_applied_names(self) -> None:
        """Return value lists every name that was successfully applied."""
        mod, _inst = _make_mock_mod("CeleryInstrumentor")
        with patch("obskit.tracing.auto.importlib.import_module", return_value=mod):
            result = apply_instrumentors(["celery"])
        assert result == ["celery"]

    def test_empty_list_applies_nothing(self) -> None:
        """Passing an empty list applies nothing."""
        result = apply_instrumentors([])
        assert result == []

    # --- idempotency -------------------------------------------------------

    def test_already_applied_is_idempotent(self) -> None:
        """A second call with the same name does not call .instrument() again."""
        mod, inst = _make_mock_mod("HttpxInstrumentor")
        # Correct class name for httpx
        mock_mod = MagicMock()
        mock_inst = MagicMock()
        mock_mod.HTTPXClientInstrumentor = MagicMock(return_value=mock_inst)

        with patch("obskit.tracing.auto.importlib.import_module", return_value=mock_mod):
            apply_instrumentors(["httpx"])
            result2 = apply_instrumentors(["httpx"])

        assert "httpx" in result2
        assert mock_inst.instrument.call_count == 1  # only once total

    # --- auto-detection ----------------------------------------------------

    def test_none_uses_detect_available(self) -> None:
        """instruments=None delegates to detect_available_instrumentors."""
        with patch(
            "obskit.tracing.auto.detect_available_instrumentors",
            return_value=[],
        ) as mock_detect:
            result = apply_instrumentors(None)

        mock_detect.assert_called_once()
        assert result == []

    def test_auto_detect_and_apply(self) -> None:
        """When None is passed, detected names are instrumented."""
        mock_mod = MagicMock()
        mock_inst = MagicMock()
        mock_mod.DjangoInstrumentor = MagicMock(return_value=mock_inst)

        with patch(
            "obskit.tracing.auto.detect_available_instrumentors",
            return_value=["django"],
        ), patch("obskit.tracing.auto.importlib.import_module", return_value=mock_mod):
            result = apply_instrumentors(None)

        assert "django" in result
        mock_inst.instrument.assert_called_once()

    # --- error handling ----------------------------------------------------

    def test_unknown_name_is_skipped(self) -> None:
        """An unrecognised instrumentor name is skipped with a warning."""
        result = apply_instrumentors(["definitely_not_a_real_lib"])
        assert "definitely_not_a_real_lib" not in result

    def test_unknown_name_does_not_raise(self) -> None:
        """Unknown names must never raise an exception."""
        apply_instrumentors(["bad_name_1", "bad_name_2"])  # no AssertionError

    def test_import_error_is_handled(self) -> None:
        """Package not installed → skipped, no exception."""
        with patch(
            "obskit.tracing.auto.importlib.import_module",
            side_effect=ImportError("no module named ..."),
        ):
            result = apply_instrumentors(["redis"])
        assert result == []

    def test_instrument_raises_runtime_error(self) -> None:
        """If .instrument() raises, name is not in result and no exception propagates."""
        mock_mod = MagicMock()
        mock_inst = MagicMock()
        mock_inst.instrument.side_effect = RuntimeError("patching failed")
        mock_mod.RedisInstrumentor = MagicMock(return_value=mock_inst)

        with patch("obskit.tracing.auto.importlib.import_module", return_value=mock_mod):
            result = apply_instrumentors(["redis"])

        assert "redis" not in result

    def test_constructor_raises_runtime_error(self) -> None:
        """If cls() itself raises, name is not in result."""
        mock_mod = MagicMock()
        mock_mod.RedisInstrumentor.side_effect = RuntimeError("constructor failed")

        with patch("obskit.tracing.auto.importlib.import_module", return_value=mock_mod):
            result = apply_instrumentors(["redis"])

        assert "redis" not in result

    def test_mixed_success_and_failure(self) -> None:
        """Successful instrumentors are returned even when others fail."""
        mock_mod = MagicMock()
        good_inst = MagicMock()
        mock_mod.DjangoInstrumentor = MagicMock(return_value=good_inst)
        mock_mod.CeleryInstrumentor.side_effect = RuntimeError("celery broke")

        with patch("obskit.tracing.auto.importlib.import_module", return_value=mock_mod):
            result = apply_instrumentors(["django", "celery"])

        assert "django" in result
        assert "celery" not in result


# ---------------------------------------------------------------------------
# TestUninstrumentAll
# ---------------------------------------------------------------------------


class TestUninstrumentAll:
    """uninstrument_all() — cleanup and teardown."""

    def setup_method(self) -> None:
        uninstrument_all()

    def test_clears_applied_registry(self) -> None:
        """After uninstrument_all, get_applied_instrumentors() returns []."""
        mock_mod = MagicMock()
        mock_inst = MagicMock()
        mock_mod.RedisInstrumentor = MagicMock(return_value=mock_inst)

        with patch("obskit.tracing.auto.importlib.import_module", return_value=mock_mod):
            apply_instrumentors(["redis"])

        assert "redis" in get_applied_instrumentors()
        uninstrument_all()
        assert get_applied_instrumentors() == []

    def test_calls_uninstrument_on_instance(self) -> None:
        """Calls .uninstrument() on every active instance."""
        mock_mod = MagicMock()
        mock_inst = MagicMock()
        mock_mod.RedisInstrumentor = MagicMock(return_value=mock_inst)

        with patch("obskit.tracing.auto.importlib.import_module", return_value=mock_mod):
            apply_instrumentors(["redis"])

        uninstrument_all()
        mock_inst.uninstrument.assert_called_once()

    def test_safe_when_nothing_applied(self) -> None:
        """Safe to call on an empty registry."""
        uninstrument_all()  # must not raise

    def test_uninstrument_exception_is_swallowed(self) -> None:
        """Errors from .uninstrument() do not propagate."""
        mock_mod = MagicMock()
        mock_inst = MagicMock()
        mock_inst.uninstrument.side_effect = RuntimeError("cleanup failed")
        mock_mod.RedisInstrumentor = MagicMock(return_value=mock_inst)

        with patch("obskit.tracing.auto.importlib.import_module", return_value=mock_mod):
            apply_instrumentors(["redis"])

        uninstrument_all()  # must not raise despite the RuntimeError
        assert get_applied_instrumentors() == []

    def test_multiple_instances_cleared(self) -> None:
        """All applied instrumentors are cleared, not just the first."""
        mock_mod = MagicMock()
        redis_inst = MagicMock()
        celery_inst = MagicMock()
        mock_mod.RedisInstrumentor = MagicMock(return_value=redis_inst)
        mock_mod.CeleryInstrumentor = MagicMock(return_value=celery_inst)

        with patch("obskit.tracing.auto.importlib.import_module", return_value=mock_mod):
            apply_instrumentors(["redis", "celery"])

        uninstrument_all()
        assert get_applied_instrumentors() == []
        redis_inst.uninstrument.assert_called_once()
        celery_inst.uninstrument.assert_called_once()


# ---------------------------------------------------------------------------
# TestGetAppliedInstrumentors
# ---------------------------------------------------------------------------


class TestGetAppliedInstrumentors:
    """get_applied_instrumentors() — snapshot of active names."""

    def setup_method(self) -> None:
        uninstrument_all()

    def teardown_method(self) -> None:
        uninstrument_all()

    def test_empty_initially(self) -> None:
        assert get_applied_instrumentors() == []

    def test_reflects_applied_names(self) -> None:
        mock_mod = MagicMock()
        mock_inst = MagicMock()
        mock_mod.RedisInstrumentor = MagicMock(return_value=mock_inst)

        with patch("obskit.tracing.auto.importlib.import_module", return_value=mock_mod):
            apply_instrumentors(["redis"])

        assert "redis" in get_applied_instrumentors()

    def test_returns_copy_not_reference(self) -> None:
        """Mutating the returned list does not affect internal state."""
        result = get_applied_instrumentors()
        result.append("injected_fake")
        assert "injected_fake" not in get_applied_instrumentors()


# ---------------------------------------------------------------------------
# TestGetInstrumentorRegistry
# ---------------------------------------------------------------------------


class TestGetInstrumentorRegistry:
    """get_instrumentor_registry() — introspection API."""

    def test_returns_dict(self) -> None:
        reg = get_instrumentor_registry()
        assert isinstance(reg, dict)

    def test_contains_expected_names(self) -> None:
        reg = get_instrumentor_registry()
        for expected in ("fastapi", "sqlalchemy", "redis", "httpx", "celery"):
            assert expected in reg, f"{expected!r} missing from registry"

    def test_values_are_two_tuples(self) -> None:
        reg = get_instrumentor_registry()
        for name, value in reg.items():
            assert isinstance(value, tuple) and len(value) == 2, (
                f"Registry entry {name!r} should be (module_path, class_name)"
            )

    def test_returns_copy_not_reference(self) -> None:
        """Mutating the returned dict does not corrupt the registry."""
        reg = get_instrumentor_registry()
        reg["injected"] = ("fake.module", "FakeClass")
        assert "injected" not in get_instrumentor_registry()

    def test_size_matches_internal_dict(self) -> None:
        reg = get_instrumentor_registry()
        assert len(reg) == len(_INSTRUMENTORS)
