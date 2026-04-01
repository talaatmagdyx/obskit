"""Tests for the Diagnostics class and obs.diagnostics property."""

from __future__ import annotations

import io
from collections.abc import Generator

import pytest

from obskit.config import reset_settings
from obskit.core.diagnostics import Diagnostics, DiagnosticsReport
from obskit.core.observability import Observability, reset_observability
from obskit.core.observability_config import ObservabilityConfig


@pytest.fixture(autouse=True)
def _clean() -> Generator[None, None, None]:
    reset_settings()
    reset_observability()
    yield
    reset_settings()
    reset_observability()


class TestDiagnostics:
    def test_packages_returns_list(self) -> None:
        diag = Diagnostics()
        packages = diag.packages()
        assert isinstance(packages, list)
        assert len(packages) > 0

    def test_report_returns_combined(self) -> None:
        diag = Diagnostics()
        report = diag.report()
        assert isinstance(report, DiagnosticsReport)
        assert isinstance(report.packages, list)
        assert len(report.packages) > 0

    def test_print_report_writes_to_stream(self) -> None:
        diag = Diagnostics()
        buf = io.StringIO()
        diag.print_report(out=buf)
        output = buf.getvalue()
        assert "obskit" in output.lower()


class TestObservabilityDiagnostics:
    def test_diagnostics_property_exists(self) -> None:
        obs = Observability(ObservabilityConfig())
        diag = obs.diagnostics
        assert isinstance(diag, Diagnostics)

    def test_diagnostics_is_cached(self) -> None:
        obs = Observability(ObservabilityConfig())
        diag1 = obs.diagnostics
        diag2 = obs.diagnostics
        assert diag1 is diag2

    def test_diagnostics_packages_via_obs(self) -> None:
        obs = Observability(ObservabilityConfig())
        packages = obs.diagnostics.packages()
        assert isinstance(packages, list)

    def test_diagnostics_report_via_obs(self) -> None:
        obs = Observability(ObservabilityConfig())
        report = obs.diagnostics.report()
        assert isinstance(report, DiagnosticsReport)
