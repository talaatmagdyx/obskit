"""Unit tests for obskit.integrations.gunicorn."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestObskitGunicornConfig:
    def test_on_starting_calls_setup_multiprocess_registry(self):
        from obskit.integrations.gunicorn import ObskitGunicornConfig

        cfg = ObskitGunicornConfig()
        mock_server = MagicMock()

        with patch(
            "obskit.metrics.multiprocess.setup_multiprocess_registry"
        ) as mock_setup:
            cfg.on_starting(mock_server)

        mock_setup.assert_called_once_with()

    def test_child_exit_calls_obskit_child_exit(self):
        from obskit.integrations.gunicorn import ObskitGunicornConfig

        cfg = ObskitGunicornConfig()
        mock_server = MagicMock()
        mock_worker = MagicMock()

        with patch(
            "obskit.metrics.multiprocess.child_exit"
        ) as mock_ce:
            cfg.child_exit(mock_server, mock_worker)

        mock_ce.assert_called_once_with(mock_server, mock_worker)

    def test_subclass_inherits_hooks(self):
        """Users can subclass and add their own attributes without breaking hooks."""
        from obskit.integrations.gunicorn import ObskitGunicornConfig

        class MyConfig(ObskitGunicornConfig):
            bind = "0.0.0.0:8000"
            workers = 8
            worker_class = "uvicorn.workers.UvicornWorker"

        cfg = MyConfig()
        assert cfg.bind == "0.0.0.0:8000"
        assert cfg.workers == 8

        mock_server = MagicMock()
        mock_worker = MagicMock()

        with patch("obskit.metrics.multiprocess.setup_multiprocess_registry") as ms, \
             patch("obskit.metrics.multiprocess.child_exit") as mce:
            cfg.on_starting(mock_server)
            cfg.child_exit(mock_server, mock_worker)

        ms.assert_called_once()
        mce.assert_called_once_with(mock_server, mock_worker)

    def test_subclass_can_super_on_starting(self):
        """Subclass overriding on_starting and calling super() still wires registry."""
        from obskit.integrations.gunicorn import ObskitGunicornConfig

        custom_called = []

        class MyConfig(ObskitGunicornConfig):
            def on_starting(self, server):
                super().on_starting(server)
                custom_called.append(True)

        cfg = MyConfig()
        with patch("obskit.metrics.multiprocess.setup_multiprocess_registry"):
            cfg.on_starting(MagicMock())

        assert custom_called == [True]

    def test_public_api(self):
        from obskit.integrations.gunicorn import ObskitGunicornConfig

        assert callable(ObskitGunicornConfig)
        cfg = ObskitGunicornConfig()
        assert hasattr(cfg, "on_starting")
        assert hasattr(cfg, "child_exit")

    def test_on_starting_passes_server_arg(self):
        """The server object received by on_starting is not forwarded to setup_multiprocess_registry."""
        from obskit.integrations.gunicorn import ObskitGunicornConfig

        cfg = ObskitGunicornConfig()
        sentinel_server = object()

        with patch("obskit.metrics.multiprocess.setup_multiprocess_registry") as mock_setup:
            cfg.on_starting(sentinel_server)

        mock_setup.assert_called_once_with()

    def test_child_exit_forwards_both_args(self):
        """Both server and worker are forwarded to child_exit unchanged."""
        from obskit.integrations.gunicorn import ObskitGunicornConfig

        cfg = ObskitGunicornConfig()
        sentinel_server = object()
        sentinel_worker = object()

        with patch("obskit.metrics.multiprocess.child_exit") as mock_ce:
            cfg.child_exit(sentinel_server, sentinel_worker)

        args = mock_ce.call_args.args
        assert args[0] is sentinel_server
        assert args[1] is sentinel_worker

    def test_on_starting_is_idempotent(self):
        """Calling on_starting twice calls setup twice (Gunicorn restart scenario)."""
        from obskit.integrations.gunicorn import ObskitGunicornConfig

        cfg = ObskitGunicornConfig()
        with patch("obskit.metrics.multiprocess.setup_multiprocess_registry") as mock_setup:
            cfg.on_starting(MagicMock())
            cfg.on_starting(MagicMock())

        assert mock_setup.call_count == 2

    def test_exported_from_obskit_namespace(self):
        """ObskitGunicornConfig is reachable via the top-level obskit package."""
        import obskit

        cls = obskit.ObskitGunicornConfig
        assert cls.__name__ == "ObskitGunicornConfig"

    def test_subclass_can_super_child_exit(self):
        """Subclass overriding child_exit and calling super() still cleans up worker."""
        from obskit.integrations.gunicorn import ObskitGunicornConfig

        cleanup_called = []

        class MyConfig(ObskitGunicornConfig):
            def child_exit(self, server, worker):
                super().child_exit(server, worker)
                cleanup_called.append(worker)

        cfg = MyConfig()
        mock_worker = MagicMock()

        with patch("obskit.metrics.multiprocess.child_exit") as mock_ce:
            cfg.child_exit(MagicMock(), mock_worker)

        mock_ce.assert_called_once()
        assert cleanup_called == [mock_worker]
