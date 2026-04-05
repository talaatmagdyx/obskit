# Startup Validation

`configure_observability()` emits structured log events at startup so misconfiguration surfaces immediately — at process start rather than at the first failed request.

---

## Overview

Every call to `configure_observability()` emits one or more structured events through the obskit log pipeline.  These events are machine-readable (they appear in JSON in production) and also captured by `structlog.testing.capture_logs()` in tests.

### Events emitted

| Event | Level | When emitted |
|---|---|---|
| `obskit_configured` | `info` | Always — summary of the active configuration |
| `otlp_endpoint_is_localhost` | `warning` | When `tracing_enabled=True` and endpoint contains `localhost` |
| `otlp_endpoint_not_configured` | `warning` | When `tracing_enabled=True` but no endpoint is set |
| `log_sampling_active` | `info` | When `log_sample_rate < 1.0` |

---

## `obskit_configured`

Emitted on every `configure_observability()` call.  Contains the full active configuration so you can verify what was applied.

```json
{
  "event": "obskit_configured",
  "level": "info",
  "service": "my-api",
  "environment": "production",
  "version": "2.0.0",
  "log_level": "INFO",
  "log_format": "json",
  "tracing_enabled": true,
  "otlp_endpoint": "http://tempo:4317",
  "trace_sample_rate": 0.1,
  "log_sample_rate": 1.0,
  "timestamp": "2026-04-03T10:00:00.000000Z"
}
```

Fields:

| Field | Description |
|---|---|
| `service` | Service name passed to `configure_observability()` |
| `environment` | Runtime environment (`production`, `staging`, …) |
| `version` | Application version |
| `log_level` | Active log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `log_format` | Log format (`json` or `console`) |
| `tracing_enabled` | Whether distributed tracing is active |
| `otlp_endpoint` | OTLP collector URL (or `"(disabled)"` when not set) |
| `trace_sample_rate` | Fraction of traces sampled (1.0 = 100%) |
| `log_sample_rate` | Fraction of non-error logs sampled (1.0 = 100%) |

---

## Warnings

### `otlp_endpoint_is_localhost`

```json
{
  "event": "otlp_endpoint_is_localhost",
  "level": "warning",
  "endpoint": "http://localhost:4317",
  "hint": "Set OBSKIT_OTLP_ENDPOINT to your collector in production"
}
```

Fired when tracing is enabled and the OTLP endpoint contains `localhost`.  This is a common misconfiguration when a service is promoted from development to production without updating the `OBSKIT_OTLP_ENDPOINT` environment variable.

**Fix:** Set the environment variable to your collector's address:

```bash
OBSKIT_OTLP_ENDPOINT=http://tempo.monitoring:4317
```

### `otlp_endpoint_not_configured`

```json
{
  "event": "otlp_endpoint_not_configured",
  "level": "warning",
  "hint": "Tracing is enabled but no OTLP endpoint is set — spans will be dropped"
}
```

Fired when `tracing_enabled=True` but no endpoint is configured.  All spans are silently dropped in this state.

### `log_sampling_active`

```json
{
  "event": "log_sampling_active",
  "level": "info",
  "rate": 0.1,
  "hint": "Only a fraction of non-error logs will be emitted"
}
```

Fired as a reminder when `log_sample_rate < 1.0`.  Error and warning logs are always emitted regardless of the sample rate.

---

## Testing startup events

Use `structlog.testing.capture_logs()` to assert which events were emitted during startup:

```python
import structlog.testing
import structlog
from obskit.config import configure_observability, reset_settings
from obskit.core.observability import reset_observability
from obskit.logging.logger import reset_logging

def test_startup():
    reset_settings()
    reset_observability()
    reset_logging()
    structlog.reset_defaults()

    with structlog.testing.capture_logs() as logs:
        configure_observability(
            service_name="my-api",
            environment="production",
            tracing_enabled=True,
            otlp_endpoint="http://tempo:4317",
        )

    events = {e["event"] for e in logs}
    assert "obskit_configured" in events
    assert "otlp_endpoint_is_localhost" not in events  # remote endpoint — no warning
```

!!! note "Why `structlog.reset_defaults()`?"
    obskit configures structlog with `cache_logger_on_first_use=True` for performance.  Call `structlog.reset_defaults()` in test teardown to clear the logger cache so `capture_logs()` correctly intercepts the next test's startup events.

---

## Integration with log aggregators

The `obskit_configured` event is emitted with all the same structured fields that appear on every subsequent log line.  In Loki or Elasticsearch, you can filter by this event to build a startup audit trail:

```logql
{app="my-api"} | json | event = "obskit_configured"
```

```kuery
event: "obskit_configured" AND environment: "production"
```
