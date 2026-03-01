<div align="center">

# ✨ obskit-decorators

**Cross-cutting `@with_observability` and `observe` decorators — add full observability to any function in one line**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-decorators.svg?color=blue)](https://pypi.org/project/obskit-decorators/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Eliminates observability boilerplate** — a single `@with_observability(component="OrderService")` replaces dozens of lines of manual timing, logging, and Prometheus counter calls in every function.
- **Records RED metrics automatically** — request rate, error rate, and duration histograms go to Prometheus on every call, with labels for component and operation, at no extra cost to the developer.
- **Works on both sync and async functions** — `with_observability` handles async, `with_observability_sync` handles sync, and `observe` / `observe_sync` double as context managers for inline instrumentation blocks.

---

## Installation

```bash
pip install obskit-decorators
```

---

## Quick Start

```python
from obskit.decorators import with_observability

@with_observability(
    component="OrderService",
    operation="create_order",
    threshold_ms=500.0,   # warn in logs if this takes longer than 500 ms
    log_start=True,
)
async def create_order(customer_id: str, items: list[dict]) -> dict:
    order = await db.insert_order(customer_id, items)
    await inventory.reserve(items)
    await notifications.send_confirmation(order)
    return order
```

Every call to `create_order` now automatically:

1. Logs `operation_started` at DEBUG level
2. Records wall-clock duration via `time.perf_counter()`
3. On success — logs `operation_completed` with duration, records `order_service_requests_total{status="success"}` and `order_service_request_duration_seconds`
4. On failure — logs `operation_failed` with the full exception, records `order_service_requests_total{status="failure", error_type="..."}` and re-raises

---

## Before and After

Without decorators, every business function needs ~20 lines of instrumentation scaffolding:

```python
# BEFORE — boilerplate repeated in every function
async def process_payment(order_id: str, amount: float) -> dict:
    start = time.perf_counter()
    logger.info("operation_started", operation="process_payment", component="PaymentService")

    try:
        result = await gateway.charge(order_id, amount)
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info("operation_completed", operation="process_payment",
                    component="PaymentService", duration_ms=duration_ms)
        payment_requests_total.labels(status="success").inc()
        payment_duration.observe(duration_ms / 1000)
        return result

    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error("operation_failed", operation="process_payment",
                     component="PaymentService", error=str(e),
                     error_type=type(e).__name__, exc_info=True)
        payment_requests_total.labels(status="failure").inc()
        raise
```

With `@with_observability`, the same result in one line:

```python
# AFTER — business logic only
@with_observability(component="PaymentService", threshold_ms=1000.0)
async def process_payment(order_id: str, amount: float) -> dict:
    return await gateway.charge(order_id, amount)
```

---

## `@with_observability` — Full Async Observability

```python
from obskit.decorators import with_observability

@with_observability(
    component="InventoryService",      # service/module name → metric prefix
    operation="check_stock",           # defaults to function name if omitted
    threshold_ms=200.0,                # logs a warning when exceeded
    track_metrics=True,                # set False for logging-only
    log_start=False,                   # set True to log operation start
    sample_rate=1.0,                   # 0.01 = sample 1% of calls
    high_throughput=False,             # True → ring-buffer pipeline (~100 ns overhead)
)
async def check_stock(product_id: str, warehouse_id: str) -> int:
    return await inventory_db.get_qty(product_id, warehouse_id)
```

### Performance threshold warnings

When a call exceeds `threshold_ms`, obskit logs a `slow_operation` event automatically:

```json
{
  "event": "slow_operation",
  "component": "InventoryService",
  "operation": "check_stock",
  "duration_ms": 347.2,
  "threshold_ms": 200.0,
  "exceeded_by_ms": 147.2
}
```

### Extra context on every log

```python
@with_observability(
    component="TenantService",
    region="eu-west-1",           # injected into all log entries
    team="platform",
)
async def get_tenant_config(tenant_id: str) -> dict:
    return await config_store.fetch(tenant_id)

# Every log entry: {"region": "eu-west-1", "team": "platform", ...}
```

---

## `@with_observability_sync` — Full Sync Observability

The synchronous version has an identical API:

```python
from obskit.decorators import with_observability_sync

@with_observability_sync(
    component="ReportExporter",
    threshold_ms=5000.0,
)
def export_monthly_report(month: str, format: str = "csv") -> bytes:
    data = db.fetch_monthly_orders(month)
    return render_report(data, format)
```

---

## `@track_operation` — Lightweight Logging Only

For internal helpers that need traceability but not Prometheus metrics:

```python
from obskit.decorators import track_operation

@track_operation(component="OrderMapper")
async def map_to_domain(raw_order: dict) -> dict:
    """Transform raw DB row to domain Order object."""
    return {
        "id": raw_order["order_id"],
        "customer": raw_order["customer_uuid"],
        "total": raw_order["total_cents"] / 100,
        "status": raw_order["status_code"],
    }
```

Logs `operation_started` and `operation_completed` (DEBUG) on success, and `operation_failed` (ERROR) with a stack trace on failure. No Prometheus metrics emitted.

---

## `@track_metrics_only` — High-Frequency Metrics

For operations called thousands of times per second where log noise is unacceptable:

```python
from obskit.decorators import track_metrics_only

@track_metrics_only(component="CacheService", operation="cache_get")
async def get_cart_from_cache(session_id: str) -> dict | None:
    return await redis.get(f"cart:{session_id}")


@track_metrics_only(component="CacheService", operation="cache_set")
async def store_cart_in_cache(session_id: str, cart: dict, ttl: int = 3600) -> None:
    await redis.setex(f"cart:{session_id}", ttl, cart)
```

Records `cache_service_requests_total` and `cache_service_request_duration_seconds` on every call — zero log noise.

---

## `observe` and `observe_sync` — Context Managers

`observe` and `observe_sync` are both context managers **and** decorators (built on `@asynccontextmanager` / `@contextmanager`). Use them when the code block to observe is not a clean function boundary.

### As a context manager (async)

```python
from obskit.decorators import observe

async def fulfill_order(order_id: str) -> None:
    order = await db.get_order(order_id)

    async with observe(
        operation="reserve_inventory",
        component="FulfillmentService",
        threshold_ms=300.0,
    ):
        await inventory.reserve(order.items)

    async with observe(
        operation="create_shipment",
        component="FulfillmentService",
        threshold_ms=500.0,
    ):
        await shipping.book(order)
```

### As a decorator (async)

```python
@observe(operation="fetch_orders", component="OrderService")
async def fetch_pending_orders() -> list[dict]:
    return await db.fetch_where(status="pending")
```

### Synchronous context manager

```python
from obskit.decorators import observe_sync

def generate_invoice(order_id: str) -> bytes:
    with observe_sync(
        operation="pdf_render",
        component="InvoiceService",
        threshold_ms=2000.0,
    ):
        return pdf_renderer.render(order_id)
```

---

## Choosing the Right Decorator

| Decorator | Logging | Prometheus Metrics | Use Case |
|---|---|---|---|
| `with_observability` | Yes | Yes | Business operations (orders, payments) |
| `with_observability_sync` | Yes | Yes | Synchronous business operations |
| `track_operation` | Yes | No | Internal helpers, data mappers |
| `track_metrics_only` | No | Yes | High-frequency cache / DB operations |
| `observe` / `observe_sync` | Yes | Yes | Ad-hoc instrumentation blocks |

---

## High-Throughput Mode

For functions in the hot path (>10 000 calls/s), switch to the ring-buffer pipeline. Overhead drops from ~20 µs to ~100 ns per call at the cost of best-effort semantics (logs may be dropped under extreme load; metrics flush every ~1 s):

```python
@with_observability(
    component="PricingEngine",
    operation="calculate_price",
    high_throughput=True,
)
async def calculate_price(product_id: str, quantity: int) -> float:
    return await pricing_db.get_price(product_id) * quantity
```

---

## Sampling

Reduce observability overhead for very high-traffic endpoints by sampling a fraction of calls:

```python
@with_observability(
    component="SearchService",
    operation="typeahead_suggest",
    sample_rate=0.05,    # fully observe 5% of calls; skip 95%
)
async def typeahead(prefix: str) -> list[str]:
    return await search_index.suggest(prefix)
```

Non-sampled calls still execute the function normally — only the instrumentation pipeline is bypassed.

---

## Composing with Other Decorators

`@with_observability` is fully compatible with other decorators. Stack it outermost so it wraps all layers:

```python
from obskit.decorators import with_observability
from obskit.resilience import retry, CircuitBreaker

checkout_cb = CircuitBreaker("checkout-service", failure_threshold=5)

@with_observability(component="CheckoutService", threshold_ms=2000.0)
@retry(max_attempts=3, base_delay=0.5)
@checkout_cb
async def submit_checkout(cart_id: str, payment_token: str) -> dict:
    return await checkout_api.submit(cart_id, payment_token)
```

---

## What Gets Logged

All events follow obskit's structured logging format (JSON by default). Example output for a successful call:

```json
{"event": "operation_completed", "component": "OrderService", "operation": "create_order",
 "status": "success", "duration_ms": 43.7, "correlation_id": "cid-8f2a"}
```

For a failed call:

```json
{"event": "operation_failed", "component": "OrderService", "operation": "create_order",
 "status": "failure", "duration_ms": 12.1, "error": "duplicate key value",
 "error_type": "IntegrityError", "correlation_id": "cid-8f2a"}
```

---

## Part of the obskit family

`obskit-decorators` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-decorators` | `pip install "obskit[all]"` |
