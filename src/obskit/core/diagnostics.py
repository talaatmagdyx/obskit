"""Unified diagnostics — observability for the observability layer.

Combines package/integration diagnostics from :mod:`obskit.core.diagnose`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from obskit.core.diagnose import PackageInfo


@dataclass
class DiagnosticsReport:
    """Combined snapshot of package health."""

    packages: list[PackageInfo]


class Diagnostics:
    """Unified diagnostics interface.

    Access via ``obs.diagnostics`` on the :class:`~obskit.core.observability.Observability`
    facade.
    """

    def packages(self) -> list[PackageInfo]:
        """Return package/integration availability info."""
        from obskit.core.diagnose import collect_diagnostics

        return collect_diagnostics()

    def report(self) -> DiagnosticsReport:
        """Return combined diagnostics report."""
        return DiagnosticsReport(
            packages=self.packages(),
        )

    def print_report(self, out: Any = None) -> None:
        """Print human-readable diagnostics to *out* (defaults to stdout)."""
        from obskit.core.diagnose import run_diagnostics

        run_diagnostics(out=out)
