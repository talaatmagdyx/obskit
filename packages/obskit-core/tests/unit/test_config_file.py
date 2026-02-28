"""Tests for obskit.config_file module."""
import json, os
from unittest.mock import patch
import pytest
from obskit.config_file import (
    _flatten_config, _load_json, _load_toml, _load_yaml,
    _restore_obskit_env_vars, _save_obskit_env_vars, configure_from_file,
)
from obskit.core.errors import ConfigFileNotFoundError, ConfigValidationError


class TestConfigureFromFileNotFound:
    def test_missing_yaml(self, tmp_path):
        with pytest.raises(ConfigFileNotFoundError):
            configure_from_file(tmp_path / "nonexistent.yaml")

    def test_missing_json(self):
        with pytest.raises(ConfigFileNotFoundError):
            configure_from_file("/no/such/dir/config.json")


class TestUnsupportedFormat:
    def test_xml_raises(self, tmp_path):
        f = tmp_path / "config.xml"
        f.write_text("<config/>", encoding="utf-8")
        with pytest.raises(ConfigValidationError, match="Unsupported"):
            configure_from_file(f)


class TestLoadJson:
    def test_simple(self, tmp_path):
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({"service_name": "svc"}))
        assert _load_json(p)["service_name"] == "svc"


class TestLoadYaml:
    def test_simple(self, tmp_path):
        pytest.importorskip("yaml")
        p = tmp_path / "cfg.yaml"
        p.write_text("service_name: myservice")
        assert _load_yaml(p)["service_name"] == "myservice"

    def test_empty(self, tmp_path):
        pytest.importorskip("yaml")
        p = tmp_path / "empty.yaml"
        p.write_text("")
        assert _load_yaml(p) == {}

    def test_missing_pyyaml_raises(self, tmp_path):
        p = tmp_path / "cfg.yaml"
        p.write_text("service_name: svc")
        import builtins
        real_import = builtins.__import__
        def _imp(name, *args, **kw):
            if name == "yaml":
                raise ImportError("no yaml")
            return real_import(name, *args, **kw)
        with patch("builtins.__import__", side_effect=_imp):
            with pytest.raises(ConfigValidationError, match="PyYAML"):
                _load_yaml(p)


class TestLoadToml:
    def _ensure_toml(self):
        try:
            import tomllib
        except ImportError:
            pytest.importorskip("tomli")

    def test_simple(self, tmp_path):
        self._ensure_toml()
        p = tmp_path / "cfg.toml"
        p.write_bytes('service_name = "toml-svc"'.encode())
        assert _load_toml(p)["service_name"] == "toml-svc"

    def test_tool_obskit(self, tmp_path):
        self._ensure_toml()
        p = tmp_path / "pyproject.toml"
        data = "[tool.obskit]\nservice_name = \"nested-svc\""
        p.write_bytes(data.encode())
        assert _load_toml(p)["service_name"] == "nested-svc"

    def test_obskit_section(self, tmp_path):
        self._ensure_toml()
        p = tmp_path / "cfg.toml"
        data = "[obskit]\nservice_name = \"obs-svc\""
        p.write_bytes(data.encode())
        assert _load_toml(p)["service_name"] == "obs-svc"


class TestConfigureFromFileJson:
    def test_basic(self, tmp_path):
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({"service_name": "json-svc", "environment": "test"}))
        assert configure_from_file(p).service_name == "json-svc"

    def test_nested_logging(self, tmp_path):
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({"service_name": "svc", "logging": {"level": "DEBUG"}}))
        assert configure_from_file(p).service_name == "svc"

    def test_parse_error(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{ invalid json }")
        with pytest.raises(ConfigValidationError, match="Failed to parse"):
            configure_from_file(p)

    def test_override_env_false(self, tmp_path, monkeypatch):
        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({"service_name": "file-svc"}))
        monkeypatch.setenv("OBSKIT_SERVICE_NAME", "env-svc")
        settings = configure_from_file(p, override_with_env=False)
        assert settings.service_name == "file-svc"


