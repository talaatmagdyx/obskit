"""Tests for obskit.tracing.sampling module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import obskit.tracing.sampling as _sampling_module
from obskit.tracing.sampling import (
    ErrorPromotionSpanProcessor,
    _RecordAndSampleErrors,
    build_sampler,
    configure_trace_sampling,
    get_sampling_config,
)


@pytest.fixture(autouse=True)
def reset_sampling_config():
    """Reset module-level _SAMPLING_CONFIG between tests."""
    old = _sampling_module._SAMPLING_CONFIG
    yield
    _sampling_module._SAMPLING_CONFIG = old


class TestConfigureTraceSampling:
    """Tests for configure_trace_sampling function."""

    def test_stores_head_rate(self):
        configure_trace_sampling(0.1)
        assert get_sampling_config()["head_rate"] == 0.1

    def test_stores_always_sample_errors(self):
        configure_trace_sampling(0.1, always_sample_errors=True)
        assert get_sampling_config()["always_sample_errors"] is True

    def test_always_sample_errors_defaults_true(self):
        configure_trace_sampling(0.5)
        assert get_sampling_config()["always_sample_errors"] is True

    def test_always_sample_errors_false(self):
        configure_trace_sampling(0.5, always_sample_errors=False)
        assert get_sampling_config()["always_sample_errors"] is False

    def test_raises_on_head_rate_below_zero(self):
        with pytest.raises(ValueError):
            configure_trace_sampling(-0.1)

    def test_raises_on_head_rate_above_one(self):
        with pytest.raises(ValueError):
            configure_trace_sampling(1.1)

    def test_head_rate_boundaries_valid(self):
        # Both 0.0 and 1.0 should not raise
        configure_trace_sampling(0.0)
        assert get_sampling_config()["head_rate"] == 0.0
        configure_trace_sampling(1.0)
        assert get_sampling_config()["head_rate"] == 1.0


class TestGetSamplingConfig:
    """Tests for get_sampling_config function."""

    def test_returns_none_when_not_configured(self):
        _sampling_module._SAMPLING_CONFIG = None
        assert get_sampling_config() is None

    def test_returns_dict_after_configure(self):
        configure_trace_sampling(0.3)
        config = get_sampling_config()
        assert isinstance(config, dict)
        assert "head_rate" in config
        assert "always_sample_errors" in config

    def test_returns_copy(self):
        configure_trace_sampling(0.3)
        config = get_sampling_config()
        config["head_rate"] = 999.0
        # Original stored config should not be modified
        assert get_sampling_config()["head_rate"] == 0.3


class TestBuildSampler:
    """Tests for build_sampler function."""

    def test_always_on_at_full_rate(self):
        from opentelemetry.sdk.trace.sampling import ALWAYS_ON

        result = build_sampler(1.0)
        assert result is ALWAYS_ON

    def test_ratio_sampler_below_full_rate(self):
        from opentelemetry.sdk.trace.sampling import ParentBased

        result = build_sampler(0.5)
        assert isinstance(result, ParentBased)
        assert not isinstance(result, _RecordAndSampleErrors)

    def test_error_aware_sampler_when_requested(self):
        result = build_sampler(0.5, True)
        assert isinstance(result, _RecordAndSampleErrors)

    def test_always_on_with_error_flag_at_full_rate(self):
        from opentelemetry.sdk.trace.sampling import ALWAYS_ON

        result = build_sampler(1.0, True)
        assert result is ALWAYS_ON


class TestRecordAndSampleErrors:
    """Tests for _RecordAndSampleErrors sampler wrapper."""

    def test_drop_becomes_record_only(self):
        from opentelemetry.sdk.trace.sampling import Decision, SamplingResult

        inner = MagicMock()
        inner.should_sample.return_value = SamplingResult(
            decision=Decision.DROP, attributes={}, trace_state=None
        )
        inner.get_description.return_value = "MockSampler"

        sampler = _RecordAndSampleErrors(inner)
        result = sampler.should_sample(None, 12345, "test_span")
        assert result.decision == Decision.RECORD_ONLY

    def test_record_and_sample_passes_through(self):
        from opentelemetry.sdk.trace.sampling import Decision, SamplingResult

        inner = MagicMock()
        original_result = SamplingResult(
            decision=Decision.RECORD_AND_SAMPLE, attributes={}, trace_state=None
        )
        inner.should_sample.return_value = original_result
        inner.get_description.return_value = "MockSampler"

        sampler = _RecordAndSampleErrors(inner)
        result = sampler.should_sample(None, 12345, "test_span")
        assert result is original_result
        assert result.decision == Decision.RECORD_AND_SAMPLE

    def test_record_only_passes_through(self):
        from opentelemetry.sdk.trace.sampling import Decision, SamplingResult

        inner = MagicMock()
        original_result = SamplingResult(
            decision=Decision.RECORD_ONLY, attributes={}, trace_state=None
        )
        inner.should_sample.return_value = original_result
        inner.get_description.return_value = "MockSampler"

        sampler = _RecordAndSampleErrors(inner)
        result = sampler.should_sample(None, 12345, "test_span")
        assert result is original_result
        assert result.decision == Decision.RECORD_ONLY

    def test_get_description_includes_inner(self):
        inner = MagicMock()
        inner.get_description.return_value = "InnerSampler"

        sampler = _RecordAndSampleErrors(inner)
        description = sampler.get_description()
        assert "InnerSampler" in description


class TestErrorPromotionSpanProcessor:
    """Tests for ErrorPromotionSpanProcessor."""

    def test_on_start_is_noop(self):
        exporter = MagicMock()
        processor = ErrorPromotionSpanProcessor(exporter)
        span = MagicMock()
        # Should not raise
        processor.on_start(span)

    def test_shutdown_is_noop(self):
        exporter = MagicMock()
        processor = ErrorPromotionSpanProcessor(exporter)
        # Should not raise
        processor.shutdown()

    def test_force_flush_returns_true(self):
        exporter = MagicMock()
        processor = ErrorPromotionSpanProcessor(exporter)
        assert processor.force_flush() is True

    def test_exports_error_unsampled_span(self):
        from opentelemetry.trace import StatusCode, TraceFlags

        exporter = MagicMock()
        processor = ErrorPromotionSpanProcessor(exporter)

        span = MagicMock()
        span.status.status_code = StatusCode.ERROR
        span.context.trace_flags = TraceFlags(0)  # NOT sampled

        processor.on_end(span)
        exporter.export.assert_called_once_with([span])

    def test_does_not_export_success_unsampled_span(self):
        from opentelemetry.trace import StatusCode, TraceFlags

        exporter = MagicMock()
        processor = ErrorPromotionSpanProcessor(exporter)

        span = MagicMock()
        span.status.status_code = StatusCode.OK
        span.context.trace_flags = TraceFlags(0)  # NOT sampled

        processor.on_end(span)
        exporter.export.assert_not_called()

    def test_does_not_export_error_sampled_span(self):
        from opentelemetry.trace import StatusCode, TraceFlags

        exporter = MagicMock()
        processor = ErrorPromotionSpanProcessor(exporter)

        span = MagicMock()
        span.status.status_code = StatusCode.ERROR
        span.context.trace_flags = TraceFlags(TraceFlags.SAMPLED)  # sampled

        processor.on_end(span)
        exporter.export.assert_not_called()


class TestApplySamplingToProvider:
    """Tests for _apply_sampling_to_provider."""

    def test_returns_early_when_no_sdk_provider(self):
        """If no SDK TracerProvider is active, the function returns early."""
        from opentelemetry.trace import ProxyTracerProvider

        with patch("opentelemetry.trace.get_tracer_provider") as mock_get:
            mock_get.return_value = ProxyTracerProvider()
            # Should not raise and just return early
            _sampling_module._apply_sampling_to_provider(0.5, False)

    def test_patches_provider_sampler(self):
        """If a real TracerProvider is active, _sampler is patched."""
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        with patch("opentelemetry.trace.get_tracer_provider", return_value=provider):
            _sampling_module._apply_sampling_to_provider(0.5, False)
            # The sampler should have been replaced
            from opentelemetry.sdk.trace.sampling import ParentBased

            assert isinstance(provider._sampler, ParentBased)

    def test_patches_provider_and_attaches_error_processor(self):
        """With always_sample_errors=True, also attaches error processor."""
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        with patch("opentelemetry.trace.get_tracer_provider", return_value=provider):
            with patch.object(
                _sampling_module, "_attach_error_promotion_processor"
            ) as mock_attach:
                _sampling_module._apply_sampling_to_provider(0.5, True)
                mock_attach.assert_called_once_with(provider)


class TestAttachErrorPromotionProcessor:
    """Direct tests for _attach_error_promotion_processor."""

    def test_returns_early_when_batch_processor_is_none(self):
        """If _batch_span_processor is None, function exits without error."""
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        with patch("obskit.tracing.tracer._batch_span_processor", None):
            # Should not raise
            _sampling_module._attach_error_promotion_processor(provider)

    def test_attaches_processor_when_exporter_available(self):
        """When BSP has span_exporter, adds ErrorPromotionSpanProcessor to provider."""
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        mock_bsp = MagicMock()
        mock_exporter = MagicMock()
        mock_bsp.span_exporter = mock_exporter

        with patch("obskit.tracing.tracer._batch_span_processor", mock_bsp):
            with patch.object(provider, "add_span_processor") as mock_add:
                _sampling_module._attach_error_promotion_processor(provider)
                mock_add.assert_called_once()
                processor = mock_add.call_args[0][0]
                assert isinstance(processor, ErrorPromotionSpanProcessor)
