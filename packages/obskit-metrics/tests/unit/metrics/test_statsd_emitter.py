"""Tests for obskit.metrics.statsd_emitter."""

import socket

from obskit.metrics.statsd_emitter import StatsDEmitter, _build_tag_str


class TestBuildTagStr:
    """Unit tests for _build_tag_str helper."""

    def test_empty_tags_returns_empty_string(self):
        assert _build_tag_str(None) == ""
        assert _build_tag_str({}) == ""

    def test_single_tag(self):
        result = _build_tag_str({"op": "search"})
        assert result == "|#op:search"

    def test_multiple_tags_sorted(self):
        result = _build_tag_str({"z": "1", "a": "2"})
        # Sorted by key
        assert result == "|#a:2,z:1"


class TestStatsDEmitter:
    """Tests for StatsDEmitter."""

    def _make_server(self):
        """Create a UDP server socket bound to a random port."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        srv.bind(("127.0.0.1", 0))
        srv.settimeout(1.0)
        port = srv.getsockname()[1]
        return srv, port

    def test_emit_counter_basic(self):
        srv, port = self._make_server()
        with StatsDEmitter(host="127.0.0.1", port=port, prefix="svc") as emitter:
            emitter.emit_counter("requests")
        data, _ = srv.recvfrom(4096)
        srv.close()
        assert data == b"svc.requests:1|c"

    def test_emit_counter_with_value(self):
        srv, port = self._make_server()
        with StatsDEmitter(host="127.0.0.1", port=port) as emitter:
            emitter.emit_counter("hits", value=5)
        data, _ = srv.recvfrom(4096)
        srv.close()
        assert data == b"hits:5|c"

    def test_emit_counter_with_sample_rate(self):
        srv, port = self._make_server()
        with StatsDEmitter(host="127.0.0.1", port=port) as emitter:
            emitter.emit_counter("hits", sample_rate=0.1)
        data, _ = srv.recvfrom(4096)
        srv.close()
        assert b"|@0.10" in data

    def test_emit_counter_with_tags(self):
        srv, port = self._make_server()
        with StatsDEmitter(host="127.0.0.1", port=port) as emitter:
            emitter.emit_counter("req", tags={"op": "search"})
        data, _ = srv.recvfrom(4096)
        srv.close()
        assert b"#op:search" in data

    def test_emit_timing(self):
        srv, port = self._make_server()
        with StatsDEmitter(host="127.0.0.1", port=port, prefix="svc") as emitter:
            emitter.emit_timing("latency_ms", value=45.2)
        data, _ = srv.recvfrom(4096)
        srv.close()
        assert b"svc.latency_ms:45.200|ms" == data

    def test_emit_gauge(self):
        srv, port = self._make_server()
        with StatsDEmitter(host="127.0.0.1", port=port, prefix="svc") as emitter:
            emitter.emit_gauge("queue_depth", value=17.0)
        data, _ = srv.recvfrom(4096)
        srv.close()
        assert b"svc.queue_depth:17.000|g" == data

    def test_emit_histogram(self):
        srv, port = self._make_server()
        with StatsDEmitter(host="127.0.0.1", port=port) as emitter:
            emitter.emit_histogram("response_size", value=1024.0)
        data, _ = srv.recvfrom(4096)
        srv.close()
        assert b"|h" in data

    def test_no_prefix_omits_dot(self):
        srv, port = self._make_server()
        with StatsDEmitter(host="127.0.0.1", port=port, prefix="") as emitter:
            emitter.emit_counter("requests")
        data, _ = srv.recvfrom(4096)
        srv.close()
        assert data == b"requests:1|c"

    def test_socket_error_silently_ignored(self):
        """Sending to an unreachable host should not raise."""
        # Port 1 is typically unreachable/refused — but UDP is fire-and-forget
        emitter = StatsDEmitter(host="127.0.0.1", port=1)
        emitter.emit_counter("test")  # should not raise
        emitter.close()

    def test_close_twice_does_not_raise(self):
        emitter = StatsDEmitter()
        emitter.close()
        emitter.close()  # second close should not raise

    def test_context_manager_closes_socket(self):
        srv, port = self._make_server()
        srv.close()
        emitter = StatsDEmitter(host="127.0.0.1", port=port)
        with emitter:
            pass  # NOSONAR
        # After exiting context, socket is closed
        emitter.emit_counter("test")  # should not raise (error swallowed)
