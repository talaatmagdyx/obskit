"""Tests for obskit.core.diagnose — environment diagnostics CLI."""

from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

import pytest

from obskit.core.diagnose import (
    IntegrationInfo,
    PackageInfo,
    _check_otlp_reachable,
    _import_available,
    _import_version,
    _pkg_version,
    _render,
    _tick,
    collect_diagnostics,
    run_diagnostics,
)

# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------


class TestPkgVersion:
    def test_returns_string_for_installed_package(self) -> None:
        """pytest is always installed in the test env."""
        ver = _pkg_version("pytest")
        assert ver is not None
        assert isinstance(ver, str)

    def test_returns_none_for_missing_package(self) -> None:
        ver = _pkg_version("this-package-does-not-exist-xyz")
        assert ver is None


class TestImportAvailable:
    def test_true_for_existing_module(self) -> None:
        assert _import_available("sys") is True

    def test_false_for_missing_module(self) -> None:
        assert _import_available("no_such_module_xyz") is False


class TestImportVersion:
    def test_returns_version_for_sys(self) -> None:
        # sys has no __version__, but we can check it returns None gracefully
        result = _import_version("sys")
        # sys.__version__ does not exist — returns "None" (stringified)
        assert result is not None  # returns str(None) = "None"

    def test_returns_none_for_missing_module(self) -> None:
        result = _import_version("no_such_module_xyz")
        assert result is None


class TestTick:
    def test_true_returns_checkmark(self) -> None:
        assert _tick(True) == "✅"

    def test_false_returns_cross(self) -> None:
        assert _tick(False) == "❌"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class TestPackageInfo:
    def test_installed_package(self) -> None:
        pkg = PackageInfo(name="obskit-core", installed=True, version="2.0.0")
        assert pkg.name == "obskit-core"
        assert pkg.installed is True
        assert pkg.version == "2.0.0"
        assert pkg.integrations == []

    def test_not_installed_package(self) -> None:
        pkg = PackageInfo(name="obskit-resilience", installed=False, version=None)
        assert pkg.installed is False
        assert pkg.version is None

    def test_with_integrations(self) -> None:
        intg = IntegrationInfo(label="structlog", available=True, detail="24.1.0")
        pkg = PackageInfo(
            name="obskit-logging", installed=True, version="2.0.0", integrations=[intg]
        )
        assert len(pkg.integrations) == 1
        assert pkg.integrations[0].label == "structlog"


class TestIntegrationInfo:
    def test_available(self) -> None:
        intg = IntegrationInfo(label="opentelemetry-api", available=True, detail="1.27.0")
        assert intg.available is True
        assert intg.detail == "1.27.0"

    def test_unavailable(self) -> None:
        intg = IntegrationInfo(label="prometheus-client", available=False)
        assert intg.available is False
        assert intg.detail is None


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


class TestRender:
    def test_render_returns_string(self) -> None:
        packages = [PackageInfo(name="obskit-core", installed=True, version="2.0.0")]
        output = _render(packages)
        assert isinstance(output, str)

    def test_render_contains_package_name(self) -> None:
        packages = [PackageInfo(name="obskit-core", installed=True, version="2.0.0")]
        output = _render(packages)
        assert "obskit-core" in output

    def test_render_shows_installed_tick(self) -> None:
        packages = [PackageInfo(name="obskit-core", installed=True, version="2.0.0")]
        output = _render(packages)
        assert "✅" in output

    def test_render_shows_not_installed(self) -> None:
        packages = [PackageInfo(name="obskit-resilience", installed=False, version=None)]
        output = _render(packages)
        assert "not installed" in output

    def test_render_shows_integration_details(self) -> None:
        intg = IntegrationInfo(label="structlog", available=True, detail="24.1.0")
        packages = [
            PackageInfo(name="obskit-logging", installed=True, version="2.0.0", integrations=[intg])
        ]
        output = _render(packages)
        assert "structlog" in output
        assert "24.1.0" in output

    def test_render_includes_python_version(self) -> None:
        packages = []
        output = _render(packages)
        assert "Python" in output

    def test_render_contains_header(self) -> None:
        output = _render([])
        assert "obskit environment diagnostics" in output


# ---------------------------------------------------------------------------
# collect_diagnostics
# ---------------------------------------------------------------------------


