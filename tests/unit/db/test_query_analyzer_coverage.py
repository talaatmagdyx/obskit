"""Additional tests for obskit.query_analyzer module to achieve 100% coverage."""

import threading
from unittest.mock import patch

import pytest

import obskit.query_analyzer as qa_module
from obskit.query_analyzer import (
    QueryAnalyzer,
    QueryPlanNode,
    QueryType,
    ScanType,
    get_query_analyzer,
)


class TestQueryPlanNode:
    """Tests for QueryPlanNode.to_dict() (line 101)."""

    def test_to_dict_with_children(self):
        """Test QueryPlanNode.to_dict() including children (line 109)."""
        child_node = QueryPlanNode(
            node_type="Index Scan",
            table="users",
            index="idx_users_email",
            scan_type=ScanType.INDEX_SCAN,
            rows_estimate=10,
            cost=5.0,
            actual_time_ms=1.5,
        )
        parent_node = QueryPlanNode(
            node_type="Nested Loop",
            scan_type=ScanType.OTHER,
            rows_estimate=100,
            cost=50.0,
            children=[child_node],
        )
        result = parent_node.to_dict()
        assert result["node_type"] == "Nested Loop"
        assert len(result["children"]) == 1
        assert result["children"][0]["node_type"] == "Index Scan"
        assert result["children"][0]["table"] == "users"

    def test_to_dict_no_children(self):
        """Test QueryPlanNode.to_dict() with no children."""
        node = QueryPlanNode(
            node_type="Seq Scan",
            table="orders",
            scan_type=ScanType.SEQ_SCAN,
            rows_estimate=1000,
            cost=100.0,
        )
        result = node.to_dict()
        assert result["node_type"] == "Seq Scan"
        assert result["children"] == []


class TestQueryAnalyzerOtherType:
    """Tests for OTHER query type detection (line 206)."""

    def test_detect_query_type_other(self):
        """Test OTHER query type for unrecognized SQL (line 206)."""
        analyzer = QueryAnalyzer("test_db")
        analysis = analyzer.analyze("CREATE TABLE users (id INT)")
        assert analysis.query_type == QueryType.OTHER

    def test_detect_query_type_alter(self):
        """Test ALTER TABLE returns OTHER query type."""
        analyzer = QueryAnalyzer("test_db")
        analysis = analyzer.analyze("ALTER TABLE users ADD COLUMN age INT")
        assert analysis.query_type == QueryType.OTHER


class TestQueryAnalyzerMissingIndex:
    """Tests for missing index detection branch (line 278->277)."""

    def test_missing_index_not_flagged_when_table_covered_by_index(self):
        """Test missing index NOT flagged when table IS in indexes (branch 278->277)."""
        analyzer = QueryAnalyzer("test_db")
        # "Index Scan on users" -> regex captures "users"
        # indexes_used = ["users"]
        # [idx.split(".")[0] for idx in ["users"]] = ["users"]
        # "users" not in ["users"] -> False -> branch not taken (278->277)
        explain_output = (
            "Seq Scan on users  (cost=0.00..10000.00 rows=5000 width=4)\n"
            "Index Scan on users  (cost=0.00..8.00 rows=1 width=4)\n"
        )
        analysis = analyzer.analyze(
            "SELECT * FROM users WHERE status = 1",
            explain_output=explain_output,
        )
        assert "users" not in analysis.missing_indexes

    def test_missing_index_detection_many_rows(self):
        """Test missing index IS flagged for seq scan with > 1000 rows and no matching index."""
        analyzer = QueryAnalyzer("test_db")
        explain_output = "Seq Scan on orders  (cost=0.00..50000.00 rows=5000 width=4)\n"
        analysis = analyzer.analyze(
            "SELECT * FROM orders WHERE status = 1",
            explain_output=explain_output,
        )
        assert "orders" in analysis.missing_indexes


class TestQueryAnalyzerSuggestions:
    """Tests for suggestion branches (lines 291-292, 302-303)."""

    def test_high_cost_suggestion(self):
        """Test high cost suggestion is added (lines 291-292)."""
        analyzer = QueryAnalyzer("test_db", high_cost_threshold=100.0)
        explain_output = "Seq Scan on orders  (cost=0.00..200.00 rows=10 width=4)\n"
        analysis = analyzer.analyze("SELECT * FROM orders", explain_output=explain_output)
        assert analysis.needs_optimization is True
        assert any("High cost" in s for s in analysis.suggestions)

    def test_large_sort_suggestion(self):
        """Test large sort suggestion is added (lines 302-303)."""
        analyzer = QueryAnalyzer("test_db")
        explain_output = "Sort  (cost=0.00..100.00 rows=20000 width=4)\n  Sort Key: created_at\n"
        analysis = analyzer.analyze(
            "SELECT * FROM events ORDER BY created_at",
            explain_output=explain_output,
        )
        assert analysis.needs_optimization is True
        assert any("sort" in s.lower() for s in analysis.suggestions)

    def test_slow_queries_list_trimmed_at_100(self):
        """Test that _slow_queries list is trimmed to last 100 entries (line 332)."""
        analyzer = QueryAnalyzer("test_db_trim", slow_query_threshold_ms=0.001)
        for i in range(110):
            analyzer.analyze(f"SELECT * FROM table_{i}", actual_time_ms=1000.0)
        with analyzer._lock:
            assert len(analyzer._slow_queries) == 100


