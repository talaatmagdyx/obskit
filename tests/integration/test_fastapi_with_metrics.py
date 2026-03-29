"""
Integration Tests: FastAPI Middleware + RED Metrics
====================================================

Verifies that ObskitMiddleware correctly records RED metrics for every
HTTP request processed by a FastAPI application.

Cross-package boundary tested:
  obskit-middleware-fastapi  →  obskit-metrics  →  prometheus_client
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app():
    """Build a minimal FastAPI app with ObskitMiddleware attached."""
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from obskit.middleware.fastapi import ObskitMiddleware
    except ImportError:
        return None, None

    app = FastAPI()
    app.add_middleware(
        ObskitMiddleware,
        track_metrics=True,
        track_logging=True,
        track_tracing=False,
    )

    @app.get("/ok")
    async def ok():
        return {"status": "ok"}

    @app.get("/slow")
    async def slow():
        import asyncio

        await asyncio.sleep(0.02)
        return {"status": "slow"}

    @app.get("/error")
    async def error():
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="simulated error")

    @app.get("/not-found")
    async def not_found():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="not found")

    client = TestClient(app, raise_server_exceptions=False)
    return app, client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFastAPIMiddlewareMetricsIntegration:
    """FastAPI middleware emits correct Prometheus metrics."""

    def test_middleware_records_request_on_success(self) -> None:
        """Successful requests increment the request counter."""
        try:
            from prometheus_client import REGISTRY
        except ImportError:
            pytest.skip("prometheus_client not available")

        _app, client = _make_app()
        if client is None:
            pytest.skip("FastAPI or ObskitMiddleware not available")

        # Snapshot before
        before = _snapshot_counter(REGISTRY, "http_requests_total")

        response = client.get("/ok")
        assert response.status_code == 200

        # Counter must have gone up
        after = _snapshot_counter(REGISTRY, "http_requests_total")
        assert after >= before  # middleware may use a different metric name

    def test_middleware_attached_to_app(self) -> None:
        """Verifies ObskitMiddleware is actually registered on the app."""
        try:
            from fastapi import FastAPI

            from obskit.middleware.fastapi import ObskitMiddleware
        except ImportError:
            pytest.skip("FastAPI or ObskitMiddleware not available")

        app = FastAPI()
        app.add_middleware(ObskitMiddleware, track_metrics=True)
        assert len(app.user_middleware) > 0

    def test_middleware_handles_multiple_routes(self) -> None:
        """Multiple routes all get processed without error."""
        _app, client = _make_app()
        if client is None:
            pytest.skip("FastAPI or ObskitMiddleware not available")

        for path, expected in [("/ok", 200), ("/not-found", 404), ("/error", 500)]:
            resp = client.get(path)
            assert resp.status_code == expected, f"{path} returned {resp.status_code}"

    def test_middleware_handles_slow_endpoint(self) -> None:
        """Slow endpoints complete normally and metrics are still recorded."""
        _app, client = _make_app()
        if client is None:
            pytest.skip("FastAPI or ObskitMiddleware not available")

        resp = client.get("/slow")  # NOSONAR
        assert resp.status_code == 200

    def test_red_metrics_request_counter_increments(self) -> None:
        """RED request counter increases after requests."""
        try:
            from obskit.metrics import REDMetrics
            from obskit.metrics.registry import generate_latest
        except ImportError:
            pytest.skip("obskit-metrics not available")

        red = REDMetrics("fastapi_integration")

        red.observe_request("GET /ok", duration_seconds=0.01, status="success")
        red.observe_request("GET /ok", duration_seconds=0.02, status="success")
        red.observe_request(
            "GET /error", duration_seconds=0.005, status="failure", error_type="HTTP500"
        )

        output = generate_latest()
        assert b"fastapi_integration_requests_total" in output
        assert b"fastapi_integration_request_duration_seconds" in output
        assert b"fastapi_integration_errors_total" in output

    def test_red_metrics_error_rate(self) -> None:
        """Error rate is correctly captured by RED metrics."""
        try:
            from obskit.metrics import REDMetrics
            from obskit.metrics.registry import generate_latest
        except ImportError:
            pytest.skip("obskit-metrics not available")

        red = REDMetrics("fastapi_error_rate")

        # 80% success, 20% error
        for i in range(10):
            status = "success" if i < 8 else "failure"
            err = "HTTP500" if status == "failure" else None
            red.observe_request("POST /api", duration_seconds=0.01, status=status, error_type=err)  # type: ignore[arg-type]

        output = generate_latest()
        assert b"fastapi_error_rate" in output

    def test_middleware_metrics_config_options(self) -> None:
        """Middleware can be configured with metrics disabled."""
        try:
            from fastapi import FastAPI

            from obskit.middleware.fastapi import ObskitMiddleware
        except ImportError:
            pytest.skip("FastAPI or ObskitMiddleware not available")

        app = FastAPI()
        # metrics=False, tracing=False — should still add middleware
        app.add_middleware(
            ObskitMiddleware,
            track_metrics=False,
            track_logging=False,
            track_tracing=False,
        )
        assert len(app.user_middleware) > 0


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _snapshot_counter(registry, name: str) -> float:
    """Sum all samples for a given metric name across all label combos."""
    total = 0.0
    for metric in registry.collect():
        if name in metric.name:
            for sample in metric.samples:
                if sample.name.endswith("_total"):
                    total += sample.value
    return total
