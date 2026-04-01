"""obskit environment diagnostics.

Run with::

    python -m obskit.core.diagnose

Prints a table of all obskit packages, their versions, and the status
of optional integrations (OpenTelemetry, Prometheus, structlog, etc.).
"""

from __future__ import annotations

import importlib
import importlib.metadata
import sys
from dataclasses import dataclass, field
from typing import Any

# Sentinel strings used when an optional setting is absent.
_NOT_CONFIGURED = "(not configured)"

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class PackageInfo:
    """Information about one obskit package."""

    name: str
    installed: bool
    version: str | None
    integrations: list[IntegrationInfo] = field(default_factory=list)


@dataclass
class IntegrationInfo:
    """An optional integration within a package."""

    label: str
    available: bool
    detail: str | None = None


# ---------------------------------------------------------------------------
# Package detection helpers
# ---------------------------------------------------------------------------


def _pkg_version(name: str) -> str | None:
    """Return installed version of *name*, or None if not installed."""
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _import_available(module: str) -> bool:
    """Return True if *module* can be imported."""
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


def _import_version(module: str, attr: str = "__version__") -> str | None:
    """Return *module.attr* version string, or None."""
    try:
        mod = importlib.import_module(module)
        return str(getattr(mod, attr, None))
    except ImportError:
        return None


def _check_otlp_reachable(endpoint: str) -> tuple[bool, str]:
    """TCP-connect to the OTLP endpoint. Returns (reachable, detail_string)."""
    import socket  # noqa: PLC0415
    import urllib.parse  # noqa: PLC0415

    try:
        parsed = urllib.parse.urlparse(endpoint)
        host = parsed.hostname or "localhost"
        port = parsed.port or 4317
        with socket.create_connection((host, port), timeout=2.0):
            return True, f"{host}:{port} reachable ✓"
    except OSError as exc:
        return False, f"{host}:{port} unreachable — {exc.strerror}"
    except Exception as exc:  # pragma: no cover
        return False, f"check failed: {exc}"


# ---------------------------------------------------------------------------
# Per-package checks
# ---------------------------------------------------------------------------


def _check_core() -> PackageInfo:
    ver = _pkg_version("obskit")
    return PackageInfo(
        name="obskit-core",
        installed=ver is not None,
        version=ver,
        integrations=[
            IntegrationInfo(
                label="pydantic-settings",
                available=_import_available("pydantic_settings"),
                detail=_import_version("pydantic_settings"),
            ),
        ],
    )


def _check_logging() -> PackageInfo:
    ver = _pkg_version("obskit")
    integrations: list[IntegrationInfo] = []
    if ver is not None:
        sl_ver = _import_version("structlog")
        integrations.append(IntegrationInfo("structlog", sl_ver is not None, sl_ver))
        # trace-correlation availability
        try:
            from obskit.logging.trace_correlation import is_trace_correlation_available

            tc_avail = is_trace_correlation_available()
        except ImportError:
            tc_avail = False
        integrations.append(
            IntegrationInfo(
                "trace-correlation",
                tc_avail,
                "✅ active" if tc_avail else "needs obskit-tracing[opentelemetry]",
            )
        )
    return PackageInfo(
        name="obskit-logging", installed=ver is not None, version=ver, integrations=integrations
    )


def _check_metrics() -> PackageInfo:
    ver = _pkg_version("obskit")
    integrations: list[IntegrationInfo] = []
    if ver is not None:
        prom_ver = _import_version("prometheus_client")
        integrations.append(IntegrationInfo("prometheus-client", prom_ver is not None, prom_ver))
        try:
            from obskit.metrics.exemplar import is_exemplar_available

            ex_avail = is_exemplar_available()
        except ImportError:
            ex_avail = False
        integrations.append(
            IntegrationInfo(
                "trace-exemplars",
                ex_avail,
                "✅ active"
                if ex_avail
                else "needs prometheus-client + obskit-tracing[opentelemetry]",
            )
        )
    return PackageInfo(
        name="obskit-metrics", installed=ver is not None, version=ver, integrations=integrations
    )


