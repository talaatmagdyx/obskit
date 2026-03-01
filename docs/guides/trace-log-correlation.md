# How to Correlate Traces with Logs

Trace-log correlation automatically injects `trace_id` and `span_id` from the active
OpenTelemetry span into every structured log record.  Once both are present in your logs,
you can navigate directly from a Grafana Loki log line to the full trace in Grafana Tempo
with a single click.

---

## What is trace-log correlation?

Every OpenTelemetry span carries two identifiers:

- **`trace_id`** — a 32-hex-character identifier shared by every span in the same distributed
  request chain.
- **`span_id`** — a 16-hex-character identifier unique to this particular operation.

When `obskit-logging` is installed alongside `obskit-tracing`, a structlog processor
(`add_trace_context`) reads those identifiers from the current OpenTelemetry context
(stored in Python `contextvars`) and injects them into the log record *before* it is
serialised.  The processor runs zero-cost when no span is active — it simply skips the
injection step.

```
HTTP request arrives
  └─ OTel middleware creates span  (trace_id=4bf92f35…, span_id=00f067aa…)
       └─ handler calls log.info("order_placed", order_id="ord-123")
            └─ add_trace_context processor reads OTel context
                 └─ {"event": "order_placed", "order_id": "ord-123",
                      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
                      "span_id": "00f067aa0ba902b7"}
```

The resulting JSON log line can be ingested by Loki, and the `trace_id` field becomes
a clickable link to the corresponding Tempo trace.

---

## Requirements

| Package | Minimum version | Role |
|---------|-----------------|------|
| `obskit-logging` | 2.0.0 | Provides `get_logger()` and the structlog processor |
| `obskit-tracing` | 2.0.0 | Provides the OTel SDK configuration |
| `opentelemetry-sdk` | 1.20.0 | OTel span context storage |
| `structlog` | 23.0.0 | Structured logging backend |

`obskit-tracing` is **optional**.  When it is absent, `get_logger()` still works normally
and logs simply omit the trace fields.

---

## Installation

```bash
pip install "obskit[otlp]"
```

---

## How the processor is wired in

`get_logger()` builds a structlog chain that already includes `add_trace_context`.
You do not need to configure anything manually:

```python
from obskit.logging import get_logger

log = get_logger("order_service")
```

If you want to inspect whether trace-correlation support is active at runtime, use
the availability check:

```python
from obskit.logging.trace_correlation import is_trace_correlation_available

if is_trace_correlation_available():
    print("trace_id / span_id will be injected automatically")
else:
    print("obskit-tracing not installed — logs will not carry trace fields")
```

---

## Basic example: with and without an active span

=== "Without a span"

    ```python
    from obskit.logging import get_logger

    log = get_logger("demo")

    # No OTel span is active here
    log.info("user_signup", email="alice@example.com")
    ```

    **Log output (JSON)**

    ```json
    {
      "event": "user_signup",
      "email": "alice@example.com",
      "level": "info",
      "timestamp": "2026-02-28T10:00:00.123456Z"
    }
    ```

    No `trace_id` or `span_id` fields — the processor detects the absence of an active
    span and leaves the record unchanged.

=== "With an active span"

    ```python
    from obskit.logging import get_logger
    from obskit.tracing import setup_tracing
    from opentelemetry import trace

    setup_tracing(service_name="demo", exporter_endpoint="http://localhost:4317")
    tracer = trace.get_tracer("demo")
    log = get_logger("demo")

    with tracer.start_as_current_span("handle_signup"):
        log.info("user_signup", email="alice@example.com")
    ```

    **Log output (JSON)**

    ```json
    {
      "event": "user_signup",
      "email": "alice@example.com",
      "level": "info",
      "timestamp": "2026-02-28T10:00:00.123456Z",
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "span_id": "00f067aa0ba902b7"
    }
    ```

---

## Reading the trace context programmatically

If you need the trace fields for purposes other than logging (for example, to include
them in an API response body or an error payload), call `get_trace_context()` directly:

```python
from obskit.logging.trace_correlation import get_trace_context

ctx = get_trace_context()
# Returns {"trace_id": "4bf92f35...", "span_id": "00f067aa..."} when a span is active.
# Returns {} when no span is active.

if ctx:
    print(f"Current trace: {ctx['trace_id']}")
```

---

## FastAPI example: automatic per-request correlation

When you add the obskit FastAPI middleware, every HTTP request is wrapped in an OTel
span automatically.  Every log line emitted inside a handler therefore carries the
request's `trace_id` without any extra code.

```python
from fastapi import FastAPI
from obskit.logging import get_logger
from obskit.middleware.fastapi import ObservabilityMiddleware
from obskit.tracing import setup_tracing

setup_tracing(service_name="order-service", exporter_endpoint="http://localhost:4317")

app = FastAPI()
app.add_middleware(ObservabilityMiddleware, service_name="order-service")

log = get_logger("order_service")


@app.post("/orders")
async def create_order(payload: dict):
    # The middleware has already started an OTel span for this request.
    # The log line below will automatically contain trace_id + span_id.
    log.info("order_received", customer_id=payload.get("customer_id"))

    order_id = "ord-9f2a"
    log.info("order_created", order_id=order_id)

    return {"order_id": order_id}
```

**Example log stream for a single POST /orders request:**

```json
{"event": "order_received", "customer_id": "cust-42",  "trace_id": "4bf92f35...", "span_id": "00f067aa..."}
{"event": "order_created",  "order_id": "ord-9f2a",   "trace_id": "4bf92f35...", "span_id": "00f067aa..."}
```

