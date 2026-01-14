"""
Configuration File Loading
===========================

This module provides utilities for loading obskit configuration from
YAML, TOML, and JSON files.

Supported Formats
-----------------
- YAML (.yaml, .yml)
- TOML (.toml)
- JSON (.json)

Example - YAML Configuration
----------------------------
Create a file `obskit.yaml`:

.. code-block:: yaml

    service_name: order-service
    environment: production
    version: "1.0.0"

    logging:
      level: INFO
      format: json

    metrics:
      enabled: true
      port: 9090
      auth_enabled: true

    tracing:
      enabled: true
      otlp_endpoint: http://jaeger:4317
      sample_rate: 0.1

Then load it:

.. code-block:: python

    from obskit import configure_from_file

    configure_from_file("obskit.yaml")

Example - TOML Configuration
----------------------------
Create a file `obskit.toml`:

.. code-block:: toml

    service_name = "order-service"
    environment = "production"
    version = "1.0.0"

    [logging]
    level = "INFO"
    format = "json"

    [metrics]
    enabled = true
    port = 9090

Then load it:

.. code-block:: python

    from obskit import configure_from_file

    configure_from_file("obskit.toml")
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from obskit.config import ObskitSettings, configure
from obskit.core.errors import ConfigFileNotFoundError, ConfigValidationError


def configure_from_file(
    file_path: str | Path,
    override_with_env: bool = True,
) -> ObskitSettings:
    """
    Load obskit configuration from a file.

    Supports YAML, TOML, and JSON formats. The format is auto-detected
    based on the file extension.

    Parameters
    ----------
    file_path : str | Path
        Path to the configuration file.
    override_with_env : bool, default=True
        If True, environment variables (OBSKIT_*) override file values.

    Returns
    -------
    ObskitSettings
        The configured settings instance.

    Raises
    ------
    ConfigFileNotFoundError
        If the configuration file does not exist.
    ConfigValidationError
        If the configuration file is invalid.

    Example
    -------
    >>> from obskit import configure_from_file
    >>>
    >>> # Load from YAML
    >>> settings = configure_from_file("config/obskit.yaml")
    >>>
    >>> # Load from TOML
    >>> settings = configure_from_file("pyproject.toml")
    >>>
    >>> # Load from JSON
    >>> settings = configure_from_file("obskit.json")
    """
    path = Path(file_path)

    if not path.exists():
        raise ConfigFileNotFoundError(
            f"Configuration file not found: {file_path}",
            details={"file_path": str(file_path)},
        )

    # Determine format from extension
    suffix = path.suffix.lower()

    try:
        if suffix in (".yaml", ".yml"):
            config_dict = _load_yaml(path)
        elif suffix == ".toml":
            config_dict = _load_toml(path)
        elif suffix == ".json":
            config_dict = _load_json(path)
        else:
            raise ConfigValidationError(
                f"Unsupported configuration file format: {suffix}. "
                "Supported formats: .yaml, .yml, .toml, .json",
                details={"file_path": str(file_path), "extension": suffix},
            )
    except Exception as e:
        if isinstance(e, (ConfigFileNotFoundError, ConfigValidationError)):
            raise
        raise ConfigValidationError(
            f"Failed to parse configuration file: {e}",
            details={"file_path": str(file_path), "error": str(e)},
        ) from e

    # Flatten nested config (e.g., logging.level -> log_level)
    flat_config = _flatten_config(config_dict)

    # If override_with_env is False, we need to set env vars from file first
    if not override_with_env:
        # Clear any OBSKIT_* env vars temporarily
        saved_env = _save_obskit_env_vars()
        try:
            settings = configure(**flat_config)
        finally:
            _restore_obskit_env_vars(saved_env)
    else:
        # Normal behavior: env vars take precedence
        settings = configure(**flat_config)

    return settings


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as e:
        raise ConfigValidationError(
            "PyYAML is required to load YAML configuration files. Install with: pip install pyyaml",
            details={"file_path": str(path)},
        ) from e

    with open(path, encoding="utf-8") as f:
        result = yaml.safe_load(f)
        return dict(result) if result else {}


def _load_toml(path: Path) -> dict[str, Any]:
    """Load configuration from TOML file."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError as e:
            raise ConfigValidationError(
                "tomli is required to load TOML configuration files on Python < 3.11. "
                "Install with: pip install tomli",
                details={"file_path": str(path)},
            ) from e

    with open(path, "rb") as f:
        data: dict[str, Any] = tomllib.load(f)

    # Check if obskit config is under [tool.obskit] (pyproject.toml style)
    if "tool" in data and "obskit" in data["tool"]:
        return dict(data["tool"]["obskit"])

    # Check if obskit config is under [obskit] section
    if "obskit" in data:
        return dict(data["obskit"])

    # Otherwise, assume the whole file is obskit config
    return data