def _check_tracing() -> PackageInfo:
    ver = _pkg_version("obskit")
    integrations: list[IntegrationInfo] = []
    if ver is not None:
        otel_api_ver = _import_version("opentelemetry.trace", "__version__") or _pkg_version(
            "opentelemetry-api"
        )
        integrations.append(
            IntegrationInfo("opentelemetry-api", otel_api_ver is not None, otel_api_ver)
        )
        otel_sdk_ver = _pkg_version("opentelemetry-sdk")
        integrations.append(
            IntegrationInfo("opentelemetry-sdk", otel_sdk_ver is not None, otel_sdk_ver)
        )
        # endpoint from settings
        try:
            from obskit.config import get_settings

            endpoint = get_settings().otlp_endpoint or _NOT_CONFIGURED
        except Exception:
            endpoint = "(unavailable)"
        integrations.append(
            IntegrationInfo("otlp-endpoint", bool(endpoint != _NOT_CONFIGURED), endpoint)
        )
        # Probe TCP reachability of the configured endpoint
        if endpoint not in {_NOT_CONFIGURED, "(unavailable)"}:
            reachable, detail = _check_otlp_reachable(endpoint)
            integrations.append(IntegrationInfo("otlp-reachable", reachable, detail))
    return PackageInfo(
        name="obskit-tracing", installed=ver is not None, version=ver, integrations=integrations
    )


def _check_health() -> PackageInfo:
    ver = _pkg_version("obskit")
    integrations: list[IntegrationInfo] = []
    if ver is not None:
        try:
            import opentelemetry  # noqa: F401

            _OTEL_AVAILABLE = True
        except ImportError:
            _OTEL_AVAILABLE = False
        integrations.append(
            IntegrationInfo(
                "health-tracing",
                _OTEL_AVAILABLE,
                "trace_id in /health responses"
                if _OTEL_AVAILABLE
                else "needs obskit-tracing[opentelemetry]",
            )
        )
    return PackageInfo(
        name="obskit-health", installed=ver is not None, version=ver, integrations=integrations
    )


def _check_simple(name: str, pip_name: str | None = None) -> PackageInfo:
    ver = _pkg_version(pip_name or name)
    return PackageInfo(name=name, installed=ver is not None, version=ver)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_WIDTH = 72
_COL1 = 28
_COL2 = 12


def _tick(ok: bool) -> str:
    return "✅" if ok else "❌"


def _render(packages: list[PackageInfo]) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append("obskit environment diagnostics")
    lines.append("─" * _WIDTH)
    lines.append(f"{'Package':<{_COL1}} {'Version':<{_COL2}} Status")
    lines.append("─" * _WIDTH)
    for pkg in packages:
        if pkg.installed:
            status = f"{_tick(True)} installed"
            ver = pkg.version or ""
        else:
            status = "not installed"
            ver = ""
        lines.append(f"{pkg.name:<{_COL1}} {ver:<{_COL2}} {status}")
        for intg in pkg.integrations:
            label = f"  └─ {intg.label}"
            detail = intg.detail or ""
            tick = _tick(intg.available)
            lines.append(f"  {'':2}{label:<{_COL1 - 4}} {detail:<{_COL2}} {tick}")
    lines.append("─" * _WIDTH)
    lines.append(f"Python {sys.version.split()[0]}  |  {sys.executable}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def collect_diagnostics() -> list[PackageInfo]:
    """Collect diagnostic information for all obskit packages.

    Returns:
        List of :class:`PackageInfo` objects, one per obskit package.
    """
    return [
        _check_core(),
        _check_logging(),
        _check_metrics(),
        _check_tracing(),
        _check_health(),
        _check_simple("obskit-resilience", pip_name="obskit"),
        _check_simple("obskit-slo", pip_name="obskit"),
        _check_simple("obskit-middleware-fastapi", pip_name="obskit"),
        _check_simple("obskit-middleware-flask", pip_name="obskit"),
        _check_simple("obskit-middleware-django", pip_name="obskit"),
        _check_simple("obskit-middleware-grpc", pip_name="obskit"),
        _check_simple("obskit"),
    ]


def run_diagnostics(*, out: Any = None) -> None:
    """Run diagnostics and print the result.

    Args:
        out: File-like object to write output to (defaults to sys.stdout).
    """
    import sys as _sys

    if out is None:
        out = _sys.stdout
    packages = collect_diagnostics()
    print(_render(packages), file=out)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_diagnostics()
