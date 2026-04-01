"""Tests for obskit.integrations.db.sqlalchemy module."""

import sys
from unittest.mock import MagicMock, patch


class TestInstrumentSqlalchemy:
    """Tests for instrument_sqlalchemy function."""

    def test_instruments_valid_engine(self):
        """Test instrumenting a valid SQLAlchemy engine."""
        # Create mock sqlalchemy modules
        mock_event = MagicMock()
        mock_engine_class = MagicMock()

        mock_sqlalchemy = MagicMock()
        mock_sqlalchemy.event = mock_event
        mock_sqlalchemy.engine.Engine = mock_engine_class

        # Create mock engine instance
        mock_engine = MagicMock()
        mock_engine.url = "postgresql://localhost/testdb"
        mock_engine.pool.checkedout.return_value = 5
        mock_engine.pool.size.return_value = 10

        with patch.dict(
            sys.modules,
            {
                "sqlalchemy": mock_sqlalchemy,
                "sqlalchemy.event": mock_event,
                "sqlalchemy.engine": mock_sqlalchemy.engine,
            },
        ):
            from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

            # Make isinstance return True for Engine check
            with patch("obskit.integrations.db.sqlalchemy.isinstance", return_value=True):
                instrument_sqlalchemy(mock_engine, database_name="postgres")

            # Verify event.listens_for was called
            assert mock_event.listens_for.called

    @patch("obskit.integrations.db.sqlalchemy.logger")
    def test_invalid_engine_type_logs_warning(self, mock_logger):
        """Test warning logged for invalid engine type."""
        mock_event = MagicMock()
        mock_engine_class = MagicMock()

        mock_sqlalchemy = MagicMock()
        mock_sqlalchemy.event = mock_event
        mock_sqlalchemy.engine.Engine = mock_engine_class

        mock_engine = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "sqlalchemy": mock_sqlalchemy,
                "sqlalchemy.event": mock_event,
                "sqlalchemy.engine": mock_sqlalchemy.engine,
            },
        ):
            from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

            # Make isinstance return False
            with patch("obskit.integrations.db.sqlalchemy.isinstance", return_value=False):
                instrument_sqlalchemy(mock_engine, database_name="test")

            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "invalid_sqlalchemy_engine"

    @patch("obskit.integrations.db.sqlalchemy.logger")
    def test_logs_instrumentation_success(self, mock_logger):
        """Test that successful instrumentation is logged."""
        mock_event = MagicMock()
        mock_engine_class = MagicMock()

        mock_sqlalchemy = MagicMock()
        mock_sqlalchemy.event = mock_event
        mock_sqlalchemy.engine.Engine = mock_engine_class

        mock_engine = MagicMock()
        mock_engine.url = "postgresql://localhost/db"
        mock_engine.pool.checkedout.return_value = 5
        mock_engine.pool.size.return_value = 10

        with patch.dict(
            sys.modules,
            {
                "sqlalchemy": mock_sqlalchemy,
                "sqlalchemy.event": mock_event,
                "sqlalchemy.engine": mock_sqlalchemy.engine,
            },
        ):
            from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

            with patch("obskit.integrations.db.sqlalchemy.isinstance", return_value=True):
                instrument_sqlalchemy(mock_engine, database_name="mydb")

            # Should have info log for successful instrumentation
            mock_logger.info.assert_called()

    @patch("obskit.integrations.db.sqlalchemy.logger")
    def test_handles_import_error(self, mock_logger):
        """Test handling when SQLAlchemy is not installed."""
        # Temporarily remove sqlalchemy from modules
        original_modules = {}
        for mod in list(sys.modules.keys()):
            if mod.startswith("sqlalchemy"):
                original_modules[mod] = sys.modules.pop(mod)

        try:
            # Force re-import without sqlalchemy
            with patch.dict(sys.modules, {"sqlalchemy": None}):
                # Import fresh
                if "obskit.integrations.db.sqlalchemy" in sys.modules:
                    del sys.modules["obskit.integrations.db.sqlalchemy"]

                # This test verifies the module structure
                mock_engine = MagicMock()

                from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

                # Run instrumentation - should handle ImportError gracefully
                try:
                    instrument_sqlalchemy(mock_engine, database_name="test")
                except ImportError:
                    # This is expected if sqlalchemy is not available
                    pass  # NOSONAR
        finally:
            # Restore original modules
            sys.modules.update(original_modules)


