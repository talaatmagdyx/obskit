# obskit-db

Database observability — query tracking, slow-query detection, and SQLAlchemy auto-instrumentation.

```bash
pip install "obskit[sqlalchemy]"
```

---

## Overview

`obskit.db` gives every database query RED metrics, distributed traces, SLO tracking, and slow-query logging with a single line of code.

| Component | What it does |
|-----------|-------------|
| **`instrument_sqlalchemy`** | Zero-code: attaches event listeners to a SQLAlchemy engine |
| **`DatabaseTracker`** | Fine-grained per-operation tracking with tenant context |
| **`track_query`** | Convenience function — no class needed |

---

## Quick Start

=== "Auto-instrument SQLAlchemy (zero code)"

    ```python
    from sqlalchemy import create_engine
    from obskit.db import instrument_sqlalchemy

    engine = create_engine("postgresql://user:pass@localhost/mydb")
    instrument_sqlalchemy(engine, database_name="postgres")

    # All queries are now automatically tracked — no other changes needed
    with engine.connect() as conn:
        conn.execute(text("SELECT * FROM orders"))
    ```

=== "DatabaseTracker (per-operation)"

    ```python
    from obskit.db import DatabaseTracker

    db = DatabaseTracker("postgres", default_slow_threshold_ms=500.0)

    def get_user(user_id: str, tenant_id: str):
        with db.track_query("get_user", tenant_id=tenant_id):
            return session.query(User).filter_by(id=user_id).first()
    ```

=== "Convenience function"

    ```python
    from obskit.db import track_query

    with track_query("create_order", database_name="postgres",
                     tenant_id="acme", slow_query_threshold_ms=200.0):
        session.add(order)
        session.commit()
    ```

---

## `instrument_sqlalchemy`

Attaches SQLAlchemy event listeners to track **every** query automatically.

```python
instrument_sqlalchemy(engine, database_name="database")
```

**What it tracks:**

- ✅ Query execution time (via Golden Signals saturation metric)
- ✅ Slow queries — logs warning when duration > 1 second
- ✅ Query errors — logs every `handle_error` event
- ✅ Connection pool saturation on each new connection

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `engine` | `Engine` | required | SQLAlchemy engine |
| `database_name` | `str` | `"database"` | Label used in all metrics and logs |

```python
# Multiple databases
instrument_sqlalchemy(read_engine,  database_name="postgres_read")
instrument_sqlalchemy(write_engine, database_name="postgres_write")
```

---

## `DatabaseTracker`

Fine-grained tracking with tenant context, SLO integration, and per-operation thresholds.

```python
from obskit.db import DatabaseTracker

db = DatabaseTracker(
    database_name="postgres",
    default_slo_name="db_latency",        # optional: wire to SLO tracker
    default_slow_threshold_ms=1000.0,     # warn on queries > 1s
)
```

### `track_query(operation, ...)` — context manager

```python
with db.track_query(
    operation="get_orders",
    query="SELECT * FROM orders WHERE tenant_id = :tid",  # for logs
    slow_query_threshold_ms=200.0,   # override per operation
    tenant_id="acme",
    slo_name="order_read_latency",
    attributes={"order_status": "pending"},
    enable_tracing=True,
    enable_slo=True,
):
    return session.execute(stmt).fetchall()
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `operation` | `str` | required | Operation name for metrics/traces |
| `query` | `str \| None` | `None` | SQL text (truncated to 200 chars in logs) |
| `slow_query_threshold_ms` | `float \| None` | instance default | Override slow threshold |
| `tenant_id` | `str \| None` | `None` | Multi-tenant context |
| `slo_name` | `str \| None` | instance default | SLO to record against |
| `attributes` | `dict \| None` | `None` | Extra span attributes |
| `enable_tracing` | `bool` | `True` | Create an OTLP span |
| `enable_slo` | `bool` | `True` | Record SLO measurement |

### `record_query(operation, duration_seconds, ...)` — manual

For when you can't use a context manager (e.g., wrapping an ORM callback):

```python
start = time.perf_counter()
try:
    result = execute_raw(sql)
    db.record_query("raw_query", time.perf_counter() - start, success=True)
except Exception as e:
    db.record_query("raw_query", time.perf_counter() - start,
                    success=False, error_type=type(e).__name__)
    raise
```

---

## `track_query` — Convenience Function

Stateless wrapper — creates a temporary `DatabaseTracker` internally.

```python
from obskit.db import track_query

with track_query(
    operation="create_order",
    database_name="postgres",
    query="INSERT INTO orders ...",
    slow_query_threshold_ms=500.0,
    tenant_id="acme",
):
    session.add(order)
    session.commit()
```

---

## What Gets Emitted

### Structured Logs

Every query emits a structured log entry on completion:

```json
{
  "event": "db_query_completed",
  "database": "postgres",
  "operation": "get_orders",
  "duration_ms": 12.4,
  "success": true,
  "tenant_id": "acme"
}
```

Slow queries emit an additional warning:

```json
{
  "event": "slow_sql_query",
  "database": "postgres",
  "duration_ms": 1234.5,
  "query": "SELECT * FROM orders WHERE ..."
}
```

### Prometheus Metrics

`DatabaseTracker` records via **Golden Signals** (shared across all instrumented databases):

| Metric | Source |
|--------|--------|
| `golden_signal_latency_seconds` | `track_query` duration |
| `golden_signal_errors_total` | Failed queries |
| `golden_signal_saturation` | Connection pool utilization |

### Distributed Traces

Each `track_query` call creates an OTLP span with:

- `db.system` = database name
- `db.operation` = operation name
- `db.statement` = query text (if provided)
- `tenant.id` = tenant ID (if provided)

---

## Pattern: Reusable Tracker per Repository

```python
# src/repositories/base.py
from obskit.db import DatabaseTracker

_db = DatabaseTracker("postgres", default_slow_threshold_ms=500.0)

class OrderRepository:
    def get(self, order_id: str, tenant_id: str):
        with _db.track_query("get_order", tenant_id=tenant_id):
            return self.session.get(Order, order_id)

    def create(self, order: Order, tenant_id: str):
        with _db.track_query("create_order", tenant_id=tenant_id):
            self.session.add(order)
            self.session.commit()
            return order
```

---

## See Also

- [`obskit.query_analyzer`](utilities.md#query-plan-analyzer) — analyze query execution plans
- [SLO Tracking](slo.md) — wire `slo_name` to an SLO target
- [Resilience](resilience.md) — circuit breaker for database connections
