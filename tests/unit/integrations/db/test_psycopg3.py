"""Tests for obskit.integrations.db.psycopg3 module.

Tests verify that ImportError is raised with the correct message when
opentelemetry-instrumentation-psycopg is not installed.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestPsycopg3ImportError:
    """Test that ImportError is raised with correct message when dependency missing."""

    def test_import_error_raised_with_correct_message(self):
        """Test ImportError raised when opentelemetry-instrumentation-psycopg not installed."""
        mod_name = "obskit.integrations.db.psycopg3"
        otel_mod = "opentelemetry.instrumentation.psycopg"

        saved_mod = sys.modules.pop(mod_name, None)
        saved_otel = sys.modules.pop(otel_mod, None)

        try:
            with patch.dict(sys.modules, {otel_mod: None}):
                with pytest.raises(ImportError) as exc_info:
                    import obskit.integrations.db.psycopg3  # noqa: F401

                assert "psycopg3 instrumentation requires" in str(exc_info.value)
                assert "opentelemetry-instrumentation-psycopg" in str(exc_info.value)
                assert "obskit[psycopg3]" in str(exc_info.value)
        finally:
            # Restore
            if saved_mod is not None:
                sys.modules[mod_name] = saved_mod
            elif mod_name in sys.modules:
                del sys.modules[mod_name]
            if saved_otel is not None:
                sys.modules[otel_mod] = saved_otel
            elif otel_mod in sys.modules:
                del sys.modules[otel_mod]


class TestPsycopg3WithMockedDependency:
    """Tests for psycopg3 instrumentation functions with mocked OTel dependency."""

    def test_instrument_psycopg3_calls_instrument(self):
        """Test instrument_psycopg3 calls PsycopgInstrumentor().instrument()."""
        mod_name = "obskit.integrations.db.psycopg3"
        otel_mod = "opentelemetry.instrumentation.psycopg"

        sys.modules.pop(mod_name, None)

        mock_instrumentor_instance = MagicMock()
        mock_instrumentor_class = MagicMock(return_value=mock_instrumentor_instance)
        mock_otel_module = MagicMock()
        mock_otel_module.PsycopgInstrumentor = mock_instrumentor_class

        with patch.dict(sys.modules, {otel_mod: mock_otel_module}):
            mod = importlib.import_module(mod_name)
            mod.instrument_psycopg3()

        mock_instrumentor_instance.instrument.assert_called_once_with(
            tracer_provider=None,
            capture_parameters=False,
            enable_commenter=False,
        )

    def test_instrument_psycopg3_with_options(self):
        """Test instrument_psycopg3 passes options correctly."""
        mod_name = "obskit.integrations.db.psycopg3"
        otel_mod = "opentelemetry.instrumentation.psycopg"

        sys.modules.pop(mod_name, None)

        mock_instrumentor_instance = MagicMock()
        mock_instrumentor_class = MagicMock(return_value=mock_instrumentor_instance)
        mock_otel_module = MagicMock()
        mock_otel_module.PsycopgInstrumentor = mock_instrumentor_class

        mock_provider = MagicMock()

        with patch.dict(sys.modules, {otel_mod: mock_otel_module}):
            mod = importlib.import_module(mod_name)
            mod.instrument_psycopg3(
                tracer_provider=mock_provider,
                capture_parameters=True,
                enable_commenter=True,
            )

        mock_instrumentor_instance.instrument.assert_called_once_with(
            tracer_provider=mock_provider,
            capture_parameters=True,
            enable_commenter=True,
        )

    def test_instrument_psycopg3_connection(self):
        """Test instrument_psycopg3_connection calls instrument_connection."""
        mod_name = "obskit.integrations.db.psycopg3"
        otel_mod = "opentelemetry.instrumentation.psycopg"

        sys.modules.pop(mod_name, None)

        mock_instrumented_conn = MagicMock()
        mock_instrumentor_instance = MagicMock()
        mock_instrumentor_instance.instrument_connection.return_value = mock_instrumented_conn
        mock_instrumentor_class = MagicMock(return_value=mock_instrumentor_instance)
        mock_otel_module = MagicMock()
        mock_otel_module.PsycopgInstrumentor = mock_instrumentor_class

        mock_conn = MagicMock()

        with patch.dict(sys.modules, {otel_mod: mock_otel_module}):
            mod = importlib.import_module(mod_name)
            result = mod.instrument_psycopg3_connection(mock_conn)

        assert result is mock_instrumented_conn
        mock_instrumentor_instance.instrument_connection.assert_called_once_with(
            mock_conn,
            tracer_provider=None,
        )

    def test_instrument_psycopg3_connection_with_provider(self):
        """Test instrument_psycopg3_connection passes tracer_provider."""
        mod_name = "obskit.integrations.db.psycopg3"
        otel_mod = "opentelemetry.instrumentation.psycopg"

        sys.modules.pop(mod_name, None)

        mock_instrumentor_instance = MagicMock()
        mock_instrumentor_class = MagicMock(return_value=mock_instrumentor_instance)
        mock_otel_module = MagicMock()
        mock_otel_module.PsycopgInstrumentor = mock_instrumentor_class

        mock_conn = MagicMock()
        mock_provider = MagicMock()

        with patch.dict(sys.modules, {otel_mod: mock_otel_module}):
            mod = importlib.import_module(mod_name)
            mod.instrument_psycopg3_connection(mock_conn, tracer_provider=mock_provider)

        mock_instrumentor_instance.instrument_connection.assert_called_once_with(
            mock_conn,
            tracer_provider=mock_provider,
        )

    def test_module_all_exports(self):
        """Test __all__ contains the expected exports."""
        mod_name = "obskit.integrations.db.psycopg3"
        otel_mod = "opentelemetry.instrumentation.psycopg"

        sys.modules.pop(mod_name, None)

        mock_otel_module = MagicMock()
        mock_otel_module.PsycopgInstrumentor = MagicMock(return_value=MagicMock())

        with patch.dict(sys.modules, {otel_mod: mock_otel_module}):
            mod = importlib.import_module(mod_name)

        assert "instrument_psycopg3" in mod.__all__
        assert "instrument_psycopg3_connection" in mod.__all__
