"""
Gunicorn Config Mixin
=====================

Drop-in base class that wires obskit multiprocess Prometheus metrics into
your Gunicorn configuration with zero boilerplate.

Usage
-----
Inherit from :class:`ObskitGunicornConfig` instead of writing the hooks
yourself::

    # gunicorn.conf.py
    from obskit.integrations.gunicorn import ObskitGunicornConfig

    class GunicornConfig(ObskitGunicornConfig):
        bind = "0.0.0.0:8000"
        workers = 8
        worker_class = "uvicorn.workers.UvicornWorker"
        timeout = 30

This replaces the manual boilerplate that every multiprocess obskit user
previously needed to copy into their config file:

.. code-block:: python

    # Without ObskitGunicornConfig — manual version
    from obskit.metrics.multiprocess import setup_multiprocess_registry

    def on_starting(server):
        setup_multiprocess_registry()

    def child_exit(server, worker):
        from obskit.metrics.multiprocess import child_exit as _ce
        _ce(server, worker)

Notes
-----
* ``PROMETHEUS_MULTIPROC_DIR`` (or ``prometheus_multiproc_dir``) must be set
  **before** the master process starts, and the directory must exist and be
  writable by all workers.
* If you override any hook in your subclass, call ``super()`` to preserve
  obskit's setup::

      def on_starting(self, server):
          super().on_starting(server)
          # your custom code

* The mixin is a no-op when ``prometheus_client`` is not installed.
"""

from __future__ import annotations

from typing import Any


class ObskitGunicornConfig:
    """
    Gunicorn config base class that automatically wires obskit multiprocess
    Prometheus metrics.

    Inherit from this class in your ``gunicorn.conf.py`` to get:

    * **``on_starting``** — calls :func:`~obskit.metrics.multiprocess.setup_multiprocess_registry`
      in the master process before any workers are forked.
    * **``child_exit``** — calls :func:`~obskit.metrics.multiprocess.child_exit`
      in the master process when a worker exits, removing its per-worker
      ``.db`` file from ``PROMETHEUS_MULTIPROC_DIR``.

    Example
    -------
    .. code-block:: python

        from obskit.integrations.gunicorn import ObskitGunicornConfig

        class GunicornConfig(ObskitGunicornConfig):
            bind = "0.0.0.0:8000"
            workers = 8
            worker_class = "uvicorn.workers.UvicornWorker"
    """

    def on_starting(self, server: Any) -> None:
        """Called once in the master process before workers are forked.

        Sets up the Prometheus multiprocess registry so that
        ``PROMETHEUS_MULTIPROC_DIR`` is initialised before any worker
        inherits the process state.

        Parameters
        ----------
        server : gunicorn.arbiter.Arbiter
            The Gunicorn arbiter (master) instance.
        """
        from obskit.metrics.multiprocess import (  # noqa: PLC0415
            setup_multiprocess_registry,
        )

        setup_multiprocess_registry()

    def child_exit(self, server: Any, worker: Any) -> None:
        """Called in the master process when a worker exits.

        Cleans up the exiting worker's per-process ``.db`` files from
        ``PROMETHEUS_MULTIPROC_DIR`` so stale metrics are not included in
        subsequent scrapes.

        Parameters
        ----------
        server : gunicorn.arbiter.Arbiter
            The Gunicorn arbiter (master) instance.
        worker : gunicorn.workers.base.Worker
            The worker that just exited.
        """
        from obskit.metrics.multiprocess import (  # noqa: PLC0415
            child_exit as _obskit_child_exit,
        )

        _obskit_child_exit(server, worker)


__all__ = ["ObskitGunicornConfig"]
