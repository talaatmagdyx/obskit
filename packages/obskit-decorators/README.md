# obskit-decorators

Cross-cutting observability decorators for Python microservices — part of the obskit toolkit.

## Installation

```bash
pip install obskit-decorators
```

## Features

- **`@observe`** — Instrument any function with metrics, logging, and tracing in one decorator
- **`@trace`** — Add distributed tracing spans to functions
- **`@combined`** — Combine multiple observability concerns declaratively
- Context managers for observability scopes

## Usage

```python
from obskit.decorators import observe, trace

@observe(operation="create_order", track_metrics=True, track_tracing=True)
async def create_order(order_data: dict) -> dict:
    ...

@trace(span_name="process_payment")
async def process_payment(amount: float) -> bool:
    ...
```

## Part of obskit

This package is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo.