class TestParseExplainIndexExtraction:
    """Tests for index extraction in _parse_explain (lines 375, 380)."""

    def test_parse_explain_with_index_using(self):
        """Test index extraction using 'using' keyword (lines 375, 380)."""
        analyzer = QueryAnalyzer("test_db")
        explain_output = (
            "Index Scan using idx_users_email on users  (cost=0.00..8.00 rows=1 width=4)\n"
        )
        analysis = analyzer.analyze(
            "SELECT * FROM users WHERE id = 1",
            explain_output=explain_output,
        )
        assert "idx_users_email" in analysis.indexes_used

    def test_parse_explain_with_index_on(self):
        """Test index extraction using 'on' keyword (lines 375, 380)."""
        analyzer = QueryAnalyzer("test_db")
        explain_output = (
            "Bitmap Index Scan on idx_orders_status  (cost=0.00..5.00 rows=100 width=0)\n"
        )
        analysis = analyzer.analyze(
            "SELECT * FROM orders WHERE status = 1",
            explain_output=explain_output,
        )
        assert "idx_orders_status" in analysis.indexes_used

    def test_parse_explain_with_sort_detected(self):
        """Test Sort detection in explain (line 375)."""
        analyzer = QueryAnalyzer("test_db")
        explain_output = "Sort  (cost=10.00..12.00 rows=100 width=4)\n  Sort Key: name\n"
        result = analyzer._parse_explain(explain_output)
        assert result["sort"] is True


class TestGetAnalysis:
    """Tests for get_analysis method (lines 391-392)."""

    def test_get_analysis_returns_analysis(self):
        """Test get_analysis returns analysis by hash (lines 391-392)."""
        analyzer = QueryAnalyzer("test_db")
        analysis = analyzer.analyze("SELECT * FROM users WHERE id = 1")
        retrieved = analyzer.get_analysis(analysis.query_hash)
        assert retrieved is not None
        assert retrieved.query_hash == analysis.query_hash

    def test_get_analysis_returns_none_for_missing(self):
        """Test get_analysis returns None for unknown hash."""
        analyzer = QueryAnalyzer("test_db")
        result = analyzer.get_analysis("nonexistent_hash")
        assert result is None


class TestClear:
    """Tests for clear method (lines 396-398)."""

    def test_clear_removes_analyses(self):
        """Test clear() removes all stored analyses (lines 396-398)."""
        analyzer = QueryAnalyzer("test_db")
        analyzer.analyze("SELECT * FROM users")
        analyzer.analyze("SELECT * FROM orders", actual_time_ms=1000.0)
        with analyzer._lock:
            assert len(analyzer._analyses) > 0
        analyzer.clear()
        with analyzer._lock:
            assert len(analyzer._analyses) == 0
            assert len(analyzer._slow_queries) == 0


class _RaceSimulatingDict(dict):
    """A dict subclass that simulates a race condition for double-checked locking tests.

    On the first __contains__ call for the race_key that returns False, it
    immediately inserts the race_value so the next __contains__ call returns True.
    This simulates another thread inserting the value after the outer check but
    before the inner check (acquires lock).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._race_key = None
        self._race_value = None
        self._triggered = False

    def __contains__(self, key):
        result = super().__contains__(key)
        if not result and key == self._race_key and not self._triggered:
            self._triggered = True
            # Insert now so inner check (after lock acquired) sees it
            self[key] = self._race_value
        return result


class TestSingletonDoubleCheck:
    """Tests for the double-checked locking singleton (lines 413->416)."""

    def test_get_query_analyzer_concurrent_creation(self):
        """Test double-checked locking in get_query_analyzer."""
        db_name = f"concurrent_test_db_{id(object())}"
        if db_name in qa_module._analyzers:
            del qa_module._analyzers[db_name]

        results = []

        def create_analyzer():
            analyzer = get_query_analyzer(db_name)
            results.append(analyzer)

        threads = [threading.Thread(target=create_analyzer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r is results[0] for r in results)

    def test_get_query_analyzer_inner_check_false_race_condition(self):
        """Test inner branch (413->416): outer if True but inner if False (race simulation).

        Covers the branch where outer check (line 411) is True (key not present),
        lock is acquired, but inner check (line 413) is False because another thread
        already added the entry. Code skips line 414 and goes directly to return.
        """
        db_name = f"race_sim_{id(object())}"
        existing_analyzer = QueryAnalyzer(db_name)

        race_dict = _RaceSimulatingDict()
        race_dict._race_key = db_name
        race_dict._race_value = existing_analyzer

        with patch.object(qa_module, "_analyzers", race_dict):
            result = get_query_analyzer(db_name)

        assert result is existing_analyzer
        assert race_dict[db_name] is existing_analyzer

    def test_get_query_analyzer_returns_existing_without_lock(self):
        """Test get_query_analyzer returns existing without acquiring lock (outer if False)."""
        db_name = f"existing_test_{id(object())}"
        existing = QueryAnalyzer(db_name)
        qa_module._analyzers[db_name] = existing

        result = get_query_analyzer(db_name)
        assert result is existing
