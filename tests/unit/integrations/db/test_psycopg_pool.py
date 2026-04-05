"""Unit tests for obskit.integrations.db.psycopg_pool."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestInstrumentPsycopgPool:
    def test_returns_instrumentor(self):
        from obskit.integrations.db.psycopg_pool import (
            PsycopgPoolInstrumentor,
            instrument_psycopg_pool,
        )

        mock_pool = MagicMock()
        instr = instrument_psycopg_pool(mock_pool, name="test")
        assert isinstance(instr, PsycopgPoolInstrumentor)

    def test_default_name(self):
        from obskit.integrations.db.psycopg_pool import instrument_psycopg_pool

        mock_pool = MagicMock()
        instr = instrument_psycopg_pool(mock_pool)
        assert instr._name == "default"

    def test_stores_name(self):
        from obskit.integrations.db.psycopg_pool import instrument_psycopg_pool

        mock_pool = MagicMock()
        instr = instrument_psycopg_pool(mock_pool, name="main")
        assert instr._name == "main"

    def test_stores_pool_reference(self):
        from obskit.integrations.db.psycopg_pool import instrument_psycopg_pool

        mock_pool = MagicMock()
        instr = instrument_psycopg_pool(mock_pool, name="p0")
        assert instr._pool is mock_pool


class TestPsycopgPoolInstrumentorGetconn:
    def test_getconn_is_patched(self):
        from obskit.integrations.db.psycopg_pool import instrument_psycopg_pool

        mock_pool = MagicMock()
        original_getconn = mock_pool.getconn
        instrument_psycopg_pool(mock_pool, name="p1")
        assert mock_pool.getconn is not original_getconn

    def test_getconn_records_acquisition_time(self):
        from obskit.integrations.db.psycopg_pool import (
            DB_POOL_ACQUISITION_SECONDS,
            instrument_psycopg_pool,
        )

        mock_pool = MagicMock()
        mock_pool.getconn.return_value = MagicMock()
        before_sum = DB_POOL_ACQUISITION_SECONDS.labels(pool_name="p2")._sum.get()
        instrument_psycopg_pool(mock_pool, name="p2")
        mock_pool.getconn()
        after_sum = DB_POOL_ACQUISITION_SECONDS.labels(pool_name="p2")._sum.get()
        assert after_sum >= before_sum

    def test_getconn_returns_connection(self):
        from obskit.integrations.db.psycopg_pool import instrument_psycopg_pool

        mock_pool = MagicMock()
        fake_conn = MagicMock()
        mock_pool.getconn.return_value = fake_conn
        instrument_psycopg_pool(mock_pool, name="p3")
        result = mock_pool.getconn()
        assert result is fake_conn

    def test_getconn_exception_still_records_time(self):
        """Even on exception, acquisition time is recorded (finally block)."""
        from obskit.integrations.db.psycopg_pool import (
            DB_POOL_ACQUISITION_SECONDS,
            instrument_psycopg_pool,
        )

        mock_pool = MagicMock()
        mock_pool.getconn.side_effect = RuntimeError("pool timeout")
        before_sum = DB_POOL_ACQUISITION_SECONDS.labels(pool_name="p4")._sum.get()
        instrument_psycopg_pool(mock_pool, name="p4")
        with pytest.raises(RuntimeError, match="pool timeout"):
            mock_pool.getconn()
        after_sum = DB_POOL_ACQUISITION_SECONDS.labels(pool_name="p4")._sum.get()
        assert after_sum >= before_sum

    def test_getconn_passes_args_and_kwargs(self):
        """Arguments are forwarded to the original getconn."""
        from obskit.integrations.db.psycopg_pool import instrument_psycopg_pool

        mock_pool = MagicMock()
        original_getconn = mock_pool.getconn  # save before patching
        instrument_psycopg_pool(mock_pool, name="p5")
        mock_pool.getconn("arg1", key="val")
        original_getconn.assert_called_once_with("arg1", key="val")


class TestPsycopgPoolInstrumentorCollectStats:
    def test_collect_stats_sets_gauges(self):
        from obskit.integrations.db.psycopg_pool import (
            DB_POOL_AVAILABLE,
            DB_POOL_SIZE,
            DB_POOL_WAITING,
            instrument_psycopg_pool,
        )

        mock_pool = MagicMock()
        mock_pool.get_stats.return_value = {
            "pool_size": 10,
            "pool_available": 7,
            "requests_waiting": 2,
        }
        instr = instrument_psycopg_pool(mock_pool, name="s1")
        instr.collect_stats()
        assert DB_POOL_SIZE.labels(pool_name="s1")._value.get() == 10.0
        assert DB_POOL_AVAILABLE.labels(pool_name="s1")._value.get() == 7.0
        assert DB_POOL_WAITING.labels(pool_name="s1")._value.get() == 2.0

    def test_collect_stats_missing_keys_default_to_zero(self):
        from obskit.integrations.db.psycopg_pool import (
            DB_POOL_AVAILABLE,
            DB_POOL_SIZE,
            DB_POOL_WAITING,
            instrument_psycopg_pool,
        )

        mock_pool = MagicMock()
        mock_pool.get_stats.return_value = {}
        instr = instrument_psycopg_pool(mock_pool, name="s2")
        instr.collect_stats()
        assert DB_POOL_SIZE.labels(pool_name="s2")._value.get() == 0.0
        assert DB_POOL_AVAILABLE.labels(pool_name="s2")._value.get() == 0.0
        assert DB_POOL_WAITING.labels(pool_name="s2")._value.get() == 0.0

    def test_collect_stats_updates_on_each_call(self):
        from obskit.integrations.db.psycopg_pool import (
            DB_POOL_SIZE,
            instrument_psycopg_pool,
        )

        mock_pool = MagicMock()
        mock_pool.get_stats.side_effect = [
            {"pool_size": 5, "pool_available": 3, "requests_waiting": 0},
            {"pool_size": 8, "pool_available": 1, "requests_waiting": 3},
        ]
        instr = instrument_psycopg_pool(mock_pool, name="s3")
        instr.collect_stats()
        assert DB_POOL_SIZE.labels(pool_name="s3")._value.get() == 5.0
        instr.collect_stats()
        assert DB_POOL_SIZE.labels(pool_name="s3")._value.get() == 8.0


class TestPsycopgPoolPublicAPI:
    def test_all_exports_present(self):
        import obskit.integrations.db.psycopg_pool as m

        for name in (
            "PsycopgPoolInstrumentor",
            "instrument_psycopg_pool",
            "DB_POOL_SIZE",
            "DB_POOL_AVAILABLE",
            "DB_POOL_WAITING",
            "DB_POOL_ACQUISITION_SECONDS",
        ):
            assert hasattr(m, name), f"missing export: {name}"
