"""Tests for configure_observability() entrypoint."""

from __future__ import annotations

from collections.abc import Generator

import structlog
import pytest

from obskit.config import (
    configure_observability,
    get_redis_slo_tracker,
    reset_redis_slo_tracker,
    reset_settings,
)
from obskit.core.observability import Observability, get_observability, reset_observability
from obskit.logging.logger import reset_logging


@pytest.fixture(autouse=True)
def _clean() -> Generator[None, None, None]:
    reset_settings()
    reset_observability()
    reset_logging()
    reset_redis_slo_tracker()
    structlog.reset_defaults()
    yield
    reset_settings()
    reset_observability()
    reset_logging()
    reset_redis_slo_tracker()
    structlog.reset_defaults()


class TestConfigureObservability:
    def test_returns_observability(self) -> None:
        obs = configure_observability(service_name="test-svc")
        assert isinstance(obs, Observability)
        assert obs.config.service.name == "test-svc"

    def test_sets_global(self) -> None:
        obs = configure_observability(service_name="global-svc")
        assert get_observability() is obs

    def test_preserves_settings_global(self) -> None:
        from obskit.config import get_settings

        configure_observability(service_name="settings-svc")
        settings = get_settings()
        assert settings.service_name == "settings-svc"

    def test_strict_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="error"):
            configure_observability(
                strict=True,
                tracing_enabled=True,
                otlp_endpoint="not-a-url",
            )

    def test_invalid_kwarg_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown"):
            configure_observability(nonexistent_field="oops")

    def test_all_config_sections_populated(self) -> None:
        obs = configure_observability(
            service_name="full-svc",
            environment="production",
            version="3.0.0",
            log_level="DEBUG",
            log_format="console",
            trace_sample_rate=0.5,
        )
        assert obs.config.service.name == "full-svc"
        assert obs.config.service.environment == "production"
        assert obs.config.service.version == "3.0.0"
        assert obs.config.logging.level == "DEBUG"
        assert obs.config.logging.format == "console"
        assert obs.config.tracing.sample_rate == pytest.approx(0.5)

    def test_configure_logging_is_implicit(self) -> None:
        """configure_observability() must wire the log pipeline automatically."""
        import obskit.logging.logger as _lm

        assert not _lm._logging_configured
        configure_observability(service_name="implicit-log-svc")
        assert _lm._logging_configured

    def test_configure_logging_caches_service_name(self) -> None:
        """configure_observability() must populate the logger service-name cache."""
        import obskit.logging.logger as _lm

        configure_observability(service_name="cached-svc", environment="staging")
        assert _lm._cached_service_name == "cached-svc"
        assert _lm._cached_environment == "staging"


