"""Prometheus multi-process mode support.

When running under gunicorn (or any multi-process server) each worker has its
own in-process metric state.  ``prometheus_client`` provides a file-based
aggregation mechanism: each worker writes its metrics to a shared directory
(``PROMETHEUS_MULTIPROC_DIR`` / ``prometheus_multiproc_dir``), and the
scrape endpoint merges them on the fly.

Usage
-----
Set the environment variable **before** importing ``prometheus_client``::

    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc

Then call :func:`setup_multiprocess_registry` once at application startup
(e.g. in ``lifespan`` or the gunicorn ``post_fork`` hook)::

    from obskit.metrics.multiprocess import setup_multiprocess_registry
    registry = setup_multiprocess_registry()

Pass *registry* to :func:`obskit.metrics.red.REDMetrics` or
:func:`obskit.metrics.types.Counter` to register metrics there instead of
the default ``REGISTRY``.

The helper :func:`make_multiprocess_app` returns a ready-to-mount ASGI/WSGI
app that serves the merged metrics output — drop it behind ``/metrics``
instead of the default ``prometheus_client.make_asgi_app()``.

Notes
-----
* ``PROMETHEUS_MULTIPROC_DIR`` must exist and be writable by all workers.
* Workers **must not** call ``prometheus_client.REGISTRY.unregister()`` on
  shared metrics — use a fresh ``CollectorRegistry(multiprocess=True)``
  returned by this module instead.
* This module is a no-op when ``prometheus_client`` is not installed.
"""

from __future__ import annotations

import logging
import os
from typing import Any

_logger = logging.getLogger(__name__)

try:
    import prometheus_client
    import prometheus_client.multiprocess
    from prometheus_client import CollectorRegistry

    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    PROMETHEUS_AVAILABLE = False
    CollectorRegistry = None  # type: ignore[misc, assignment]


def is_multiprocess_mode() -> bool:
    """Return *True* when the process is running in multiprocess mode.

    Multiprocess mode is active when the ``PROMETHEUS_MULTIPROC_DIR``
    (or its alias ``prometheus_multiproc_dir``) environment variable is set
    to a non-empty value.
    """
    return bool(
        os.environ.get("PROMETHEUS_MULTIPROC_DIR") or os.environ.get("prometheus_multiproc_dir")
    )


def setup_multiprocess_registry() -> Any:
    """Create and return a ``CollectorRegistry`` suitable for multiprocess use.

    In multiprocess mode (gunicorn / multi-worker) this returns a
    ``CollectorRegistry(multiprocess=True)`` that aggregates metrics from all
    worker files on ``collect()``.

    In single-process mode it returns the default ``prometheus_client.REGISTRY``
    so callers do not need to branch.

    Returns
    -------
    CollectorRegistry
        Registry to use for metric registration and scraping.

    Raises
    ------
    RuntimeError
        If multiprocess mode is active but the shared directory does not exist
        or is not writable — caught early to prevent silent data loss.
    """
    if not PROMETHEUS_AVAILABLE:  # pragma: no cover
        _logger.warning("prometheus_client not installed — multiprocess registry unavailable")
        return None

    if not is_multiprocess_mode():
        return prometheus_client.REGISTRY

    mp_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR") or os.environ.get(
        "prometheus_multiproc_dir", ""
    )

    if not os.path.isdir(mp_dir):
        # Attempt to create the directory — common in containerised setups where
        # the init container creates it just before the app starts.
        try:
            os.makedirs(mp_dir, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"PROMETHEUS_MULTIPROC_DIR={mp_dir!r} does not exist and could not be created: {exc}. "
                "Create the directory and ensure all workers can write to it."
            ) from exc
    if not os.access(mp_dir, os.W_OK):
        raise RuntimeError(f"PROMETHEUS_MULTIPROC_DIR={mp_dir!r} is not writable by this process.")

    try:
        registry = CollectorRegistry()
        prometheus_client.multiprocess.MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
    except (FileNotFoundError, PermissionError) as exc:
        _logger.warning(
            "prometheus_multiprocess_registry_write_failed: %s",
            exc,
            extra={"multiproc_dir": mp_dir},
        )
        raise RuntimeError(
            f"PROMETHEUS_MULTIPROC_DIR={mp_dir!r} became inaccessible during registry setup: {exc}"
        ) from exc
    _logger.info(
        "prometheus_multiprocess_registry_created",
        extra={"multiproc_dir": mp_dir},
    )
    return registry


def make_multiprocess_app() -> Any:
    """Return a WSGI app that serves aggregated multiprocess metrics.

    This is the correct replacement for ``prometheus_client.make_wsgi_app()``
    when running under gunicorn.  Mount it at ``/metrics``::

        from obskit.metrics.multiprocess import make_multiprocess_app
        metrics_app = make_multiprocess_app()
        # With gunicorn + uvicorn workers you'd mount via your router

    Returns
    -------
    WSGI callable or *None* if prometheus_client is not installed.
    """
    if not PROMETHEUS_AVAILABLE:  # pragma: no cover
        return None

    registry = setup_multiprocess_registry()
    return prometheus_client.make_wsgi_app(registry)


def _cleanup_worker_files(mp_dir: str, worker_pid: int) -> None:  # pragma: no cover
    """Delete stale ``.db`` metric files for *worker_pid* from *mp_dir*.

    prometheus_client names files like ``<metric_type>_<pid>.db``, so we
    match on the ``_<pid>.db`` suffix.  Errors are silently ignored because
    files may already be removed by a concurrent cleanup.
    """
    if not (mp_dir and os.path.isdir(mp_dir)):  # pragma: no cover
        return
    pid_suffix = f"_{worker_pid}.db"
    for filename in os.listdir(mp_dir):
        if filename.endswith(pid_suffix):
            try:
                os.unlink(os.path.join(mp_dir, filename))
            except OSError:
                pass  # Non-critical; file may already be removed


def child_exit(server: Any, worker: Any) -> None:  # pragma: no cover
    """Gunicorn ``child_exit`` server hook — cleans up worker metric files.

    Add this to your gunicorn config::

        from obskit.metrics.multiprocess import child_exit

    This prevents stale metric files from accumulating when workers restart.

    Parameters
    ----------
    server:
        Gunicorn Arbiter instance (passed by gunicorn).
    worker:
        Gunicorn Worker instance (passed by gunicorn).
    """
    if PROMETHEUS_AVAILABLE and is_multiprocess_mode():
        prometheus_client.multiprocess.mark_process_dead(worker.pid)  # type: ignore[no-untyped-call]

        # Also delete the worker's metric files so the multiprocess directory
        # does not accumulate stale files over repeated gunicorn reloads
        # (SIGHUP).
        mp_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR") or os.environ.get(
            "prometheus_multiproc_dir", ""
        )
        _cleanup_worker_files(mp_dir, worker.pid)
