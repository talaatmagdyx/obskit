"""
Query Plan Analyzer
===================

Analyze and track database query execution plans.

Features:
- EXPLAIN plan parsing
- Slow query detection
- Index usage analysis
- Query optimization suggestions

Example:
    from obskit.query_analyzer import QueryAnalyzer

    analyzer = QueryAnalyzer()

    plan = analyzer.analyze("SELECT * FROM users WHERE email = ?")
    if plan.needs_optimization:
        print(f"Suggestions: {plan.suggestions}")
"""

import hashlib
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from prometheus_client import Counter, Histogram

from obskit.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

QUERY_ANALYZED_TOTAL = Counter(
    "query_analyzer_queries_total", "Total queries analyzed", ["database", "query_type"]
)

QUERY_PLAN_COST = Histogram(
    "query_analyzer_plan_cost",
    "Query plan cost",
    ["database"],
    buckets=(1, 10, 100, 1000, 10000, 100000),
)

SLOW_QUERIES_TOTAL = Counter(
    "query_analyzer_slow_queries_total", "Queries identified as slow", ["database", "query_type"]
)

MISSING_INDEX_DETECTED = Counter(
    "query_analyzer_missing_index_total", "Queries with missing index", ["database", "table"]
)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class QueryType(Enum):
    """Types of SQL queries."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    OTHER = "OTHER"


class ScanType(Enum):
    """Types of table scans."""

    SEQ_SCAN = "Sequential Scan"
    INDEX_SCAN = "Index Scan"
    INDEX_ONLY_SCAN = "Index Only Scan"
    BITMAP_SCAN = "Bitmap Scan"
    OTHER = "Other"


@dataclass
class QueryPlanNode:
    """A node in the query plan tree."""

    node_type: str
    table: str | None = None
    index: str | None = None
    scan_type: ScanType = ScanType.OTHER
    rows_estimate: int = 0
    cost: float = 0.0
    actual_time_ms: float = 0.0
    children: list["QueryPlanNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_type": self.node_type,
            "table": self.table,
            "index": self.index,
            "scan_type": self.scan_type.value,
            "rows_estimate": self.rows_estimate,
            "cost": self.cost,
            "actual_time_ms": self.actual_time_ms,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class QueryAnalysis:
    """Analysis result for a query."""

    query_hash: str
    query_type: QueryType
    tables_accessed: list[str]
    indexes_used: list[str]
    missing_indexes: list[str]
    estimated_cost: float
    estimated_rows: int
    actual_time_ms: float | None = None
    plan_tree: QueryPlanNode | None = None
    has_seq_scan: bool = False
    has_sort: bool = False
    needs_optimization: bool = False
    suggestions: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_hash": self.query_hash,
            "query_type": self.query_type.value,
            "tables_accessed": self.tables_accessed,
            "indexes_used": self.indexes_used,
            "missing_indexes": self.missing_indexes,
            "estimated_cost": self.estimated_cost,
            "estimated_rows": self.estimated_rows,
            "actual_time_ms": self.actual_time_ms,
            "has_seq_scan": self.has_seq_scan,
            "has_sort": self.has_sort,
            "needs_optimization": self.needs_optimization,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Query Analyzer
# =============================================================================


class QueryAnalyzer:
    """
    Analyze SQL query execution plans.

    Parameters
    ----------
    database_name : str
        Database identifier
    slow_query_threshold_ms : float
        Threshold for slow query detection
    high_cost_threshold : float
        Threshold for high cost queries
    """

    def __init__(
        self,
        database_name: str = "default",
        slow_query_threshold_ms: float = 100.0,
        high_cost_threshold: float = 1000.0,
    ):
        self.database_name = database_name
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.high_cost_threshold = high_cost_threshold

        self._analyses: dict[str, QueryAnalysis] = {}
        self._slow_queries: list[QueryAnalysis] = []
        self._lock = threading.Lock()

    def _hash_query(self, query: str) -> str:
        """Create a hash for the query."""
        # Normalize query
        normalized = re.sub(r"\s+", " ", query.strip().upper())
        # Replace literals
        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        normalized = re.sub(r"\b\d+\b", "?", normalized)

        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def _detect_query_type(self, query: str) -> QueryType:
        """Detect the type of SQL query."""
        query_upper = query.strip().upper()

        if query_upper.startswith("SELECT"):
            return QueryType.SELECT
        elif query_upper.startswith("INSERT"):
            return QueryType.INSERT
        elif query_upper.startswith("UPDATE"):
            return QueryType.UPDATE
        elif query_upper.startswith("DELETE"):
            return QueryType.DELETE
        else:
            return QueryType.OTHER

    def _extract_tables(self, query: str) -> list[str]:
        """Extract table names from query."""
        tables = []

        # FROM clause
        from_match = re.findall(r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)", query, re.IGNORECASE)
        tables.extend(from_match)

        # JOIN clauses
        join_match = re.findall(r"\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)", query, re.IGNORECASE)
        tables.extend(join_match)

        # UPDATE/INSERT tables
        update_match = re.findall(r"\bUPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)", query, re.IGNORECASE)
        tables.extend(update_match)

        insert_match = re.findall(
            r"\bINSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)", query, re.IGNORECASE
        )
        tables.extend(insert_match)

        return list(set(tables))

    def analyze(
        self,
        query: str,
        explain_output: str | None = None,
        actual_time_ms: float | None = None,
    ) -> QueryAnalysis:
        """
        Analyze a query.

        Parameters
        ----------
        query : str
            SQL query
        explain_output : str, optional
            EXPLAIN output if available
        actual_time_ms : float, optional
            Actual execution time

        Returns
        -------
        QueryAnalysis
        """
        query_hash = self._hash_query(query)
        query_type = self._detect_query_type(query)
        tables = self._extract_tables(query)

        # Parse EXPLAIN output if provided
        indexes_used = []
        missing_indexes = []
        estimated_cost = 0.0
        estimated_rows = 0
        has_seq_scan = False
        has_sort = False
        plan_tree = None

        if explain_output:
            plan_data = self._parse_explain(explain_output)
            indexes_used = plan_data.get("indexes", [])
            estimated_cost = plan_data.get("cost", 0)
            estimated_rows = plan_data.get("rows", 0)
            has_seq_scan = plan_data.get("seq_scan", False)
            has_sort = plan_data.get("sort", False)
            plan_tree = plan_data.get("tree")

        # Detect potential missing indexes
        if has_seq_scan and estimated_rows > 1000:
            for table in tables:
                if table not in [idx.split(".")[0] for idx in indexes_used]:
                    missing_indexes.append(table)
                    MISSING_INDEX_DETECTED.labels(database=self.database_name, table=table).inc()

        # Generate suggestions
        suggestions = []
        needs_optimization = False

        if has_seq_scan and estimated_rows > 100:
            suggestions.append(f"Consider adding index for sequential scan on {tables}")
            needs_optimization = True

        if estimated_cost > self.high_cost_threshold:
            suggestions.append(f"High cost query ({estimated_cost}). Review query plan.")
            needs_optimization = True

        if actual_time_ms and actual_time_ms > self.slow_query_threshold_ms:
            suggestions.append(f"Slow query ({actual_time_ms}ms). Consider optimization.")
            needs_optimization = True
            SLOW_QUERIES_TOTAL.labels(
                database=self.database_name, query_type=query_type.value
            ).inc()

        if has_sort and estimated_rows > 10000:
            suggestions.append("Large sort operation. Consider adding ORDER BY index.")
            needs_optimization = True

        # Record metrics
        QUERY_ANALYZED_TOTAL.labels(database=self.database_name, query_type=query_type.value).inc()

        if estimated_cost > 0:
            QUERY_PLAN_COST.labels(database=self.database_name).observe(estimated_cost)

        analysis = QueryAnalysis(
            query_hash=query_hash,
            query_type=query_type,
            tables_accessed=tables,
            indexes_used=indexes_used,
            missing_indexes=missing_indexes,
            estimated_cost=estimated_cost,
            estimated_rows=estimated_rows,
            actual_time_ms=actual_time_ms,
            plan_tree=plan_tree,
            has_seq_scan=has_seq_scan,
            has_sort=has_sort,
            needs_optimization=needs_optimization,
            suggestions=suggestions,
        )

        with self._lock:
            self._analyses[query_hash] = analysis
            if needs_optimization:
                self._slow_queries.append(analysis)
                if len(self._slow_queries) > 100:
                    self._slow_queries = self._slow_queries[-100:]

        if needs_optimization:
            logger.warning(
                "query_needs_optimization",
                query_hash=query_hash,
                query_type=query_type.value,
                cost=estimated_cost,
                suggestions=suggestions,
            )

        return analysis

    def _parse_explain(self, explain_output: str) -> dict[str, Any]:
        """Parse EXPLAIN output (PostgreSQL format)."""
        result = {
            "indexes": [],
            "cost": 0.0,
            "rows": 0,
            "seq_scan": False,
            "sort": False,
            "tree": None,
        }

        lines = explain_output.split("\n")

        for line in lines:
            # Extract cost
            cost_match = re.search(r"cost=[\d.]+\.\.(\d+\.?\d*)", line)
            if cost_match:
                result["cost"] = max(result["cost"], float(cost_match.group(1)))

            # Extract rows
            rows_match = re.search(r"rows=(\d+)", line)
            if rows_match:
                result["rows"] = max(result["rows"], int(rows_match.group(1)))

            # Detect seq scan
            if "Seq Scan" in line or "Sequential Scan" in line:
                result["seq_scan"] = True

            # Detect sort
            if "Sort" in line:
                result["sort"] = True

            # Extract index names
            index_match = re.search(r"Index.*?(?:using|on)\s+(\w+)", line, re.IGNORECASE)
            if index_match:
                result["indexes"].append(index_match.group(1))

        return result

    def get_slow_queries(self, limit: int = 10) -> list[QueryAnalysis]:
        """Get recent slow queries."""
        with self._lock:
            return list(reversed(self._slow_queries[-limit:]))

    def get_analysis(self, query_hash: str) -> QueryAnalysis | None:
        """Get analysis by query hash."""
        with self._lock:
            return self._analyses.get(query_hash)

    def clear(self):
        """Clear all analyses."""
        with self._lock:
            self._analyses.clear()
            self._slow_queries.clear()


# =============================================================================
# Singleton
# =============================================================================

_analyzers: dict[str, QueryAnalyzer] = {}
_analyzer_lock = threading.Lock()


def get_query_analyzer(database_name: str = "default", **kwargs) -> QueryAnalyzer:
    """Get or create a query analyzer."""
    if database_name not in _analyzers:
        with _analyzer_lock:
            if database_name not in _analyzers:
                _analyzers[database_name] = QueryAnalyzer(database_name, **kwargs)

    return _analyzers[database_name]
