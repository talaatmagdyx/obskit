"""Unit tests for Query Plan Analyzer."""

import pytest
from obskit.query_analyzer import (
    QueryAnalyzer,
    QueryAnalysis,
    QueryType,
    get_query_analyzer,
)


class TestQueryAnalyzer:
    """Tests for QueryAnalyzer."""

    def test_detect_query_type_select(self):
        """Test SELECT query detection."""
        analyzer = QueryAnalyzer("test_db")
        
        analysis = analyzer.analyze("SELECT * FROM users WHERE id = 1")
        assert analysis.query_type == QueryType.SELECT

    def test_detect_query_type_insert(self):
        """Test INSERT query detection."""
        analyzer = QueryAnalyzer("test_db")
        
        analysis = analyzer.analyze("INSERT INTO users (name) VALUES ('test')")
        assert analysis.query_type == QueryType.INSERT

    def test_detect_query_type_update(self):
        """Test UPDATE query detection."""
        analyzer = QueryAnalyzer("test_db")
        
        analysis = analyzer.analyze("UPDATE users SET name = 'new' WHERE id = 1")
        assert analysis.query_type == QueryType.UPDATE

    def test_detect_query_type_delete(self):
        """Test DELETE query detection."""
        analyzer = QueryAnalyzer("test_db")
        
        analysis = analyzer.analyze("DELETE FROM users WHERE id = 1")
        assert analysis.query_type == QueryType.DELETE

    def test_extract_tables(self):
        """Test table extraction from query."""
        analyzer = QueryAnalyzer("test_db")
        
        analysis = analyzer.analyze(
            "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert "users" in analysis.tables_accessed
        assert "orders" in analysis.tables_accessed

    def test_analyze_with_explain(self):
        """Test analysis with EXPLAIN output."""
        analyzer = QueryAnalyzer("test_db")
        
        explain_output = """
        Seq Scan on users  (cost=0.00..35.50 rows=2550 width=4)
        """
        
        analysis = analyzer.analyze(
            "SELECT * FROM users",
            explain_output=explain_output,
        )
        
        assert analysis.has_seq_scan is True
        assert analysis.estimated_cost > 0

    def test_slow_query_detection(self):
        """Test slow query detection."""
        analyzer = QueryAnalyzer("test_db", slow_query_threshold_ms=50.0)
        
        analysis = analyzer.analyze(
            "SELECT * FROM large_table",
            actual_time_ms=100.0,
        )
        
        assert analysis.needs_optimization is True
        assert any("slow" in s.lower() for s in analysis.suggestions)

    def test_query_hash(self):
        """Test query hash normalization."""
        analyzer = QueryAnalyzer("test_db")
        
        analysis1 = analyzer.analyze("SELECT * FROM users WHERE id = 1")
        analysis2 = analyzer.analyze("SELECT * FROM users WHERE id = 2")
        
        # Same query pattern should have same hash
        assert analysis1.query_hash == analysis2.query_hash

    def test_get_slow_queries(self):
        """Test slow query retrieval."""
        analyzer = QueryAnalyzer("test_db", slow_query_threshold_ms=10.0)
        
        analyzer.analyze("SELECT * FROM fast", actual_time_ms=5.0)
        analyzer.analyze("SELECT * FROM slow", actual_time_ms=100.0)
        
        slow = analyzer.get_slow_queries()
        assert len(slow) >= 1


class TestQueryAnalysis:
    """Tests for QueryAnalysis."""

    def test_to_dict(self):
        """Test QueryAnalysis serialization."""
        analysis = QueryAnalysis(
            query_hash="abc123",
            query_type=QueryType.SELECT,
            tables_accessed=["users"],
            indexes_used=["idx_users_id"],
            missing_indexes=[],
            estimated_cost=10.5,
            estimated_rows=100,
        )
        
        data = analysis.to_dict()
        assert data["query_hash"] == "abc123"
        assert data["query_type"] == "SELECT"
        assert "users" in data["tables_accessed"]


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_query_analyzer(self):
        """Test query analyzer singleton per database."""
        analyzer1 = get_query_analyzer("db1")
        analyzer2 = get_query_analyzer("db1")
        analyzer3 = get_query_analyzer("db2")
        
        assert analyzer1 is analyzer2
        assert analyzer1 is not analyzer3
