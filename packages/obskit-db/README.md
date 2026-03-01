<div align="center">

# 🗄️ obskit-db

**SQLAlchemy instrumentation, N+1 query detection, slow query logging, and connection pool monitoring**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-db.svg?color=blue)](https://pypi.org/project/obskit-db/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Instruments SQLAlchemy engines automatically** — one call to `instrument_sqlalchemy(engine)` hooks into every query executed against that engine, recording duration metrics, logging slow queries, tracking pool saturation, and catching errors without touching any application code.
- **Detects N+1 queries and slow operations** — `QueryAnalyzer` fingerprints SQL statements, parses `EXPLAIN` output, detects sequential scans on large tables, and surfaces actionable optimization suggestions before they hit production.
- **Gives per-query full-stack observability** — the `DatabaseTracker` context manager wraps any database call with RED metrics, distributed tracing spans (OpenTelemetry), SLO measurements, and tenant context in a single `with` block.

---

## Installation

```bash
pip install obskit-db

# With SQLAlchemy support
pip install "obskit-db[sqlalchemy]"
```

---

## Quick Start

```python
from sqlalchemy import create_engine
from obskit.db import instrument_sqlalchemy

engine = create_engine(
    "postgresql+psycopg2://orders_user:secret@db.internal:5432/orders_db",
    pool_size=10,
    max_overflow=20,
)

# That's it — all queries are now instrumented
instrument_sqlalchemy(engine, database_name="orders_db")
```

From this point on, every query executed through `engine` is:

- Timed and recorded as `orders_db_requests_total` and `orders_db_request_duration_seconds`
- Logged at WARNING level if it exceeds 1 000 ms
- Tracked for connection pool saturation (`orders_db.connections` golden signal)
- Logged at ERROR level on any DB-level exception

---

## `instrument_sqlalchemy` — Automatic Engine Instrumentation

```python
from sqlalchemy import create_engine
from obskit.db import instrument_sqlalchemy

engine = create_engine("postgresql+psycopg2://user:pass@localhost/ecommerce")
instrument_sqlalchemy(engine, database_name="ecommerce")

# Instrument multiple engines in the same process
read_engine = create_engine("postgresql+psycopg2://ro_user:pass@replica/ecommerce")
instrument_sqlalchemy(read_engine, database_name="ecommerce_replica")
```

### What is hooked automatically

| SQLAlchemy Event | What obskit does |
|---|---|
| `before_cursor_execute` | Records `perf_counter()` start time on the execution context |
| `after_cursor_execute` | Computes duration, records metrics, logs if `> 1 000 ms` |
| `handle_error` | Logs `sql_query_error` with error type and original exception |
| `connect` | Updates pool saturation gauge (`checkedout / pool_size`) |

### Slow query log output

```json
{
  "event": "slow_sql_query",
  "database": "ecommerce",
  "duration_ms": 1847.3,
  "query": "SELECT o.*, p.name, p.sku FROM orders o JOIN order_items oi ON ..."
}
```

---

## `DatabaseTracker` — Per-Query Full-Stack Observability

For fine-grained control, wrap individual operations with `DatabaseTracker.track_query()`. It adds RED metrics, an OpenTelemetry span, optional SLO measurement, and tenant context.

```python
from obskit.db import DatabaseTracker

tracker = DatabaseTracker(
    database_name="ecommerce",
    default_slo_name="db_query_latency_p95",
    default_slow_threshold_ms=500.0,
)


async def get_customer_orders(customer_id: str, tenant_id: str) -> list[dict]:
    query = """
        SELECT o.id, o.status, o.total_cents, o.created_at
        FROM orders o
        WHERE o.customer_id = :customer_id
        ORDER BY o.created_at DESC
        LIMIT 50
    """
    with tracker.track_query(
        operation="get_customer_orders",
        query=query,
        tenant_id=tenant_id,
        slo_name="order_query_latency",
        slow_query_threshold_ms=300.0,
        attributes={"customer.id": customer_id},
    ):
        return await db_session.execute(text(query), {"customer_id": customer_id})
```

### Module-level convenience function

```python
from obskit.db import track_query

async def fetch_product(product_id: str) -> dict | None:
    with track_query(
        operation="fetch_product",
        database_name="catalog",
        query="SELECT * FROM products WHERE id = :id",
        tenant_id="store-42",
        slow_query_threshold_ms=200.0,
    ):
        return await catalog_db.get(product_id)
```

### What `track_query` records

| Signal | Details |
|---|---|
| RED metrics | `ecommerce.get_customer_orders` rate, error rate, duration histogram |
| OpenTelemetry span | `db.get_customer_orders` span with `db.system`, `db.statement`, `tenant.id` attributes |
| SLO measurement | `order_query_latency` tracked as success/failure against your SLO budget |
| Slow query log | WARNING with `operation`, `duration_ms`, `threshold_ms`, `tenant_id` |
| Error log | ERROR with `error`, `error_type`, full stack trace on exception |

---

## `QueryAnalyzer` — N+1 Detection and EXPLAIN Parsing

`QueryAnalyzer` fingerprints every query (normalizing literals and values) and can parse PostgreSQL `EXPLAIN` output to surface optimization opportunities.

```python
from obskit.query_analyzer import QueryAnalyzer

analyzer = QueryAnalyzer(
    database_name="ecommerce",
    slow_query_threshold_ms=100.0,
    high_cost_threshold=1000.0,
)


# Analyze a query after execution
async def get_orders_with_items(customer_id: str):
    query = """
        SELECT o.*, oi.product_id, oi.quantity
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        WHERE o.customer_id = :customer_id
    """
    explain_output = await db.scalar(
        text(f"EXPLAIN {query}"), {"customer_id": customer_id}
    )
    result = await db.execute(text(query), {"customer_id": customer_id})

    # Analyze EXPLAIN output and actual timing
    analysis = analyzer.analyze(
        query=query,
        explain_output=explain_output,
        actual_time_ms=47.3,
    )

    if analysis.needs_optimization:
        for suggestion in analysis.suggestions:
            logger.warning("query_optimization_needed", suggestion=suggestion)

    return result.all()
```

### `QueryAnalysis` fields

```python
analysis.query_hash          # "a3f8d2c1e9b4"  — stable fingerprint for grouping
analysis.query_type          # QueryType.SELECT
analysis.tables_accessed     # ["orders", "order_items"]
analysis.indexes_used        # ["idx_orders_customer_id"]
analysis.missing_indexes     # ["order_items"]  — tables with Seq Scan and >1 000 rows
analysis.estimated_cost      # 4721.5  — EXPLAIN total cost
analysis.estimated_rows      # 18_500
analysis.has_seq_scan        # True
analysis.has_sort            # False
analysis.needs_optimization  # True
analysis.suggestions         # ["Consider adding index for sequential scan on ['order_items']"]
```

### Reviewing recent slow queries

```python
slow = analyzer.get_slow_queries(limit=10)
for q in slow:
    print(f"{q.query_hash}  cost={q.estimated_cost:.0f}  {q.suggestions}")
```

### Prometheus metrics emitted

| Metric | Description |
|---|---|
| `query_analyzer_queries_total` | Queries analyzed, labeled by `database` and `query_type` |
| `query_analyzer_plan_cost` | Estimated EXPLAIN cost histogram |
| `query_analyzer_slow_queries_total` | Queries exceeding the slow threshold |
| `query_analyzer_missing_index_total` | Tables detected with missing indexes |

---

## Connection Pool Monitoring

`instrument_sqlalchemy` automatically tracks pool saturation. You can also read pool state directly:

```python
pool = engine.pool

print(f"Checked out: {pool.checkedout()}")
print(f"Pool size:   {pool.size()}")
print(f"Overflow:    {pool.overflow()}")
print(f"Saturation:  {pool.checkedout() / pool.size():.1%}")
```

Set a Prometheus alert when saturation exceeds 80%:

```yaml
# Prometheus alert rule
- alert: DBPoolExhaustion
  expr: |
    ecommerce_saturation{resource="ecommerce.connections"} > 0.8
  for: 5m
  annotations:
    summary: "Database connection pool near exhaustion"
```

---

## Multi-tenant Usage

Pass `tenant_id` to `track_query` for per-tenant query observability in SaaS applications:

```python
async def get_tenant_invoices(tenant_id: str, month: str) -> list[dict]:
    with tracker.track_query(
        operation="list_invoices",
        tenant_id=tenant_id,
        attributes={"billing.month": month},
    ):
        return await invoices_db.list(tenant_id=tenant_id, month=month)
```

The `tenant.id` attribute is included in every OpenTelemetry span, enabling per-tenant query latency analysis in Jaeger or Tempo.

---

## Integration with obskit-health

When obskit-health is installed, you can expose a database health endpoint:

```python
from obskit.health import HealthChecker
from obskit.db import DatabaseTracker

checker = HealthChecker()

async def check_db_health() -> dict:
    try:
        with DatabaseTracker("ecommerce").track_query(
            "health_check",
            query="SELECT 1",
        ):
            await engine.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

checker.register("database", check_db_health)
```

---

## Environment Variables / Configuration

| Variable | Default | Description |
|---|---|---|
| `OBSKIT_DB_SLOW_QUERY_THRESHOLD_MS` | `1000.0` | Slow query logging threshold (ms) |
| `OBSKIT_DB_POOL_SATURATION_WARN` | `0.8` | Pool saturation warning threshold |

---

## Part of the obskit family

`obskit-db` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-db` | `pip install "obskit[all]"` |
