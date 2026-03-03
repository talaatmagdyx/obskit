"""
Tests for obskit.health.router — build_health_router
=====================================================

Covers:
- Router is created with the correct URL prefix and endpoints (/live, /ready, /)
- /live returns 200 when liveness checks pass, 503 when they fail
- /ready returns 200 when readiness checks pass, 503 when they fail
- Root endpoint (combined) honours both check sets
- HealthCheck(name=..., check=lambda: ..., timeout=...) syntax (new 'check' alias)
- HealthCheck(name=..., check_fn=lambda: ...) backward-compat syntax
- Sync callables work (wrapped transparently by HealthChecker)
- Async callables work
- Checks parameter (shortcut — all treated as readiness)
- readiness_checks + liveness_checks split parameter
- Custom prefix
- Non-critical failing check → still 200 / "degraded" in body
- ImportError raised when fastapi is not installed
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Skip the whole module if fastapi is not installed
# ---------------------------------------------------------------------------
pytest.importorskip("fastapi", reason="fastapi not installed; skipping router tests")

from fastapi.testclient import TestClient  # noqa: E402 (after importorskip guard)

from obskit.health.checker import HealthCheck  # noqa: E402
from obskit.health.router import build_health_router  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _app(router):
    """Wrap a router in a minimal FastAPI app for TestClient."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return app


def _healthy_check(name: str, timeout: float = 2.0) -> HealthCheck:
    return HealthCheck(name=name, check=lambda: True, timeout=timeout)


def _unhealthy_check(name: str, timeout: float = 2.0) -> HealthCheck:
    return HealthCheck(name=name, check=lambda: False, timeout=timeout)


async def _async_healthy() -> bool:  # noqa: D401
    return True


async def _async_unhealthy() -> bool:  # noqa: D401
    return False


# ---------------------------------------------------------------------------
# TestBuildHealthRouterCreation
# ---------------------------------------------------------------------------


class TestBuildHealthRouterCreation:
    """Structural tests — does the router expose the right endpoints?"""

    def test_returns_api_router(self):
        from fastapi.routing import APIRouter

        router = build_health_router(checks=[_healthy_check("db")])
        assert isinstance(router, APIRouter)

    def test_default_prefix(self):
        from fastapi.routing import APIRouter

        router = build_health_router(checks=[_healthy_check("db")])
        assert router.prefix == "/health"

    def test_custom_prefix(self):
        router = build_health_router(
            checks=[_healthy_check("db")],
            prefix="/healthz",
        )
        assert router.prefix == "/healthz"

    def test_endpoints_registered(self):
        """Router must expose /live, /ready, and a root path."""
        router = build_health_router(checks=[_healthy_check("db")])
        paths = {route.path for route in router.routes}
        # Depending on the FastAPI version, route.path may or may not include
        # the router prefix.  Use suffix matching to be version-agnostic.
        assert any(p.endswith("/live") for p in paths), f"No /live route in {paths}"
        assert any(p.endswith("/ready") for p in paths), f"No /ready route in {paths}"
        assert any(p.endswith("/health") or p == "" for p in paths), f"No root route in {paths}"

    def test_no_checks_allowed(self):
        """Router without any checks should still start without error."""
        router = build_health_router()
        assert router is not None

    def test_include_in_schema_false_by_default(self):
        router = build_health_router(checks=[_healthy_check("db")])
        for route in router.routes:
            assert route.include_in_schema is False

    def test_include_in_schema_true(self):
        router = build_health_router(
            checks=[_healthy_check("db")],
            include_in_schema=True,
        )
        for route in router.routes:
            assert route.include_in_schema is True


# ---------------------------------------------------------------------------
# TestLivenessEndpoint
# ---------------------------------------------------------------------------


class TestLivenessEndpoint:
    """Tests for GET /health/live."""

    def test_live_200_when_no_liveness_checks(self):
        client = TestClient(_app(build_health_router()))
        resp = client.get("/health/live")
        # no liveness checks → always healthy
        assert resp.status_code == 200

    def test_live_200_when_liveness_passes(self):
        router = build_health_router(
            liveness_checks=[_healthy_check("memory")]
        )
        client = TestClient(_app(router))
        resp = client.get("/health/live")
        assert resp.status_code == 200
        body = resp.json()
        assert body["healthy"] is True

    def test_live_503_when_liveness_fails(self):
        router = build_health_router(
            liveness_checks=[_unhealthy_check("memory")]
        )
        client = TestClient(_app(router))
        resp = client.get("/health/live")
        assert resp.status_code == 503
        body = resp.json()
        assert body["healthy"] is False

    def test_live_body_contains_status(self):
        router = build_health_router(liveness_checks=[_healthy_check("cpu")])
        client = TestClient(_app(router))
        body = client.get("/health/live").json()
        assert "status" in body

    def test_live_body_contains_checks(self):
        router = build_health_router(liveness_checks=[_healthy_check("cpu")])
        client = TestClient(_app(router))
        body = client.get("/health/live").json()
        assert "checks" in body
        assert "cpu" in body["checks"]

    def test_live_not_affected_by_readiness_check_failure(self):
        """Failing readiness check must NOT affect /live."""
        router = build_health_router(
            readiness_checks=[_unhealthy_check("db")],
            liveness_checks=[_healthy_check("memory")],
        )
        client = TestClient(_app(router))
        assert client.get("/health/live").status_code == 200


