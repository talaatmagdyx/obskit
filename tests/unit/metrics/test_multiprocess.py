"""Tests for obskit.metrics.multiprocess — Prometheus multi-process mode support."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from obskit.metrics.multiprocess import is_multiprocess_mode, setup_multiprocess_registry


class TestIsMultiprocessMode:
    """is_multiprocess_mode() — environment variable detection."""

    def test_returns_false_when_env_not_set(self) -> None:
        """Returns False when neither env var is set."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PROMETHEUS_MULTIPROC_DIR", "prometheus_multiproc_dir")
        }
        with patch.dict(os.environ, env, clear=True):
            assert is_multiprocess_mode() is False

    def test_returns_true_when_uppercase_set(self) -> None:
        """Returns True when PROMETHEUS_MULTIPROC_DIR is set."""
        with patch.dict(os.environ, {"PROMETHEUS_MULTIPROC_DIR": "/tmp/prom"}):
            assert is_multiprocess_mode() is True

    def test_returns_true_when_lowercase_set(self) -> None:
        """Returns True when prometheus_multiproc_dir (lowercase alias) is set."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PROMETHEUS_MULTIPROC_DIR", "prometheus_multiproc_dir")
        }
        env["prometheus_multiproc_dir"] = "/tmp/prom"
        with patch.dict(os.environ, env, clear=True):
            assert is_multiprocess_mode() is True

    def test_returns_false_when_empty_string(self) -> None:
        """Returns False when env var is set to empty string."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PROMETHEUS_MULTIPROC_DIR", "prometheus_multiproc_dir")
        }
        env["PROMETHEUS_MULTIPROC_DIR"] = ""
        with patch.dict(os.environ, env, clear=True):
            assert is_multiprocess_mode() is False


class TestSetupMultiprocessRegistry:
    """setup_multiprocess_registry() — returns default REGISTRY in single-process mode."""

    def test_single_process_returns_default_registry(self) -> None:
        """In single-process mode (no env var), returns prometheus_client.REGISTRY."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PROMETHEUS_MULTIPROC_DIR", "prometheus_multiproc_dir")
        }
        with patch.dict(os.environ, env, clear=True):
            import prometheus_client

            result = setup_multiprocess_registry()
            assert result is prometheus_client.REGISTRY

    def test_multiprocess_dir_not_exists_creates_dir(self) -> None:
        """When multiprocess mode is set and dir doesn't exist, it's created."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PROMETHEUS_MULTIPROC_DIR", "prometheus_multiproc_dir")
        }
        env["PROMETHEUS_MULTIPROC_DIR"] = "/tmp/test_obskit_prom_mp"
        with patch.dict(os.environ, env, clear=True):
            with (
                patch("os.path.isdir", return_value=False),
                patch("os.makedirs") as mock_makedirs,
                patch("os.access", return_value=True),
                patch("obskit.metrics.multiprocess.CollectorRegistry", return_value=MagicMock()),
                patch("obskit.metrics.multiprocess.prometheus_client") as mock_pc,
            ):
                mock_pc.multiprocess = MagicMock()
                mock_pc.REGISTRY = MagicMock()
                setup_multiprocess_registry()
            mock_makedirs.assert_called_once()

    def test_multiprocess_dir_not_writable_raises(self) -> None:
        """When multiprocess dir is not writable, raises RuntimeError."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PROMETHEUS_MULTIPROC_DIR", "prometheus_multiproc_dir")
        }
        env["PROMETHEUS_MULTIPROC_DIR"] = "/tmp/test_obskit_prom_mp"
        with patch.dict(os.environ, env, clear=True):
            with patch("os.path.isdir", return_value=True), patch("os.access", return_value=False):
                with pytest.raises(RuntimeError, match="not writable"):
                    setup_multiprocess_registry()

    def test_multiprocess_dir_makedirs_fails_raises(self) -> None:
        """When makedirs fails with OSError, raises RuntimeError."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PROMETHEUS_MULTIPROC_DIR", "prometheus_multiproc_dir")
        }
        env["PROMETHEUS_MULTIPROC_DIR"] = "/nonexistent/path"
        with patch.dict(os.environ, env, clear=True):
            with (
                patch("os.path.isdir", return_value=False),
                patch("os.makedirs", side_effect=OSError("permission denied")),
            ):
                with pytest.raises(RuntimeError, match="does not exist"):
                    setup_multiprocess_registry()

    def test_multiprocess_registry_created_successfully(self) -> None:
        """When all conditions are met, returns the multiprocess registry."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PROMETHEUS_MULTIPROC_DIR", "prometheus_multiproc_dir")
        }
        env["PROMETHEUS_MULTIPROC_DIR"] = "/tmp/test_obskit_prom_mp"
        mock_registry = MagicMock()
        with patch.dict(os.environ, env, clear=True):
            with (
                patch("os.path.isdir", return_value=True),
                patch("os.access", return_value=True),
                patch("obskit.metrics.multiprocess.CollectorRegistry", return_value=mock_registry),
                patch("obskit.metrics.multiprocess.prometheus_client") as mock_pc,
            ):
                mock_pc.multiprocess = MagicMock()
                result = setup_multiprocess_registry()
        assert result is mock_registry

    def test_multiprocess_collector_file_not_found_raises(self) -> None:
        """When MultiProcessCollector raises FileNotFoundError, wraps in RuntimeError."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PROMETHEUS_MULTIPROC_DIR", "prometheus_multiproc_dir")
        }
        env["PROMETHEUS_MULTIPROC_DIR"] = "/tmp/test_obskit_prom_mp"
        with patch.dict(os.environ, env, clear=True):
            with (
                patch("os.path.isdir", return_value=True),
                patch("os.access", return_value=True),
                patch("obskit.metrics.multiprocess.CollectorRegistry", return_value=MagicMock()),
                patch("obskit.metrics.multiprocess.prometheus_client") as mock_pc,
            ):
                mock_pc.multiprocess.MultiProcessCollector.side_effect = FileNotFoundError("gone")
                with pytest.raises(RuntimeError, match="became inaccessible"):
                    setup_multiprocess_registry()


class TestMakeMultiprocessApp:
    """make_multiprocess_app() — returns a WSGI app."""

    def test_returns_wsgi_app_in_single_process_mode(self) -> None:
        """In single-process mode, returns prometheus_client default WSGI app."""
        from obskit.metrics.multiprocess import make_multiprocess_app

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PROMETHEUS_MULTIPROC_DIR", "prometheus_multiproc_dir")
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("obskit.metrics.multiprocess.prometheus_client") as mock_pc:
                mock_app = MagicMock()
                mock_pc.make_wsgi_app.return_value = mock_app
                mock_pc.REGISTRY = MagicMock()
                result = make_multiprocess_app()
            assert result is mock_app