class TestConfigureFromFileYaml:
    def test_yaml(self, tmp_path):
        pytest.importorskip("yaml")
        p = tmp_path / "cfg.yaml"
        p.write_text("service_name: yaml-svc")
        assert configure_from_file(p).service_name == "yaml-svc"

    def test_yml_extension(self, tmp_path):
        pytest.importorskip("yaml")
        p = tmp_path / "cfg.yml"
        p.write_text("service_name: yml-svc")
        assert configure_from_file(p).service_name == "yml-svc"


class TestConfigureFromFileToml:
    def test_toml(self, tmp_path):
        try:
            import tomllib
        except ImportError:
            pytest.importorskip("tomli")
        p = tmp_path / "cfg.toml"
        p.write_bytes('service_name = "toml-svc"'.encode())
        assert configure_from_file(p).service_name == "toml-svc"


class TestFlattenConfig:
    def test_direct_keys(self):
        r = _flatten_config({"service_name": "s", "environment": "e", "version": "v"})
        assert r["service_name"] == "s"

    def test_logging(self):
        cfg = {"logging": {"level": "DEBUGI", "format": "text",
                           "include_timestamp": True, "sample_rate": 0.5, "backend": "sl"}}
        r = _flatten_config(cfg)
        assert r["log_level"] == "DEBUGI"
        assert r["log_format"] == "text"
        assert r["log_include_timestamp"] is True
        assert r["log_sample_rate"] == 0.5
        assert r["logging_backend"] == "sl"

    def test_metrics(self):
        cfg = {"metrics": {"enabled": True, "port": 9090, "path": "/m",
                           "method": "push", "auth_enabled": True, "auth_token": "s",
                           "rate_limit_enabled": True, "rate_limit_requests": 100,
                           "sample_rate": 0.1, "use_histogram": True, "use_summary": False}}
        r = _flatten_config(cfg)
        assert r["metrics_enabled"] is True
        assert r["metrics_port"] == 9090
        assert r["metrics_path"] == "/m"
        assert r["metrics_method"] == "push"
        assert r["metrics_auth_enabled"] is True
        assert r["metrics_auth_token"] == "s"
        assert r["metrics_rate_limit_enabled"] is True
        assert r["metrics_rate_limit_requests"] == 100
        assert r["metrics_sample_rate"] == 0.1
        assert r["use_histogram"] is True
        assert r["use_summary"] is False

    def test_tracing(self):
        cfg = {"tracing": {"enabled": True, "otlp_endpoint": "http://x",
                           "otlp_insecure": True, "sample_rate": 0.1,
                           "export_queue_size": 2048, "export_batch_size": 512,
                           "export_timeout": 5}}
        r = _flatten_config(cfg)
        assert r["tracing_enabled"] is True
        assert r["otlp_endpoint"] == "http://x"
        assert r["otlp_insecure"] is True
        assert r["trace_sample_rate"] == 0.1
        assert r["trace_export_queue_size"] == 2048
        assert r["trace_export_batch_size"] == 512
        assert r["trace_export_timeout"] == 5

    def test_health(self):
        r = _flatten_config({"health": {"check_timeout": 10}})
        assert r["health_check_timeout"] == 10

    def test_circuit_breaker(self):
        cfg = {"circuit_breaker": {"failure_threshold": 5,
                                    "recovery_timeout": 30, "half_open_requests": 3}}
        r = _flatten_config(cfg)
        assert r["circuit_breaker_failure_threshold"] == 5
        assert r["circuit_breaker_recovery_timeout"] == 30
        assert r["circuit_breaker_half_open_requests"] == 3

    def test_retry(self):
        cfg = {"retry": {"max_attempts": 5, "base_delay": 2.0,
                         "max_delay": 60.0, "exponential_base": 3.0}}
        r = _flatten_config(cfg)
        assert r["retry_max_attempts"] == 5
        assert r["retry_base_delay"] == 2.0
        assert r["retry_max_delay"] == 60.0
        assert r["retry_exponential_base"] == 3.0

    def test_rate_limit(self):
        r = _flatten_config({"rate_limit": {"requests": 100, "window_seconds": 60}})
        assert r["rate_limit_requests"] == 100
        assert r["rate_limit_window_seconds"] == 60

    def test_self_monitoring(self):
        cfg = {"self_monitoring": {"enabled": True, "async_queue_size": 1000}}
        r = _flatten_config(cfg)
        assert r["enable_self_metrics"] is True
        assert r["async_metric_queue_size"] == 1000

    def test_empty(self):
        assert _flatten_config({}) == {}


