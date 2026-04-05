# Multi-App Observability Setup

Services that run multiple FastAPI apps (e.g. an API service on port 8000 and an upload service on port 8001) need each app independently instrumented.  `configure_app_observability` does both steps — middleware and metrics endpoint — in a single call.

## Quick Start

```python
from fastapi import FastAPI
from obskit import configure_observability
from obskit.middleware.instrument import configure_app_observability

obs = configure_observability(service_name="upload-service")

upload_app = FastAPI(title="upload-service")
configure_app_observability(upload_app, exclude_paths=["/v2/_healthy"])
```

This is equivalent to:

```python
from obskit import instrument_fastapi
from obskit.metrics.registry import generate_latest
from starlette.requests import Request
from starlette.responses import Response

instrument_fastapi(upload_app, exclude_paths=["/v2/_healthy"])

@upload_app.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    return Response(generate_latest(), media_type="text/plain; version=0.0.4")
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `app` | — | The FastAPI application. |
| `exclude_paths` | middleware defaults | Paths excluded from observability. |
| `track_metrics` | `True` | Enable RED metrics. |
| `track_logging` | `True` | Enable request/response logging. |
| `track_tracing` | `True` | Enable distributed tracing. |
| `metrics_path` | `"/metrics"` | URL path for the Prometheus scrape endpoint. |

## Custom Metrics Path

```python
configure_app_observability(upload_app, metrics_path="/internal/metrics")
```

## API Reference

::: obskit.middleware.instrument.configure_app_observability