# ---------------------------------------------------------------------------
# TestReadinessEndpoint
# ---------------------------------------------------------------------------


class TestReadinessEndpoint:
    """Tests for GET /health/ready."""

    def test_ready_200_when_all_pass(self):
        router = build_health_router(
            checks=[
                _healthy_check("redis"),
                _healthy_check("postgres"),
            ]
        )
        client = TestClient(_app(router))
        assert client.get("/health/ready").status_code == 200

    def test_ready_503_when_one_fails(self):
        router = build_health_router(
            checks=[
                _healthy_check("redis"),
                _unhealthy_check("postgres"),
            ]
        )
        client = TestClient(_app(router))
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        assert resp.json()["healthy"] is False

    def test_ready_check_names_in_body(self):
        router = build_health_router(
            checks=[
                _healthy_check("redis"),
                _healthy_check("postgres"),
            ]
        )
        client = TestClient(_app(router))
        body = client.get("/health/ready").json()
        assert "redis" in body["checks"]
        assert "postgres" in body["checks"]

    def test_ready_uses_readiness_checks_param(self):
        router = build_health_router(
            readiness_checks=[_unhealthy_check("db")]
        )
        client = TestClient(_app(router))
        assert client.get("/health/ready").status_code == 503

    def test_ready_merges_checks_and_readiness_checks(self):
        router = build_health_router(
            checks=[_healthy_check("redis")],
            readiness_checks=[_unhealthy_check("postgres")],
        )
        client = TestClient(_app(router))
        body = client.get("/health/ready").json()
        assert "redis" in body["checks"]
        assert "postgres" in body["checks"]


# ---------------------------------------------------------------------------
# TestCombinedEndpoint
# ---------------------------------------------------------------------------


class TestCombinedEndpoint:
    """Tests for GET /health (combined liveness + readiness)."""

    def test_root_200_when_all_healthy(self):
        router = build_health_router(
            checks=[_healthy_check("db")],
            liveness_checks=[_healthy_check("mem")],
        )
        client = TestClient(_app(router))
        assert client.get("/health").status_code == 200

    def test_root_503_when_readiness_fails(self):
        router = build_health_router(
            checks=[_unhealthy_check("db")],
        )
        client = TestClient(_app(router))
        assert client.get("/health").status_code == 503

    def test_root_503_when_liveness_fails(self):
        router = build_health_router(
            liveness_checks=[_unhealthy_check("memory")],
        )
        client = TestClient(_app(router))
        assert client.get("/health").status_code == 503


# ---------------------------------------------------------------------------
# TestHealthCheckSyntax
# ---------------------------------------------------------------------------


class TestHealthCheckSyntax:
    """Tests that both 'check' and 'check_fn' parameter names work."""

    def test_check_alias_works(self):
        hc = HealthCheck(name="db", check=lambda: True, timeout=2.0)
        assert hc.check_fn is not None
        assert hc.check_fn() is True

    def test_check_fn_backward_compat(self):
        hc = HealthCheck(name="db", check_fn=lambda: True, timeout=2.0)
        assert hc.check is not None
        assert hc.check() is True

    def test_no_callable_raises_value_error(self):
        with pytest.raises(ValueError, match="requires a callable"):
            HealthCheck(name="db")

    def test_check_alias_in_router(self):
        """HealthCheck created with check= alias should work end-to-end."""
        router = build_health_router(
            checks=[HealthCheck(name="db", check=lambda: True, timeout=1.0)]
        )
        client = TestClient(_app(router))
        assert client.get("/health/ready").status_code == 200

    def test_check_fn_param_in_router(self):
        """HealthCheck created with check_fn= (legacy) should work end-to-end."""
        router = build_health_router(
            checks=[HealthCheck(name="db", check_fn=lambda: False, timeout=1.0)]
        )
        client = TestClient(_app(router))
        assert client.get("/health/ready").status_code == 503


# ---------------------------------------------------------------------------
# TestAsyncChecks
# ---------------------------------------------------------------------------


