# obskit-logging

Structured logging for Python services — built on structlog with automatic correlation-ID and trace-context injection.

## Install

```bash
pip install obskit-logging
```

## Quick start

```python
from obskit.logging import get_logger

logger = get_logger(__name__)
logger.info("order_placed", order_id="ord-123", user_id="usr-456", total=99.99)
```

Output (JSON, production):
```json
{"level": "info", "event": "order_placed", "order_id": "ord-123", "user_id": "usr-456", "total": 99.99, "service": "my-service", "timestamp": "2026-02-28T10:00:00Z"}
```

## Trace-log correlation

When `obskit-tracing` (or `opentelemetry-api`) is installed, every log record automatically gains `trace_id` and `span_id`:

```json
{"event": "order_placed", "trace_id": "4bf92f3577b34da6...", "span_id": "00f067aa0ba902b7"}
```

No extra code needed — the `add_trace_context` processor is injected automatically.

## Key features

| Feature | API |
|---------|-----|
| Structured logger | `get_logger(__name__)` |
| Bind context | `logger.bind(request_id="x").info(...)` |
| Performance log | `log_performance("op", "Svc", 45.2, threshold_ms=200)` |
| Error log + traceback | `log_error(exc, "Component", "operation")` |
| Smart sampling | `SampledLogger`, `AdaptiveSampledLogger` |
| Trace-log correlation | `get_trace_context()` → `{"trace_id": ..., "span_id": ...}` |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OBSKIT_LOG_FORMAT` | `"json"` | `"json"` or `"console"` |
| `OBSKIT_LOG_LEVEL` | `"INFO"` | Minimum log level |
| `OBSKIT_LOG_INCLUDE_TIMESTAMP` | `true` | Add ISO timestamp |