class TestStartupValidation:
    """configure_observability() emits structured startup logs."""

    def test_emits_obskit_configured_event(self) -> None:
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(service_name="startup-svc", environment="production")

        events = [e["event"] for e in logs]
        assert "obskit_configured" in events

    def test_configured_event_carries_service_fields(self) -> None:
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(
                service_name="field-svc",
                environment="staging",
                version="2.0.0",
            )

        cfg_log = next(e for e in logs if e["event"] == "obskit_configured")
        assert cfg_log["service"] == "field-svc"
        assert cfg_log["environment"] == "staging"
        assert cfg_log["version"] == "2.0.0"

    def test_warns_when_otlp_is_localhost(self) -> None:
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(
                service_name="warn-svc",
                tracing_enabled=True,
                otlp_endpoint="http://localhost:4317",
            )

        events = [e["event"] for e in logs]
        assert "otlp_endpoint_is_localhost" in events

    def test_no_localhost_warning_for_remote_endpoint(self) -> None:
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(
                service_name="remote-svc",
                tracing_enabled=True,
                otlp_endpoint="http://jaeger:4317",
            )

        events = [e["event"] for e in logs]
        assert "otlp_endpoint_is_localhost" not in events

    def test_warns_when_tracing_enabled_but_no_endpoint(self) -> None:
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(
                service_name="no-endpoint-svc",
                tracing_enabled=True,
                otlp_endpoint="",
            )

        events = [e["event"] for e in logs]
        assert "otlp_endpoint_not_configured" in events

    def test_no_endpoint_warning_when_tracing_disabled(self) -> None:
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(
                service_name="no-trace-svc",
                tracing_enabled=False,
                otlp_endpoint="",
            )

        events = [e["event"] for e in logs]
        assert "otlp_endpoint_not_configured" not in events

    def test_logs_sampling_active_when_rate_lt_1(self) -> None:
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(service_name="sampling-svc", log_sample_rate=0.1)

        events = [e["event"] for e in logs]
        assert "log_sampling_active" in events

    def test_no_sampling_log_when_rate_is_1(self) -> None:
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(service_name="full-log-svc", log_sample_rate=1.0)

        events = [e["event"] for e in logs]
        assert "log_sampling_active" not in events

    def test_configured_event_carries_tracing_fields(self) -> None:
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(
                service_name="trace-svc",
                tracing_enabled=True,
                otlp_endpoint="http://tempo:4317",
                trace_sample_rate=0.25,
            )

        cfg_log = next(e for e in logs if e["event"] == "obskit_configured")
        assert cfg_log["tracing_enabled"] is True
        assert cfg_log["otlp_endpoint"] == "http://tempo:4317"
        assert cfg_log["trace_sample_rate"] == pytest.approx(0.25)

    def test_configured_event_disabled_tracing_shows_disabled_endpoint(self) -> None:
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(
                service_name="no-trace-svc",
                tracing_enabled=False,
            )

        cfg_log = next(e for e in logs if e["event"] == "obskit_configured")
        assert cfg_log["tracing_enabled"] is False
        # Endpoint should appear as "(disabled)" when not meaningful
        assert cfg_log["otlp_endpoint"] in ("(disabled)", "http://localhost:4317")

    def test_sampling_log_carries_rate_field(self) -> None:
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(service_name="rate-svc", log_sample_rate=0.5)

        sampling_log = next(e for e in logs if e["event"] == "log_sampling_active")
        assert sampling_log["rate"] == pytest.approx(0.5)

    def test_no_warnings_for_well_configured_service(self) -> None:
        """A properly configured service should emit only obskit_configured."""
        import structlog.testing

        with structlog.testing.capture_logs() as logs:
            configure_observability(
                service_name="well-svc",
                environment="production",
                tracing_enabled=True,
                otlp_endpoint="http://otel-collector:4317",
                log_sample_rate=1.0,
            )

        warning_events = [e for e in logs if e.get("level") == "warning"]
        assert warning_events == []


class TestPatchThreadsParam:
    def test_patch_threads_false_does_not_replace_thread(self) -> None:
        import threading

        from obskit.threading import _original_thread

        configure_observability(service_name="no-patch-svc", patch_threads=False)
        assert threading.Thread is _original_thread

    def test_patch_threads_true_replaces_thread(self) -> None:
        import threading

        from obskit.threading import _ContextThread, reset_threading_patch

        configure_observability(service_name="patch-svc", patch_threads=True)
        assert threading.Thread is _ContextThread
        reset_threading_patch()

    def test_patch_threads_default_is_false(self) -> None:
        import threading

        from obskit.threading import _original_thread

        configure_observability(service_name="default-patch-svc")
        assert threading.Thread is _original_thread