def _load_json(path: Path) -> dict[str, Any]:
    """Load configuration from JSON file."""
    with open(path, encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result


def _flatten_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Flatten nested configuration to obskit settings format.

    Converts nested structure like:
        logging:
          level: INFO
          format: json

    To flat structure like:
        log_level: INFO
        log_format: json
    """
    result: dict[str, Any] = {}

    # Direct mappings (top-level keys that match settings)
    direct_keys = [
        "service_name",
        "environment",
        "version",
    ]

    for key in direct_keys:
        if key in config:
            result[key] = config[key]

    # Logging section
    if "logging" in config:
        logging_config = config["logging"]
        if "level" in logging_config:
            result["log_level"] = logging_config["level"]
        if "format" in logging_config:
            result["log_format"] = logging_config["format"]
        if "include_timestamp" in logging_config:
            result["log_include_timestamp"] = logging_config["include_timestamp"]
        if "sample_rate" in logging_config:
            result["log_sample_rate"] = logging_config["sample_rate"]
        if "backend" in logging_config:
            result["logging_backend"] = logging_config["backend"]

    # Metrics section
    if "metrics" in config:
        metrics_config = config["metrics"]
        if "enabled" in metrics_config:
            result["metrics_enabled"] = metrics_config["enabled"]
        if "port" in metrics_config:
            result["metrics_port"] = metrics_config["port"]
        if "path" in metrics_config:
            result["metrics_path"] = metrics_config["path"]
        if "method" in metrics_config:
            result["metrics_method"] = metrics_config["method"]
        if "auth_enabled" in metrics_config:
            result["metrics_auth_enabled"] = metrics_config["auth_enabled"]
        if "auth_token" in metrics_config:
            result["metrics_auth_token"] = metrics_config["auth_token"]
        if "rate_limit_enabled" in metrics_config:
            result["metrics_rate_limit_enabled"] = metrics_config["rate_limit_enabled"]
        if "rate_limit_requests" in metrics_config:
            result["metrics_rate_limit_requests"] = metrics_config["rate_limit_requests"]
        if "sample_rate" in metrics_config:
            result["metrics_sample_rate"] = metrics_config["sample_rate"]
        if "use_histogram" in metrics_config:
            result["use_histogram"] = metrics_config["use_histogram"]
        if "use_summary" in metrics_config:
            result["use_summary"] = metrics_config["use_summary"]

    # Tracing section
    if "tracing" in config:
        tracing_config = config["tracing"]
        if "enabled" in tracing_config:
            result["tracing_enabled"] = tracing_config["enabled"]
        if "otlp_endpoint" in tracing_config:
            result["otlp_endpoint"] = tracing_config["otlp_endpoint"]
        if "otlp_insecure" in tracing_config:
            result["otlp_insecure"] = tracing_config["otlp_insecure"]
        if "sample_rate" in tracing_config:
            result["trace_sample_rate"] = tracing_config["sample_rate"]
        if "export_queue_size" in tracing_config:
            result["trace_export_queue_size"] = tracing_config["export_queue_size"]
        if "export_batch_size" in tracing_config:
            result["trace_export_batch_size"] = tracing_config["export_batch_size"]
        if "export_timeout" in tracing_config:
            result["trace_export_timeout"] = tracing_config["export_timeout"]

    # Health section
    if "health" in config:
        health_config = config["health"]
        if "check_timeout" in health_config:
            result["health_check_timeout"] = health_config["check_timeout"]

    # Circuit breaker section
    if "circuit_breaker" in config:
        cb_config = config["circuit_breaker"]
        if "failure_threshold" in cb_config:
            result["circuit_breaker_failure_threshold"] = cb_config["failure_threshold"]
        if "recovery_timeout" in cb_config:
            result["circuit_breaker_recovery_timeout"] = cb_config["recovery_timeout"]
        if "half_open_requests" in cb_config:
            result["circuit_breaker_half_open_requests"] = cb_config["half_open_requests"]

    # Retry section
    if "retry" in config:
        retry_config = config["retry"]
        if "max_attempts" in retry_config:
            result["retry_max_attempts"] = retry_config["max_attempts"]
        if "base_delay" in retry_config:
            result["retry_base_delay"] = retry_config["base_delay"]
        if "max_delay" in retry_config:
            result["retry_max_delay"] = retry_config["max_delay"]
        if "exponential_base" in retry_config:
            result["retry_exponential_base"] = retry_config["exponential_base"]

    # Rate limiting section
    if "rate_limit" in config:
        rl_config = config["rate_limit"]
        if "requests" in rl_config:
            result["rate_limit_requests"] = rl_config["requests"]
        if "window_seconds" in rl_config:
            result["rate_limit_window_seconds"] = rl_config["window_seconds"]

    # Self-monitoring section
    if "self_monitoring" in config:
        sm_config = config["self_monitoring"]
        if "enabled" in sm_config:
            result["enable_self_metrics"] = sm_config["enabled"]
        if "async_queue_size" in sm_config:
            result["async_metric_queue_size"] = sm_config["async_queue_size"]

    return result


def _save_obskit_env_vars() -> dict[str, str]:
    """Save all OBSKIT_* environment variables."""
    saved = {}
    for key, value in os.environ.items():
        if key.startswith("OBSKIT_"):
            saved[key] = value

    for key in saved:
        del os.environ[key]

    return saved


def _restore_obskit_env_vars(saved: dict[str, str]) -> None:
    """Restore saved OBSKIT_* environment variables."""
    for key, value in saved.items():
        os.environ[key] = value