class TestEventListenerFunctions:
    """Tests for the event listener callback functions."""

    def test_event_listeners_registered(self):
        """Test that all event listeners are registered."""
        mock_event = MagicMock()
        mock_engine_class = MagicMock()

        mock_sqlalchemy = MagicMock()
        mock_sqlalchemy.event = mock_event
        mock_sqlalchemy.engine.Engine = mock_engine_class

        mock_engine = MagicMock()
        mock_engine.url = "postgresql://localhost/db"
        mock_engine.pool.checkedout.return_value = 5
        mock_engine.pool.size.return_value = 10

        listeners = {}

        def capture_listens_for(target, identifier):
            def decorator(func):
                listeners[identifier] = func
                return func

            return decorator

        mock_event.listens_for.side_effect = capture_listens_for

        with patch.dict(
            sys.modules,
            {
                "sqlalchemy": mock_sqlalchemy,
                "sqlalchemy.event": mock_event,
                "sqlalchemy.engine": mock_sqlalchemy.engine,
            },
        ):
            from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

            with patch("obskit.integrations.db.sqlalchemy.isinstance", return_value=True):
                instrument_sqlalchemy(mock_engine, database_name="test")

        # Verify all listeners were registered
        assert "before_cursor_execute" in listeners
        assert "after_cursor_execute" in listeners
        assert "handle_error" in listeners
        assert "connect" in listeners

    def test_before_cursor_execute_sets_start_time(self):
        """Test before_cursor_execute stores query start time."""
        mock_event = MagicMock()
        mock_engine_class = MagicMock()

        mock_sqlalchemy = MagicMock()
        mock_sqlalchemy.event = mock_event
        mock_sqlalchemy.engine.Engine = mock_engine_class

        mock_engine = MagicMock()
        mock_engine.url = "postgresql://localhost/db"
        mock_engine.pool.checkedout.return_value = 5
        mock_engine.pool.size.return_value = 10

        listeners = {}

        def capture_listens_for(target, identifier):
            def decorator(func):
                listeners[identifier] = func
                return func

            return decorator

        mock_event.listens_for.side_effect = capture_listens_for

        with patch.dict(
            sys.modules,
            {
                "sqlalchemy": mock_sqlalchemy,
                "sqlalchemy.event": mock_event,
                "sqlalchemy.engine": mock_sqlalchemy.engine,
            },
        ):
            from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

            with patch("obskit.integrations.db.sqlalchemy.isinstance", return_value=True):
                instrument_sqlalchemy(mock_engine, database_name="test")

        # Test before_cursor_execute
        mock_context = MagicMock(spec=[])

        listeners["before_cursor_execute"](
            conn=MagicMock(),
            cursor=MagicMock(),
            statement="SELECT 1",
            parameters=None,
            context=mock_context,
            executemany=False,
        )

        assert hasattr(mock_context, "_query_start_time")
        assert hasattr(mock_context, "_query_statement")

    def test_after_cursor_execute_tracks_duration(self):
        """Test after_cursor_execute records query duration."""
        mock_event = MagicMock()
        mock_engine_class = MagicMock()

        mock_sqlalchemy = MagicMock()
        mock_sqlalchemy.event = mock_event
        mock_sqlalchemy.engine.Engine = mock_engine_class

        mock_engine = MagicMock()
        mock_engine.url = "postgresql://localhost/db"
        mock_engine.pool.checkedout.return_value = 5
        mock_engine.pool.size.return_value = 10

        listeners = {}

        def capture_listens_for(target, identifier):
            def decorator(func):
                listeners[identifier] = func
                return func

            return decorator

        mock_event.listens_for.side_effect = capture_listens_for

        with (
            patch.dict(
                sys.modules,
                {
                    "sqlalchemy": mock_sqlalchemy,
                    "sqlalchemy.event": mock_event,
                    "sqlalchemy.engine": mock_sqlalchemy.engine,
                },
            ),
            patch("obskit.integrations.db.sqlalchemy.get_red_metrics") as mock_red,
        ):
            mock_metrics = MagicMock()
            mock_red.return_value = mock_metrics

            from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

            with patch("obskit.integrations.db.sqlalchemy.isinstance", return_value=True):
                instrument_sqlalchemy(mock_engine, database_name="testdb")

            # Test after_cursor_execute
            mock_context = MagicMock()
            mock_context._query_start_time = 0.0  # Set start time

            listeners["after_cursor_execute"](
                conn=MagicMock(),
                cursor=MagicMock(),
                statement="SELECT 1",
                parameters=None,
                context=mock_context,
                executemany=False,
            )

            mock_metrics.observe_request.assert_called()

    @patch("obskit.integrations.db.sqlalchemy.logger")
    def test_handle_error_logs_exception(self, mock_logger):
        """Test handle_error logs query errors."""
        mock_event = MagicMock()
        mock_engine_class = MagicMock()

        mock_sqlalchemy = MagicMock()
        mock_sqlalchemy.event = mock_event
        mock_sqlalchemy.engine.Engine = mock_engine_class

        mock_engine = MagicMock()
        mock_engine.url = "postgresql://localhost/db"
        mock_engine.pool.checkedout.return_value = 5
        mock_engine.pool.size.return_value = 10

        listeners = {}

        def capture_listens_for(target, identifier):
            def decorator(func):
                listeners[identifier] = func
                return func

            return decorator

        mock_event.listens_for.side_effect = capture_listens_for

        with patch.dict(
            sys.modules,
            {
                "sqlalchemy": mock_sqlalchemy,
                "sqlalchemy.event": mock_event,
                "sqlalchemy.engine": mock_sqlalchemy.engine,
            },
        ):
            from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

            with patch("obskit.integrations.db.sqlalchemy.isinstance", return_value=True):
                instrument_sqlalchemy(mock_engine, database_name="test")

        # Test handle_error
        mock_exception_context = MagicMock()
        mock_exception_context.original_exception = ValueError("DB connection failed")

        listeners["handle_error"](mock_exception_context)

        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "sql_query_error"

    @patch("obskit.integrations.db.sqlalchemy.logger")
    def test_on_connect_logs_debug(self, mock_logger):
        """Test on_connect logs a debug message."""
        mock_event = MagicMock()
        mock_engine_class = MagicMock()

        mock_sqlalchemy = MagicMock()
        mock_sqlalchemy.event = mock_event
        mock_sqlalchemy.engine.Engine = mock_engine_class

        mock_engine = MagicMock()
        mock_engine.url = "postgresql://localhost/db"
        mock_engine.pool.checkedout.return_value = 3
        mock_engine.pool.size.return_value = 10

        listeners = {}

        def capture_listens_for(target, identifier):
            def decorator(func):
                listeners[identifier] = func
                return func

            return decorator

        mock_event.listens_for.side_effect = capture_listens_for

        with patch.dict(
            sys.modules,
            {
                "sqlalchemy": mock_sqlalchemy,
                "sqlalchemy.event": mock_event,
                "sqlalchemy.engine": mock_sqlalchemy.engine,
            },
        ):
            from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

            with patch("obskit.integrations.db.sqlalchemy.isinstance", return_value=True):
                instrument_sqlalchemy(mock_engine, database_name="testdb")

        # Test on_connect
        mock_logger.reset_mock()
        listeners["connect"](
            dbapi_conn=MagicMock(),
            connection_record=MagicMock(),
        )

        mock_logger.debug.assert_called()

    def test_after_cursor_execute_without_start_time(self):
        """Test after_cursor_execute handles missing start time (line 84->exit)."""
        mock_event = MagicMock()
        mock_engine_class = MagicMock()

        mock_sqlalchemy = MagicMock()
        mock_sqlalchemy.event = mock_event
        mock_sqlalchemy.engine.Engine = mock_engine_class

        mock_engine = MagicMock()
        mock_engine.url = "postgresql://localhost/db"
        mock_engine.pool.checkedout.return_value = 5
        mock_engine.pool.size.return_value = 10

        listeners = {}

        def capture_listens_for(target, identifier):
            def decorator(func):
                listeners[identifier] = func
                return func

            return decorator

        mock_event.listens_for.side_effect = capture_listens_for

        with (
            patch.dict(
                sys.modules,
                {
                    "sqlalchemy": mock_sqlalchemy,
                    "sqlalchemy.event": mock_event,
                    "sqlalchemy.engine": mock_sqlalchemy.engine,
                },
            ),
            patch("obskit.integrations.db.sqlalchemy.get_red_metrics") as mock_red,
        ):
            mock_metrics = MagicMock()
            mock_red.return_value = mock_metrics

            from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

            with patch("obskit.integrations.db.sqlalchemy.isinstance", return_value=True):
                instrument_sqlalchemy(mock_engine, database_name="testdb")

            # Test after_cursor_execute WITHOUT _query_start_time
            mock_context = MagicMock(spec=[])  # No _query_start_time attribute

            # Should not raise error
            listeners["after_cursor_execute"](
                conn=MagicMock(),
                cursor=MagicMock(),
                statement="SELECT 1",
                parameters=None,
                context=mock_context,
                executemany=False,
            )

            # observe_request should NOT be called since no start time
            mock_metrics.observe_request.assert_not_called()

    @patch("obskit.integrations.db.sqlalchemy.logger")
    def test_after_cursor_execute_slow_query(self, mock_logger):
        """Test after_cursor_execute logs slow queries (line 95->taken)."""
        import time

        mock_event = MagicMock()
        mock_engine_class = MagicMock()

        mock_sqlalchemy = MagicMock()
        mock_sqlalchemy.event = mock_event
        mock_sqlalchemy.engine.Engine = mock_engine_class

        mock_engine = MagicMock()
        mock_engine.url = "postgresql://localhost/db"
        mock_engine.pool.checkedout.return_value = 5
        mock_engine.pool.size.return_value = 10

        listeners = {}

        def capture_listens_for(target, identifier):
            def decorator(func):
                listeners[identifier] = func
                return func

            return decorator

        mock_event.listens_for.side_effect = capture_listens_for

        with (
            patch.dict(
                sys.modules,
                {
                    "sqlalchemy": mock_sqlalchemy,
                    "sqlalchemy.event": mock_event,
                    "sqlalchemy.engine": mock_sqlalchemy.engine,
                },
            ),
            patch("obskit.integrations.db.sqlalchemy.get_red_metrics") as mock_red,
        ):
            mock_metrics = MagicMock()
            mock_red.return_value = mock_metrics

            from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

            with patch("obskit.integrations.db.sqlalchemy.isinstance", return_value=True):
                instrument_sqlalchemy(mock_engine, database_name="testdb")

            # Test after_cursor_execute with slow query (>1 second)
            mock_context = MagicMock()
            # Set start time to be more than 1 second ago
            mock_context._query_start_time = time.perf_counter() - 2.0  # 2 seconds ago

            listeners["after_cursor_execute"](
                conn=MagicMock(),
                cursor=MagicMock(),
                statement="SELECT * FROM very_large_table WHERE complex_condition",
                parameters=None,
                context=mock_context,
                executemany=False,
            )

            # Should log slow query warning
            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "slow_sql_query"

    @patch("obskit.integrations.db.sqlalchemy.logger")
    def test_after_cursor_execute_fast_query_no_warning(self, mock_logger):
        """Test after_cursor_execute does not log warning for fast queries (line 95->exit)."""
        import time

        mock_event = MagicMock()
        mock_engine_class = MagicMock()

        mock_sqlalchemy = MagicMock()
        mock_sqlalchemy.event = mock_event
        mock_sqlalchemy.engine.Engine = mock_engine_class

        mock_engine = MagicMock()
        mock_engine.url = "postgresql://localhost/db"
        mock_engine.pool.checkedout.return_value = 5
        mock_engine.pool.size.return_value = 10

        listeners = {}

        def capture_listens_for(target, identifier):
            def decorator(func):
                listeners[identifier] = func
                return func

            return decorator

        mock_event.listens_for.side_effect = capture_listens_for

        with (
            patch.dict(
                sys.modules,
                {
                    "sqlalchemy": mock_sqlalchemy,
                    "sqlalchemy.event": mock_event,
                    "sqlalchemy.engine": mock_sqlalchemy.engine,
                },
            ),
            patch("obskit.integrations.db.sqlalchemy.get_red_metrics") as mock_red,
        ):
            mock_metrics = MagicMock()
            mock_red.return_value = mock_metrics

            from obskit.integrations.db.sqlalchemy import instrument_sqlalchemy

            with patch("obskit.integrations.db.sqlalchemy.isinstance", return_value=True):
                instrument_sqlalchemy(mock_engine, database_name="testdb")

            # Reset mock_logger to clear any previous calls
            mock_logger.reset_mock()

            # Test after_cursor_execute with fast query (<1 second)
            mock_context = MagicMock()
            # Set start time to just now (fast query)
            mock_context._query_start_time = time.perf_counter()

            listeners["after_cursor_execute"](
                conn=MagicMock(),
                cursor=MagicMock(),
                statement="SELECT 1",
                parameters=None,
                context=mock_context,
                executemany=False,
            )

            # observe_request should be called (metrics tracked)
            mock_metrics.observe_request.assert_called()

            # warning should NOT be called for fast query
            # (only info for instrumentation success may have been called before)
            warning_calls = [
                c for c in mock_logger.warning.call_args_list if c[0][0] == "slow_sql_query"
            ]
            assert len(warning_calls) == 0