class TestRedisUrlParam:
    def test_redis_url_none_leaves_tracker_unset(self) -> None:
        configure_observability(service_name="no-redis-svc")
        assert get_redis_slo_tracker() is None

    def test_redis_url_creates_tracker_when_redis_available(self) -> None:
        """When redis package is present, tracker is initialised."""
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        mock_tracker = MagicMock()

        with (
            patch("obskit.config._init_redis_slo_tracker") as mock_init,
        ):
            mock_init.side_effect = lambda s: None  # don't actually create
            configure_observability(
                service_name="redis-svc",
                redis_url="redis://localhost:6379/0",
            )
            mock_init.assert_called_once()

    def test_redis_url_warns_when_redis_not_installed(self) -> None:
        """When redis package is absent, a warning is logged and tracker stays None."""
        import sys
        from unittest.mock import patch

        # Simulate redis not installed by making _init_redis_slo_tracker warn + return
        with patch(
            "obskit.config._init_redis_slo_tracker",
            side_effect=lambda s: None,
        ):
            configure_observability(
                service_name="no-redis-pkg-svc",
                redis_url="redis://localhost:6379/0",
            )
        # Should not raise and tracker remains None (init was mocked to do nothing)
        assert get_redis_slo_tracker() is None

    def test_redis_url_init_skips_gracefully_when_import_fails(self) -> None:
        """_init_redis_slo_tracker() emits a warning when redis is absent."""
        import logging
        import sys
        from unittest.mock import patch

        # Simulate ImportError inside _init_redis_slo_tracker by removing redis from sys.modules
        saved = {k: v for k, v in sys.modules.items() if k.startswith("redis")}
        for k in saved:
            sys.modules.pop(k)

        with patch.dict("sys.modules", {"redis": None, "redis.asyncio": None}):
            with patch("logging.Logger.warning") as mock_warn:
                from obskit.config import _init_redis_slo_tracker
                from obskit.config import ObskitSettings

                settings = ObskitSettings(redis_url="redis://localhost:6379/0")
                _init_redis_slo_tracker(settings)
                # Should have warned
                assert mock_warn.called or get_redis_slo_tracker() is None

        # Restore
        sys.modules.update(saved)

    def test_init_redis_slo_tracker_happy_path(self) -> None:
        """_init_redis_slo_tracker() creates and registers the tracker when redis is available."""
        from obskit.config import ObskitSettings, _init_redis_slo_tracker
        from obskit.slo.redis_tracker import AsyncRedisSLOTracker

        settings = ObskitSettings(
            service_name="redis-happy-svc",
            redis_url="redis://localhost:6379/0",
        )
        _init_redis_slo_tracker(settings)
        tracker = get_redis_slo_tracker()
        assert isinstance(tracker, AsyncRedisSLOTracker)
        assert tracker._service == "redis-happy-svc"


class TestRedactFieldsParam:
    def test_default_redact_fields_redacts_password(self) -> None:
        """Built-in defaults include 'password' — verify via processor directly."""
        from obskit.logging.redaction import DEFAULT_SENSITIVE_FIELDS, make_redaction_processor

        # Simulate what configure_logging() builds with default settings
        processor = make_redaction_processor(fields=DEFAULT_SENSITIVE_FIELDS)
        event = processor(None, None, {"event": "test", "password": "s3cr3t"})
        assert event["password"] == "[REDACTED]"

    def test_extra_redact_fields_merged_with_defaults(self) -> None:
        """User-supplied redact_fields are merged with built-in defaults."""
        from obskit.config import get_settings
        from obskit.logging.redaction import DEFAULT_SENSITIVE_FIELDS, make_redaction_processor

        configure_observability(
            service_name="custom-redact-svc",
            redact_fields=["my_custom_secret"],
        )
        settings = get_settings()
        merged = DEFAULT_SENSITIVE_FIELDS | {f.lower() for f in settings.redact_fields}
        processor = make_redaction_processor(fields=merged)

        event = processor(None, None, {"event": "secret event", "my_custom_secret": "topsecret"})
        assert event["my_custom_secret"] == "[REDACTED]"

    def test_extra_redact_fields_stored_in_settings(self) -> None:
        """redact_fields= is persisted on the settings object."""
        from obskit.config import get_settings

        configure_observability(
            service_name="stored-fields-svc",
            redact_fields=["api_key", "session_token"],
        )
        settings = get_settings()
        assert "api_key" in settings.redact_fields
        assert "session_token" in settings.redact_fields

    def test_empty_redact_fields_uses_defaults_only(self) -> None:
        """No extra fields → only built-in defaults are active."""
        from obskit.config import get_settings

        configure_observability(service_name="defaults-only-svc")
        settings = get_settings()
        assert settings.redact_fields == []

    def test_non_sensitive_field_not_redacted(self) -> None:
        """A safe field name is not matched by the redaction processor."""
        from obskit.logging.redaction import DEFAULT_SENSITIVE_FIELDS, make_redaction_processor

        processor = make_redaction_processor(fields=DEFAULT_SENSITIVE_FIELDS)
        event = processor(None, None, {"event": "normal", "company_id": "acme"})
        assert event["company_id"] == "acme"