class TestEnvVarHelpers:
    def test_save_removes_obskit_vars(self, monkeypatch):
        monkeypatch.setenv("OBSKIT_SERVICE_NAME", "s")
        monkeypatch.setenv("OTHER_VAR", "o")
        saved = _save_obskit_env_vars()
        assert "OBSKIT_SERVICE_NAME" in saved
        assert "OTHER_VAR" not in saved
        assert "OBSKIT_SERVICE_NAME" not in os.environ

    def test_restore_puts_back(self, monkeypatch):
        monkeypatch.setenv("OBSKIT_SERVICE_NAME", "s")
        saved = _save_obskit_env_vars()
        _restore_obskit_env_vars(saved)
        assert os.environ.get("OBSKIT_SERVICE_NAME") == "s"

    def test_save_no_obskit_vars(self, monkeypatch):
        for k in list(os.environ.keys()):
            if k.startswith("OBSKIT_"): monkeypatch.delenv(k)
        assert _save_obskit_env_vars() == {}

    def test_restore_empty(self):
        _restore_obskit_env_vars({})


class TestFlattenConfigMissingBranches:
    """Tests that cover the False branches in _flatten_config for each section.
    
    Each section test uses an empty sub-dict so that all the 'if key in section:' checks
    are False, exercising the skip-to-next-check branches (e.g., 256->258).
    """

    def test_logging_section_empty_keys(self):
        """Test logging section with no keys (covers all 256->258, 258->260, etc.)."""
        from obskit.config_file import _flatten_config
        # Empty logging section - all if checks are False
        r = _flatten_config({"logging": {}})
        assert "log_level" not in r
        assert "log_format" not in r
        assert "log_include_timestamp" not in r
        assert "log_sample_rate" not in r
        assert "logging_backend" not in r

    def test_logging_section_partial_keys(self):
        """Test logging section with only some keys (some False branches)."""
        from obskit.config_file import _flatten_config
        # Only 'format' key, no 'level', 'include_timestamp', etc.
        r = _flatten_config({"logging": {"format": "json"}})
        assert "log_level" not in r
        assert r["log_format"] == "json"
        assert "log_include_timestamp" not in r

    def test_metrics_section_empty_keys(self):
        """Test metrics section with no keys (covers 270->272, 272->274, etc.)."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"metrics": {}})
        assert "metrics_enabled" not in r
        assert "metrics_port" not in r

    def test_metrics_section_partial_keys(self):
        """Test metrics section with only some keys."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"metrics": {"enabled": True, "use_histogram": True}})
        assert r["metrics_enabled"] is True
        assert r["use_histogram"] is True
        assert "metrics_port" not in r
        assert "metrics_path" not in r

    def test_tracing_section_empty_keys(self):
        """Test tracing section with no keys (covers 296->298, 298->300, etc.)."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"tracing": {}})
        assert "tracing_enabled" not in r
        assert "otlp_endpoint" not in r

    def test_tracing_section_partial_keys(self):
        """Test tracing section with only some keys."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"tracing": {"otlp_endpoint": "http://jaeger:4317"}})
        assert "tracing_enabled" not in r
        assert r["otlp_endpoint"] == "http://jaeger:4317"
        assert "otlp_insecure" not in r

    def test_health_section_empty_keys(self):
        """Test health section with no keys."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"health": {}})
        assert "health_check_timeout" not in r

    def test_circuit_breaker_section_empty_keys(self):
        """Test circuit_breaker section with no keys (covers 320->322, 322->324, etc.)."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"circuit_breaker": {}})
        assert "circuit_breaker_failure_threshold" not in r
        assert "circuit_breaker_recovery_timeout" not in r
        assert "circuit_breaker_half_open_requests" not in r

    def test_circuit_breaker_partial_keys(self):
        """Test circuit_breaker section with only failure_threshold."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"circuit_breaker": {"failure_threshold": 3}})
        assert r["circuit_breaker_failure_threshold"] == 3
        assert "circuit_breaker_recovery_timeout" not in r
        assert "circuit_breaker_half_open_requests" not in r

    def test_retry_section_empty_keys(self):
        """Test retry section with no keys (covers 330->332, 332->334, etc.)."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"retry": {}})
        assert "retry_max_attempts" not in r
        assert "retry_base_delay" not in r
        assert "retry_max_delay" not in r
        assert "retry_exponential_base" not in r

    def test_retry_partial_keys(self):
        """Test retry section with only max_attempts."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"retry": {"max_attempts": 3}})
        assert r["retry_max_attempts"] == 3
        assert "retry_base_delay" not in r
        assert "retry_max_delay" not in r

    def test_rate_limit_section_empty_keys(self):
        """Test rate_limit section with no keys (covers 342->344, 344->348)."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"rate_limit": {}})
        assert "rate_limit_requests" not in r
        assert "rate_limit_window_seconds" not in r

    def test_rate_limit_only_requests(self):
        """Test rate_limit section with only requests key."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"rate_limit": {"requests": 50}})
        assert r["rate_limit_requests"] == 50
        assert "rate_limit_window_seconds" not in r

    def test_self_monitoring_section_empty_keys(self):
        """Test self_monitoring section with no keys (covers 350->352, 352->355)."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"self_monitoring": {}})
        assert "enable_self_metrics" not in r
        assert "async_metric_queue_size" not in r

    def test_self_monitoring_only_enabled(self):
        """Test self_monitoring section with only enabled key."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"self_monitoring": {"enabled": False}})
        assert r["enable_self_metrics"] is False
        assert "async_metric_queue_size" not in r

    def test_metrics_all_secondary_keys(self):
        """Test metrics with all the secondary keys (method, auth_enabled, etc.)."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"metrics": {
            "method": "GET",
            "auth_enabled": True,
            "auth_token": "secret",
            "rate_limit_enabled": True,
            "rate_limit_requests": 100,
            "sample_rate": 1.0,
            "use_summary": True,
        }})
        assert r["metrics_method"] == "GET"
        assert r["metrics_auth_enabled"] is True
        assert r["metrics_auth_token"] == "secret"
        assert r["metrics_rate_limit_enabled"] is True
        assert r["metrics_rate_limit_requests"] == 100
        assert r["metrics_sample_rate"] == 1.0
        assert r["use_summary"] is True

    def test_tracing_all_secondary_keys(self):
        """Test tracing with all secondary keys."""
        from obskit.config_file import _flatten_config
        r = _flatten_config({"tracing": {
            "enabled": True,
            "otlp_insecure": True,
            "sample_rate": 0.5,
            "export_queue_size": 512,
            "export_batch_size": 64,
            "export_timeout": 30,
        }})
        assert r["tracing_enabled"] is True
        assert r["otlp_insecure"] is True
        assert r["trace_sample_rate"] == 0.5
        assert r["trace_export_queue_size"] == 512
        assert r["trace_export_batch_size"] == 64
        assert r["trace_export_timeout"] == 30