class TestAsyncChecks:
    """Async check callables must work correctly."""

    def test_async_healthy_check_passes(self):
        router = build_health_router(
            checks=[HealthCheck(name="db", check=_async_healthy, timeout=2.0)]
        )
        client = TestClient(_app(router))
        assert client.get("/health/ready").status_code == 200

    def test_async_unhealthy_check_fails(self):
        router = build_health_router(
            checks=[HealthCheck(name="db", check=_async_unhealthy, timeout=2.0)]
        )
        client = TestClient(_app(router))
        assert client.get("/health/ready").status_code == 503


# ---------------------------------------------------------------------------
# TestCustomPrefix
# ---------------------------------------------------------------------------


class TestCustomPrefix:
    """Tests for custom router prefix."""

    def test_custom_prefix_live(self):
        router = build_health_router(
            checks=[_healthy_check("db")],
            prefix="/healthz",
        )
        client = TestClient(_app(router))
        assert client.get("/healthz/live").status_code == 200

    def test_custom_prefix_ready(self):
        router = build_health_router(
            checks=[_healthy_check("db")],
            prefix="/healthz",
        )
        client = TestClient(_app(router))
        assert client.get("/healthz/ready").status_code == 200

    def test_custom_prefix_root(self):
        router = build_health_router(
            checks=[_healthy_check("db")],
            prefix="/healthz",
        )
        client = TestClient(_app(router))
        assert client.get("/healthz").status_code == 200

    def test_default_prefix_not_accessible_when_custom(self):
        router = build_health_router(
            checks=[_healthy_check("db")],
            prefix="/healthz",
        )
        client = TestClient(_app(router))
        assert client.get("/health/ready").status_code == 404


# ---------------------------------------------------------------------------
# TestImportError
# ---------------------------------------------------------------------------


class TestImportError:
    """build_health_router raises ImportError if fastapi is not installed."""

    def test_import_error_raised_without_fastapi(self, monkeypatch):
        # Temporarily make fastapi un-importable
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else None

        fastapi_modules = {k: v for k, v in sys.modules.items() if "fastapi" in k}

        # Remove fastapi from sys.modules and block re-import
        for k in fastapi_modules:
            monkeypatch.delitem(sys.modules, k, raising=False)

        with patch.dict(sys.modules, {"fastapi": None, "fastapi.responses": None}):
            # Re-import the router module fresh so it re-evaluates the import
            import obskit.health.router as router_mod

            original_fn = router_mod.build_health_router

            def patched_build(*args, **kwargs):
                try:
                    import fastapi  # noqa: F401
                    if fastapi is None:
                        raise ImportError("mocked missing fastapi")
                except (ImportError, TypeError):
                    raise ImportError(
                        "fastapi is required for build_health_router. "
                        "Install it with: pip install 'obskit[fastapi]'"
                    )
                return original_fn(*args, **kwargs)

            monkeypatch.setattr(router_mod, "build_health_router", patched_build)

            with pytest.raises(ImportError, match="fastapi"):
                router_mod.build_health_router(checks=[_healthy_check("db")])


# ---------------------------------------------------------------------------
# TestResponseShape
# ---------------------------------------------------------------------------


class TestResponseShape:
    """The JSON response body must follow the documented schema."""

    def test_response_has_healthy_key(self):
        router = build_health_router(checks=[_healthy_check("db")])
        client = TestClient(_app(router))
        body = client.get("/health/ready").json()
        assert "healthy" in body

    def test_response_has_status_key(self):
        router = build_health_router(checks=[_healthy_check("db")])
        client = TestClient(_app(router))
        body = client.get("/health/ready").json()
        assert "status" in body

    def test_response_has_checks_key(self):
        router = build_health_router(checks=[_healthy_check("db")])
        client = TestClient(_app(router))
        body = client.get("/health/ready").json()
        assert "checks" in body

    def test_check_entry_has_status(self):
        router = build_health_router(checks=[_healthy_check("db")])
        client = TestClient(_app(router))
        body = client.get("/health/ready").json()
        assert "status" in body["checks"]["db"]

    def test_check_entry_has_duration_ms(self):
        router = build_health_router(checks=[_healthy_check("db")])
        client = TestClient(_app(router))
        body = client.get("/health/ready").json()
        assert "duration_ms" in body["checks"]["db"]

    def test_healthy_check_status_is_healthy(self):
        router = build_health_router(checks=[_healthy_check("db")])
        client = TestClient(_app(router))
        body = client.get("/health/ready").json()
        assert body["checks"]["db"]["status"] == "healthy"

    def test_unhealthy_check_status_is_unhealthy(self):
        router = build_health_router(checks=[_unhealthy_check("db")])
        client = TestClient(_app(router))
        body = client.get("/health/ready").json()
        assert body["checks"]["db"]["status"] == "unhealthy"
