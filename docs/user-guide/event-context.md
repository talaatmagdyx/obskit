# Event Handler Context

Worker processes — RabbitMQ consumers, Celery tasks, background loops — run without HTTP middleware, so `company_id` and other tenant fields are never automatically bound to structlog context-vars.  Without them, every log line from the worker is anonymous and debugging requires painful cross-referencing.

`with_event_context` solves this by binding the tenant context for the duration of a single event handler call.

## Quick Start

```python
from obskit import with_event_context
import structlog

logger = structlog.get_logger()

@with_event_context(lambda event: {
    "company_id": str(event.get("company_id", "")),
    "company_schema": event.get("company_schema", ""),
})
async def handle(self, event: dict) -> None:
    logger.info("processing event")
    # → {"event": "processing event", "company_id": "42", "company_schema": "acme_db", ...}
    await self.repo.create_record(event["data"])
```

## How It Works

1. Before the handler is called, `extractor(event)` is called to produce a dict of context-var bindings.
2. The bindings are added to the structlog context via `bind_contextvars(**ctx)`.
3. The handler runs — all log calls inside it include the bound fields automatically.
4. On exit (normal return **or** exception), the bound keys are removed via `unbind_contextvars(*ctx.keys())`.

## Extractor Function

The extractor receives the raw event dict and returns a dict of bindings:

```python
def my_extractor(event: dict) -> dict:
    company_id = event.get("company_id")
    if company_id is None:
        return {}  # skip binding — no tenant context in this event
    return {
        "company_id": str(company_id),
        "company_schema": event.get("company_schema", ""),
    }

@with_event_context(my_extractor)
async def handle(self, event: dict) -> None:
    ...
```

Returning `{}` or `None` skips all binding — no keys are added or removed.

## Standalone Functions

The decorator works with standalone async functions too (no `self`):

```python
@with_event_context(lambda e: {"job_id": e.get("job_id")})
async def process_job(event: dict) -> None:
    ...
```

## Exception Safety

The context is **always** unbound on exit, even if the handler raises:

```python
@with_event_context(lambda e: {"company_id": str(e.get("company_id"))})
async def handle(self, event: dict) -> None:
    raise RuntimeError("unexpected error")
# company_id is removed from context even though an exception was raised
```

## Scope Isolation

Only the keys returned by the extractor are unbound on exit.  Keys bound inside the handler (or by outer middleware) are not affected:

```python
bind_context(request_id="req-123")  # bound before handler

@with_event_context(lambda e: {"company_id": str(e.get("company_id"))})
async def handle(self, event: dict) -> None:
    bind_context(extra="info")  # bound inside — caller's responsibility

# After handler: request_id is still bound, company_id is unbound
```

## API Reference

::: obskit.logging.event_context.with_event_context
