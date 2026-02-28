"""StatsD UDP emitter for fire-and-forget metric emission.

At millions of requests/second, even prometheus_client's in-process
lock can be a bottleneck.  This module provides a paper-thin UDP sender
that formats and emits StatsD datagrams with ~100 ns per call:

- No GIL-held lock acquisition on the hot path (UDP send is non-blocking).
- Stateless: one UDP socket shared across all threads (thread-safe by the OS).
- Graceful degradation: socket errors are silently swallowed so a downed
  StatsD agent never impacts request handling.

Usage::

    from obskit.metrics.statsd_emitter import StatsDEmitter

    emitter = StatsDEmitter(host="127.0.0.1", port=8125, prefix="myservice")
    emitter.emit_counter("requests", tags={"op": "create_order", "status": "ok"})
    emitter.emit_timing("latency_ms", value=45.2, tags={"op": "create_order"})
    emitter.emit_gauge("queue_depth", value=17.0)
    emitter.close()
"""

from __future__ import annotations

import socket
from typing import Any


def _build_tag_str(tags: dict[str, str] | None) -> str:
    """Render a DogStatsD-style tag string, e.g. ``|#key:val,key2:val2``."""
    if not tags:
        return ""
    return "|#" + ",".join(f"{k}:{v}" for k, v in sorted(tags.items()))


class StatsDEmitter:
    """Fire-and-forget StatsD UDP emitter.

    Parameters
    ----------
    host : str
        StatsD agent hostname or IP (default ``"127.0.0.1"``).
    port : int
        StatsD agent UDP port (default ``8125``).
    prefix : str
        Metric name prefix prepended to every metric (default ``""``).
        Example: ``"myservice"`` → metric name becomes ``"myservice.requests"``.

    Notes
    -----
    The emitter uses ``SOCK_DGRAM`` (UDP) and sets the socket to non-blocking
    mode.  A failed send (e.g. StatsD agent down, buffer full) is silently
    ignored — the business request is never impacted.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8125,
        prefix: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._prefix = f"{prefix}." if prefix else ""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)  # non-blocking: sendto never waits
        self._addr = (host, port)

    # ------------------------------------------------------------------
    # Hot-path emit methods (~100 ns each)
    # ------------------------------------------------------------------

    def emit_counter(
        self,
        metric: str,
        value: int = 1,
        sample_rate: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Emit a counter increment (StatsD ``c`` type).

        Parameters
        ----------
        metric : str
            Metric name (without prefix).
        value : int
            Increment amount (default 1).
        sample_rate : float
            Sampling rate sent to StatsD agent (default 1.0).
        tags : dict, optional
            DogStatsD-style tags.
        """
        suffix = f"|@{sample_rate:.2f}" if sample_rate < 1.0 else ""
        self._send(f"{self._prefix}{metric}:{value}|c{suffix}{_build_tag_str(tags)}")

    def emit_timing(
        self,
        metric: str,
        value: float,
        sample_rate: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Emit a timing value in milliseconds (StatsD ``ms`` type).

        Parameters
        ----------
        metric : str
            Metric name (without prefix).
        value : float
            Duration in **milliseconds**.
        sample_rate : float
            Sampling rate (default 1.0).
        tags : dict, optional
            DogStatsD-style tags.
        """
        suffix = f"|@{sample_rate:.2f}" if sample_rate < 1.0 else ""
        self._send(f"{self._prefix}{metric}:{value:.3f}|ms{suffix}{_build_tag_str(tags)}")

    def emit_gauge(
        self,
        metric: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Emit an absolute gauge value (StatsD ``g`` type).

        Parameters
        ----------
        metric : str
            Metric name (without prefix).
        value : float
            Gauge value.
        tags : dict, optional
            DogStatsD-style tags.
        """
        self._send(f"{self._prefix}{metric}:{value:.3f}|g{_build_tag_str(tags)}")

    def emit_histogram(
        self,
        metric: str,
        value: float,
        sample_rate: float = 1.0,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Emit a histogram sample (StatsD ``h`` type, DogStatsD extension).

        Parameters
        ----------
        metric : str
            Metric name (without prefix).
        value : float
            Sample value.
        sample_rate : float
            Sampling rate (default 1.0).
        tags : dict, optional
            DogStatsD-style tags.
        """
        suffix = f"|@{sample_rate:.2f}" if sample_rate < 1.0 else ""
        self._send(f"{self._prefix}{metric}:{value:.3f}|h{suffix}{_build_tag_str(tags)}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying UDP socket."""
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self) -> StatsDEmitter:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send(self, payload: str) -> None:
        """Encode and send a datagram; silently swallow errors."""
        try:
            self._sock.sendto(payload.encode(), self._addr)
        except OSError:
            # Buffer full, socket closed, network error — never raise.
            pass
