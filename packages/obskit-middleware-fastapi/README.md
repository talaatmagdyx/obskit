# obskit-middleware-fastapi

FastAPI middleware that automatically injects correlation IDs, RED metrics, and distributed tracing into every request.

## Install

```bash
pip install "obskit-middleware-fastapi"
```

## Quick start

```python
from fastapi import FastAPI
from obskit.middleware.fastapi import ObskitMiddleware

app = FastAPI()
app.add_middleware(ObskitMiddleware)

@app.get("/orders/{id}")
async def get_order(id: str):
    # correlation_id, trace_id, RED metrics all automatic
    return {"id": id}
```

## What it adds to every request

- `X-Correlation-ID` header (generated or forwarded from incoming request)
- RED metrics: `{service}_requests_total`, `{service}_request_duration_seconds`
- OpenTelemetry span (if `obskit-tracing` is configured)

## Configuration

```python
app.add_middleware(
    ObskitMiddleware,
    exclude_paths=["/health", "/metrics", "/ready"],
)
```
