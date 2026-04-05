"""Tests for obskit.health.server (WorkerHealthServer)."""

from __future__ import annotations

import http.client
import json
import time

import pytest

from obskit.health.server import WorkerHealthServer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server():
    """Start a WorkerHealthServer on a random OS-assigned port."""
    s = WorkerHealthServer(port=0, checks={"ok": lambda: True})
    s._start_sync()
    port = s._server.server_address[1]
    time.sleep(0.05)  # give thread time to bind and serve
    yield s, port
    s.stop()


@pytest.fixture
def failing_server():
    """Start a WorkerHealthServer whose single check always fails."""
    s = WorkerHealthServer(port=0, checks={"bad": lambda: False})
    s._start_sync()
    port = s._server.server_address[1]
    time.sleep(0.05)
    yield s, port
    s.stop()


def _get(port: int, path: str) -> http.client.HTTPResponse:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    return resp


# ---------------------------------------------------------------------------
# TestWorkerHealthServerEvaluate
# ---------------------------------------------------------------------------


class TestWorkerHealthServerEvaluate:
    """Unit tests for _evaluate() — no HTTP involved."""

    def test_all_checks_pass(self):
        s = WorkerHealthServer(
            port=0, checks={"a": lambda: True, "b": lambda: True}
        )
        ok, body = s._evaluate()
        assert ok is True
        assert body["status"] == "ok"
        assert body["checks"]["a"]["status"] == "ok"
        assert body["checks"]["b"]["status"] == "ok"

    def test_check_returns_falsy(self):
        s = WorkerHealthServer(port=0, checks={"c": lambda: False})
        ok, body = s._evaluate()
        assert ok is False
        assert body["checks"]["c"]["status"] == "fail"

    def test_check_raises_exception(self):
        exc = RuntimeError("something broke")

        def bad_check():
            raise exc

        s = WorkerHealthServer(port=0, checks={"boom": bad_check})
        ok, body = s._evaluate()
        assert ok is False
        assert body["checks"]["boom"]["status"] == "error"
        assert "something broke" in body["checks"]["boom"]["detail"]

    def test_no_silence_check_when_not_configured(self):
        s = WorkerHealthServer(port=0, checks={"x": lambda: True})
        _, body = s._evaluate()
        assert "activity" not in body["checks"]

    def test_silence_within_threshold(self):
        s = WorkerHealthServer(
            port=0,
            checks={},
            max_silence_seconds=60,
        )
        s.record_activity()
        ok, body = s._evaluate()
        assert ok is True
        assert body["checks"]["activity"]["status"] == "ok"

    def test_silence_exceeded(self):
        s = WorkerHealthServer(
            port=0,
            checks={},
            max_silence_seconds=0.001,
        )
        time.sleep(0.005)
        ok, body = s._evaluate()
        assert ok is False
        assert body["checks"]["activity"]["status"] == "stale"

    def test_record_activity_resets_timer(self):
        s = WorkerHealthServer(
            port=0,
            checks={},
            max_silence_seconds=0.001,
        )
        time.sleep(0.005)
        # At this point silence is exceeded
        ok_before, _ = s._evaluate()
        assert ok_before is False

        # Reset the timer
        s.record_activity()
        ok_after, body_after = s._evaluate()
        assert ok_after is True
        assert body_after["checks"]["activity"]["status"] == "ok"


# ---------------------------------------------------------------------------
# TestWorkerHealthServerHTTP
# ---------------------------------------------------------------------------


class TestWorkerHealthServerHTTP:
    """Integration tests — real HTTP requests to the background thread."""

    def test_health_returns_200_when_healthy(self, server):
        _, port = server
        resp = _get(port, "/health")
        assert resp.status == 200

    def test_health_returns_503_when_check_fails(self, failing_server):
        _, port = failing_server
        resp = _get(port, "/health")
        assert resp.status == 503

    def test_unknown_path_returns_404(self, server):
        _, port = server
        resp = _get(port, "/unknown")
        assert resp.status == 404

    def test_live_path_accepted(self, server):
        _, port = server
        resp = _get(port, "/live")
        assert resp.status == 200

    def test_ready_path_accepted(self, server):
        _, port = server
        resp = _get(port, "/ready")
        assert resp.status == 200

    def test_response_is_json(self, server):
        _, port = server
        resp = _get(port, "/health")
        body = resp.read()
        parsed = json.loads(body)
        assert "status" in parsed
        assert "checks" in parsed

    def test_stop_shuts_down_server(self):
        s = WorkerHealthServer(port=0, checks={"ok": lambda: True})
        s._start_sync()
        thread = s._thread
        assert thread is not None
        assert thread.is_alive()
        s.stop()
        assert not thread.is_alive()

    def test_stop_before_start_is_safe(self):
        """stop() called without start() must not raise."""
        s = WorkerHealthServer(port=0, checks={})
        assert s._server is None
        assert s._thread is None
        s.stop()  # should be a no-op


# ---------------------------------------------------------------------------
# TestWorkerHealthServerAPI
# ---------------------------------------------------------------------------


class TestWorkerHealthServerAPI:
    """Tests for the public API surface of WorkerHealthServer."""

    def test_port_property(self):
        s = WorkerHealthServer(port=9999, checks={})
        assert s.port == 9999

    def test_start_sync_works(self):
        s = WorkerHealthServer(port=0, checks={"ok": lambda: True})
        s.start_sync()
        assert s._thread is not None
        assert s._thread.is_alive()
        s.stop()

    def test_record_activity_updates_timestamp(self):
        s = WorkerHealthServer(port=0, checks={})
        before = s._last_activity
        time.sleep(0.01)
        s.record_activity()
        after = s._last_activity
        assert after > before

    @pytest.mark.asyncio
    async def test_start_async_works(self):
        """async start() should also spin up the server."""
        s = WorkerHealthServer(port=0, checks={"ok": lambda: True})
        await s.start()
        assert s._thread is not None
        assert s._thread.is_alive()
        s.stop()