class TestCollectDiagnostics:
    def test_returns_list(self) -> None:
        result = collect_diagnostics()
        assert isinstance(result, list)

    def test_contains_core_package(self) -> None:
        result = collect_diagnostics()
        names = [p.name for p in result]
        assert "obskit-core" in names

    def test_contains_all_packages(self) -> None:
        result = collect_diagnostics()
        names = [p.name for p in result]
        expected = [
            "obskit-core",
            "obskit-logging",
            "obskit-metrics",
            "obskit-tracing",
            "obskit-health",
            "obskit-resilience",
            "obskit-slo",
            "obskit-middleware-fastapi",
            "obskit-middleware-flask",
            "obskit-middleware-django",
            "obskit-middleware-grpc",
            "obskit",
        ]
        for name in expected:
            assert name in names

    def test_each_item_is_package_info(self) -> None:
        result = collect_diagnostics()
        for item in result:
            assert isinstance(item, PackageInfo)

    def test_obskit_core_installed(self) -> None:
        """obskit-core must be installed since we're running tests for it."""
        result = collect_diagnostics()
        core = next(p for p in result if p.name == "obskit-core")
        assert core.installed is True
        assert core.version is not None


# ---------------------------------------------------------------------------
# run_diagnostics
# ---------------------------------------------------------------------------


class TestRunDiagnostics:
    def test_writes_to_stdout_by_default(self, capsys: pytest.CaptureFixture[str]) -> None:
        run_diagnostics()
        captured = capsys.readouterr()
        assert "obskit environment diagnostics" in captured.out

    def test_accepts_custom_file_object(self) -> None:
        buf = io.StringIO()
        run_diagnostics(out=buf)
        output = buf.getvalue()
        assert "obskit environment diagnostics" in output
        assert "obskit-core" in output

    def test_output_contains_python_version(self) -> None:
        buf = io.StringIO()
        run_diagnostics(out=buf)
        assert "Python" in buf.getvalue()

    def test_output_contains_tick_or_cross(self) -> None:
        buf = io.StringIO()
        run_diagnostics(out=buf)
        output = buf.getvalue()
        # At least some packages are installed
        assert "✅" in output


# ---------------------------------------------------------------------------
# Branch coverage: "not installed" paths for per-package check functions
# ---------------------------------------------------------------------------


class TestCheckFunctionsNotInstalled:
    """Exercise the `if ver is None` (False) branches in each _check_* function.

    When a package is NOT installed, _pkg_version returns None so the
    integrations block is skipped and an empty PackageInfo is returned.
    """

    def test_check_logging_not_installed(self) -> None:
        from obskit.core.diagnose import _check_logging

        with patch("obskit.core.diagnose._pkg_version", return_value=None):
            result = _check_logging()
        assert result.installed is False
        assert result.version is None
        assert result.integrations == []

    def test_check_metrics_not_installed(self) -> None:
        from obskit.core.diagnose import _check_metrics

        with patch("obskit.core.diagnose._pkg_version", return_value=None):
            result = _check_metrics()
        assert result.installed is False
        assert result.integrations == []

    def test_check_tracing_not_installed(self) -> None:
        from obskit.core.diagnose import _check_tracing

        with patch("obskit.core.diagnose._pkg_version", return_value=None):
            result = _check_tracing()
        assert result.installed is False
        assert result.integrations == []

    def test_check_health_not_installed(self) -> None:
        from obskit.core.diagnose import _check_health

        with patch("obskit.core.diagnose._pkg_version", return_value=None):
            result = _check_health()
        assert result.installed is False
        assert result.integrations == []


# ---------------------------------------------------------------------------
# ImportError / Exception branches inside "if ver is not None" blocks
# ---------------------------------------------------------------------------


