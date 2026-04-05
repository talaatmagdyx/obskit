# Repository Tracing Decorator

`instrument_repo` is a class decorator that automatically wraps every public async method of a repository class with an OTel trace span.  Apply it once at class definition time and every DB operation becomes visible in distributed traces — no per-method boilerplate required.

## Quick Start

```python
from obskit import instrument_repo

@instrument_repo(component="postgres")
class NotesRepo:
    async def insert_note(self, title: str, body: str) -> None:
        await self._db.execute(
            "INSERT INTO notes (title, body) VALUES ($1, $2)", title, body
        )

    async def get_notes(self, limit: int = 100) -> list[dict]:
        return await self._db.fetch("SELECT * FROM notes LIMIT $1", limit)
```

Each method call creates a span:

| Call | Span name | component |
|------|-----------|-----------|
| `repo.insert_note(...)` | `NotesRepo.insert_note` | `postgres` |
| `repo.get_notes()` | `NotesRepo.get_notes` | `postgres` |

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `component` | `"db"` | Span `component` attribute — appears in trace views. Use `"postgres"`, `"redis"`, `"mongo"`, etc. |
| `span_prefix` | class name | Override the prefix in span names. Useful for aliasing a repo to a shorter name. |
| `slow_threshold_ms` | `None` | Emit a `slow_repo_operation` warning log when any method exceeds this duration in milliseconds. |

## Slow Operation Warnings

Pass `slow_threshold_ms` to get automatic warnings for any method that exceeds the threshold:

```python
from obskit import instrument_repo

@instrument_repo(component="postgres", slow_threshold_ms=200.0)
class OrderRepo:
    async def get_orders(self, tenant_id: str) -> list[dict]:
        return await self._db.fetch("SELECT * FROM orders WHERE tid=$1", tenant_id)
```

When `get_orders` takes longer than 200 ms, a structured warning is emitted:

```json
{
  "event": "slow_repo_operation",
  "operation": "OrderRepo.get_orders",
  "duration_ms": 347.8,
  "threshold_ms": 200.0
}
```

The warning fires even when the method raises an exception, so slow failures are always visible.

## Custom Prefix

```python
@instrument_repo(component="postgres", span_prefix="tags")
class TagsRepository:
    async def upsert_tags(self, entity_id: int, tags: list[str]) -> None: ...
    async def delete_tags(self, entity_id: int) -> None: ...
# Spans: "tags.upsert_tags", "tags.delete_tags"
```

## What Gets Wrapped

| Method type | Wrapped? |
|-------------|----------|
| Public async methods (`async def method(self, ...)`) | Yes |
| Private/dunder methods (`_method`, `__init__`) | No |
| Synchronous methods (`def method(self, ...)`) | No |
| `@staticmethod` | No |
| `@classmethod` | No |

## Exceptions Are Propagated

If a wrapped method raises, the exception propagates unchanged after the span closes:

```python
@instrument_repo(component="postgres")
class AssignmentRepo:
    async def upsert_assignment(self, data: dict) -> None:
        raise DatabaseError("connection lost")

# Span ends, exception propagates — caller handles it normally
```

## Multiple Repos

```python
@instrument_repo(component="postgres")
class AssignmentRepo: ...

@instrument_repo(component="postgres")
class NotesRepo: ...

@instrument_repo(component="postgres")
class TagsRepo: ...

@instrument_repo(component="postgres")
class CustomFieldsRepo: ...
```

---

# Event Handler Instrumentation

`instrument_event_handler` is an async decorator factory that wraps event handlers with an OTel span and Prometheus metrics — no per-handler boilerplate required.

## Quick Start

```python
from obskit import instrument_event_handler

@instrument_event_handler(name="order_created")
async def handle_order_created(event: dict) -> None:
    order_id = event["order_id"]
    await process_order(order_id)
```

Each invocation:

- Creates a child OTel span named `event_handler.order_created`
- Records latency in `event_handler_duration_seconds{name="order_created"}`
- Increments `event_handler_errors_total{name="order_created"}` on any exception

## Parameters

| Parameter | Description |
|-----------|-------------|
| `name` | Logical handler name — used as the `name` label in all metrics and appended to the OTel span name: `event_handler.<name>`. |

## Emitted Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `event_handler_duration_seconds{name}` | Histogram | `name` | Handler duration in seconds. Always recorded — including when the handler raises. |
| `event_handler_errors_total{name}` | Counter | `name` | Exceptions raised by the handler. |

## Span Name Convention

The OTel span is named `event_handler.<name>`:

| `name` parameter | Span name |
|------------------|-----------|
| `"order_created"` | `event_handler.order_created` |
| `"engagement_insert"` | `event_handler.engagement_insert` |
| `"status_update"` | `event_handler.status_update` |

## Error Handling

The decorator re-raises the original exception unchanged after incrementing the error counter and recording duration:

```python
@instrument_event_handler(name="payment_processed")
async def handle_payment(event: dict) -> None:
    raise ValueError("missing payment_id")

# ValueError propagates to the caller unchanged
# event_handler_errors_total{name="payment_processed"} += 1
# event_handler_duration_seconds{name="payment_processed"} observed
```

## Class Methods

The decorator works correctly on class methods:

```python
class EngagementInsertHandler:
    @instrument_event_handler(name="engagement_insert")
    async def handle(self, event: dict) -> None:
        await self.repo.insert(event["engagement"])
```

## Multiple Handlers

```python
@instrument_event_handler(name="order_created")
async def handle_order_created(event: dict) -> None: ...

@instrument_event_handler(name="order_cancelled")
async def handle_order_cancelled(event: dict) -> None: ...

@instrument_event_handler(name="payment_processed")
async def handle_payment_processed(event: dict) -> None: ...
```

Each handler has its own independent metric series.

## Grafana alert example

```promql
# Alert when any event handler error rate rises
rate(event_handler_errors_total[5m]) > 0

# P99 handler latency by name
histogram_quantile(0.99,
  rate(event_handler_duration_seconds_bucket[5m])
) by (name)
```

---

## API Reference

::: obskit.decorators.repo.instrument_repo
::: obskit.decorators.event_handler.instrument_event_handler
