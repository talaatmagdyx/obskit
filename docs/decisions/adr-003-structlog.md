# ADR-003: structlog over stdlib logging

**Date:** 2025-06-01
**Status:** Accepted

## Context

obskit needs a logging library that supports structured (JSON) output, context binding, and custom processors. The two main options are Python's standard `logging` module with JSON formatters, and `structlog`.

## Decision

Use **structlog** as the primary logging library for obskit.

## Rationale

| Concern | stdlib + JSON formatter | structlog |
|---------|------------------------|-----------|
| Context binding | Manual `extra={}` dict | `log = log.bind(user_id=...)` |
| Processor pipeline | Not supported | First-class (`add_log_level`, `add_timestamp`, …) |
| Trace injection | Manual in every call | Single processor in the chain |
| Async support | Limited | `AsyncBoundLogger` |
| Type safety | Poor | Good |
| Learning curve | Low | Medium |

The processor pipeline is what enables obskit's `add_trace_context` to inject `trace_id`/`span_id` into **every** log record automatically, without modifying application code.

## Consequences

- `structlog` is a required dependency of `obskit` (always-on; not a separate optional extra)
- Applications using stdlib `logging` directly won't get auto trace injection (they must use `get_logger()`)
- structlog output is fully compatible with `logging` handlers when `configure()` is called with `wrapper_class=structlog.stdlib.BoundLogger`