Both lines share the same `trace_id` and can be retrieved together with a single Loki
query.

---

## Async example: context propagation through tasks

Python `contextvars` propagate automatically when you use `asyncio.create_task()` or
`asyncio.gather()`.  Child tasks inherit the parent's OTel context, so their logs also
carry the same `trace_id`.

```python
import asyncio
from obskit.logging import get_logger
from obskit.tracing import setup_tracing
from opentelemetry import trace

setup_tracing(service_name="worker", exporter_endpoint="http://localhost:4317")
tracer = trace.get_tracer("worker")
log = get_logger("worker")


async def process_item(item_id: str) -> None:
    # Inherits OTel context from the parent task via contextvars.
    log.info("processing_item", item_id=item_id)
    await asyncio.sleep(0.01)
    log.info("item_processed", item_id=item_id)


async def handle_batch(batch: list[str]) -> None:
    with tracer.start_as_current_span("handle_batch"):
        log.info("batch_started", size=len(batch))
        # All tasks created here inherit the active span context.
        await asyncio.gather(*[process_item(i) for i in batch])
        log.info("batch_done")


asyncio.run(handle_batch(["item-1", "item-2", "item-3"]))
```

!!! note "Thread pools are different"
    Context propagation works automatically with `asyncio.create_task()`.
    If you dispatch work to a `ThreadPoolExecutor` you must copy the context manually:

    ```python
    import contextvars, concurrent.futures

    ctx = contextvars.copy_context()
    executor.submit(ctx.run, your_function, *args)
    ```

---

## Grafana Loki queries

### Find all logs for a specific trace

```logql
{app="order-service"} | json | trace_id="4bf92f3577b34da6a3ce929d0e0e4736"
```

### Find error logs that have a trace_id

```logql
{app="order-service"} | json | level="error" | trace_id != ""
```

### Count error log lines per trace in the last hour

```logql
sum by (trace_id) (
  count_over_time(
    {app="order-service"} | json | level="error" [1h]
  )
)
```

---

## Grafana: jumping from a trace to its logs (Tempo → Loki)

Configure a **Derived Field** on the Loki datasource so that `trace_id` values in log
lines become clickable links to Tempo.

1. In Grafana, open **Configuration → Data Sources → Loki**.
2. Scroll to **Derived fields** and click **Add**.
3. Fill in:
   - **Name**: `TraceID`
   - **Regex**: `"trace_id":"([a-f0-9]+)"`
   - **URL**: `${__value.raw}`  (select the Tempo datasource from the **URL Label** dropdown)
4. Save the datasource.

Now every log line in Explore that contains a `trace_id` will show a **Tempo** button
next to the value.

Alternatively, configure a **Trace to logs** link on the **Tempo** datasource:

1. Open **Configuration → Data Sources → Tempo**.
2. Under **Trace to logs**, select **Loki** as the logs datasource.
3. Set the **Tags** field to `app` so Grafana filters Loki by `{app="<service-name>"}`.
4. Enable **Filter by trace ID** and **Filter by span ID**.

With this configuration, clicking any span in the Tempo trace view opens the Loki
Explore panel pre-filtered to that exact `trace_id`.

---

## Checking availability at runtime

```python
from obskit.logging.trace_correlation import is_trace_correlation_available

print(is_trace_correlation_available())
# True  — obskit-tracing and opentelemetry-sdk are installed and initialised
# False — trace context injection is disabled (logs still work normally)
```

Use this in a startup check or health endpoint to verify your environment is wired
up correctly before sending traffic.

---

## Troubleshooting

### "My logs don't have trace_id"

Work through the checklist in order:

1. **Is `obskit-tracing` installed?**

   ```bash
   python -m obskit.core.diagnose
   ```

   Look for `obskit-tracing` with status `installed` and `trace-correlation: available`.

2. **Has `setup_tracing()` been called before the first log statement?**

   Calling `setup_tracing()` initialises the OTel `TracerProvider`.  If it is called
   after the first request is processed, earlier log lines will not carry trace fields.

3. **Is the logger created with `get_logger()`?**

   The `add_trace_context` processor is only part of the chain when you use
   `obskit.logging.get_logger()`.  A bare `logging.getLogger()` or a manually
   constructed structlog logger will not include it.

4. **Is a span actually active at the point of the log call?**

   ```python
   from opentelemetry import trace
   span = trace.get_current_span()
   print(span.get_span_context().is_valid)  # Must be True
   ```

   If this prints `False`, the middleware is not wrapping the request or the log call
   is outside the span scope.

5. **Are logs parsed as JSON in Loki?**

   The Loki query must include `| json` to parse the structured fields.  Without it,
   `trace_id` is not extracted and filters against it will not match.

### "trace_id appears as all zeros (00000000...)"

This usually means the OTel SDK is installed but no exporter / provider has been
configured.  The SDK creates a no-op span with an invalid context.  Call
`setup_tracing()` with a valid `exporter_endpoint`.

### "Logs in async tasks don't have trace_id"

See the note in the [Async example](#async-example-context-propagation-through-tasks)
section above.  Thread pool workers require manual context copying.

---

## Summary

| Step | What to do |
|------|------------|
| Install | `pip install "obskit[otlp]"` |
| Initialise | Call `setup_tracing()` at application startup |
| Create logger | Use `get_logger()` — not `logging.getLogger()` |
| Verify | `is_trace_correlation_available()` returns `True` |
| Loki query | `{app="…"} \| json \| trace_id="<id>"` |
| Grafana link | Configure Tempo → Loki "Trace to logs" derived field |