class TestCheckFunctionsSubImportErrors:
    """Cover the except-ImportError/Exception clauses that fire when a
    sub-module cannot be imported even though the parent package IS installed.

    Technique: set ``sys.modules[module_path] = None`` before the call so
    that Python raises ``ImportError`` on ``from module_path import …``,
    then restore the real entry afterwards.
    """

    def test_check_logging_trace_correlation_import_error(self) -> None:
        """Lines 108-109: except ImportError when importing trace_correlation."""
        from obskit.core.diagnose import _check_logging

        key = "obskit.logging.trace_correlation"
        saved = sys.modules.get(key, ...)
        sys.modules[key] = None  # type: ignore[assignment]
        try:
            result = _check_logging()
        finally:
            if saved is ...:
                del sys.modules[key]
            else:
                sys.modules[key] = saved  # type: ignore[assignment]

        tc = next(i for i in result.integrations if i.label == "trace-correlation")
        assert tc.available is False

    def test_check_metrics_exemplar_import_error(self) -> None:
        """Lines 129-130: except ImportError when importing exemplar."""
        from obskit.core.diagnose import _check_metrics

        key = "obskit.metrics.exemplar"
        saved = sys.modules.get(key, ...)
        sys.modules[key] = None  # type: ignore[assignment]
        try:
            result = _check_metrics()
        finally:
            if saved is ...:
                del sys.modules[key]
            else:
                sys.modules[key] = saved  # type: ignore[assignment]

        ex = next(i for i in result.integrations if i.label == "trace-exemplars")
        assert ex.available is False

    def test_check_tracing_settings_exception(self) -> None:
        """Lines 156-157: except Exception when get_settings() raises."""
        from obskit.core.diagnose import _check_tracing

        with patch("obskit.config.get_settings", side_effect=RuntimeError("cfg error")):
            result = _check_tracing()

        endpoint_info = next(i for i in result.integrations if i.label == "otlp-endpoint")
        # "(unavailable)" != "(not configured)" → available=True, but detail shows the fallback
        assert endpoint_info.detail == "(unavailable)"

    def test_check_health_tracing_integration_present(self) -> None:
        """health-tracing integration is always present in _check_health output (based on opentelemetry)."""
        from obskit.core.diagnose import _check_health

        result = _check_health()

        # health-tracing integration is always added based on opentelemetry availability
        labels = [i.label for i in result.integrations]
        assert "health-tracing" in labels


# ---------------------------------------------------------------------------
# _check_otlp_reachable
# ---------------------------------------------------------------------------


class TestCheckOtlpReachable:
    def test_reachable_returns_true_and_detail(self) -> None:
        """Successful TCP connection returns (True, '<host>:<port> reachable ✓')."""
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cm)
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("socket.create_connection", return_value=mock_cm):
            reachable, detail = _check_otlp_reachable("http://localhost:4317")
        assert reachable is True
        assert "reachable ✓" in detail
        assert "localhost:4317" in detail

    def test_unreachable_returns_false_and_detail(self) -> None:
        """Failed TCP connection returns (False, '<host>:<port> unreachable — ...')."""
        exc = OSError()
        exc.strerror = "Connection refused"
        with patch("socket.create_connection", side_effect=exc):
            reachable, detail = _check_otlp_reachable("http://localhost:4317")
        assert reachable is False
        assert "unreachable" in detail
        assert "Connection refused" in detail
        assert "localhost:4317" in detail

    def test_default_port_used_when_missing(self) -> None:
        """Endpoint without explicit port defaults to 4317."""
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cm)
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("socket.create_connection", return_value=mock_cm) as mock_conn:
            reachable, detail = _check_otlp_reachable("http://tempo")
        assert reachable is True
        # Verify port 4317 was used
        call_args = mock_conn.call_args[0][0]
        assert call_args[1] == 4317


# ---------------------------------------------------------------------------
# _check_tracing otlp-reachable integration
# ---------------------------------------------------------------------------


class TestCheckTracingOtlpReachable:
    def test_otlp_reachable_included_when_endpoint_configured(self) -> None:
        """otlp-reachable integration appears when endpoint is configured."""
        from obskit.core.diagnose import _check_tracing

        mock_settings = MagicMock()
        mock_settings.otlp_endpoint = "http://tempo:4317"

        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_cm)
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch("obskit.config.get_settings", return_value=mock_settings):
            with patch("socket.create_connection", return_value=mock_cm):
                result = _check_tracing()

        labels = [i.label for i in result.integrations]
        assert "otlp-reachable" in labels

    def test_otlp_reachable_not_included_when_endpoint_not_configured(self) -> None:
        """otlp-reachable integration is absent when endpoint is '(not configured)'."""
        from obskit.core.diagnose import _check_tracing

        mock_settings = MagicMock()
        mock_settings.otlp_endpoint = None  # results in "(not configured)"

        with patch("obskit.config.get_settings", return_value=mock_settings):
            result = _check_tracing()

        labels = [i.label for i in result.integrations]
        assert "otlp-reachable" not in labels

    def test_otlp_reachable_not_included_when_settings_unavailable(self) -> None:
        """otlp-reachable integration is absent when get_settings() raises."""
        from obskit.core.diagnose import _check_tracing

        with patch("obskit.config.get_settings", side_effect=RuntimeError("cfg error")):
            result = _check_tracing()

        labels = [i.label for i in result.integrations]
        assert "otlp-reachable" not in labels


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------


class TestMainEntryPoint:
    def test_main_runs_without_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Running as __main__ should not raise."""
        import runpy

        runpy.run_module("obskit.core.diagnose", run_name="__main__", alter_sys=False)
        captured = capsys.readouterr()
        assert "obskit environment diagnostics" in captured.out
