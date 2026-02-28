# obskit-core

Core configuration, settings, error types, and shared interfaces for the obskit observability toolkit.

## Install

```bash
pip install obskit-core
```

## What's inside

| Module | Purpose |
|--------|---------|
| `obskit.config` | Pydantic-settings based `ObskitSettings` with env-var support |
| `obskit.errors` | Shared exception hierarchy |
| `obskit.core.context` | Thread/async-safe correlation-ID context |
| `obskit.interfaces` | Abstract base classes for all obskit packages |
| `obskit.middleware.base` | Base ASGI/WSGI middleware |

## Quick start

```python
from obskit.config import get_settings

settings = get_settings()
print(settings.service_name)   # "my-service" (from env OBSKIT_SERVICE_NAME)
print(settings.environment)    # "production"
```

### Correlation IDs

```python
from obskit.core.context import set_correlation_id, get_correlation_id

set_correlation_id("req-abc-123")
cid = get_correlation_id()   # "req-abc-123"
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OBSKIT_SERVICE_NAME` | `"service"` | Service name used in all telemetry |
| `OBSKIT_ENVIRONMENT` | `"development"` | Deployment environment |
| `OBSKIT_VERSION` | `"0.0.0"` | Service version |
| `OBSKIT_LOG_LEVEL` | `"INFO"` | Minimum log level |
| `OBSKIT_TRACING_ENABLED` | `true` | Enable OTel tracing |
| `OBSKIT_OTLP_ENDPOINT` | `""` | OTLP collector URL |

## Part of the obskit family

`obskit-core` is a dependency of every other obskit package. Install the full stack with `pip install obskit`.
