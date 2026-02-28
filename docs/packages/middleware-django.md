# obskit-middleware-django

Automatic per-request observability for Django applications. Works with both WSGI (sync) and ASGI (async) deployments, providing correlation ID propagation, structured logging, RED metrics, and distributed tracing through Django's standard middleware API.

## Installation

```bash
pip install obskit-middleware-django
```

---

## Setup

Add `ObskitDjangoMiddleware` to your Django `MIDDLEWARE` list. It should appear early so that correlation context is available to all subsequent middleware and views.

```python
# settings.py

MIDDLEWARE = [
    "obskit.middleware.django.ObskitDjangoMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # ... your other middleware
]
```

### Optional OBSKIT configuration block

```python
# settings.py

OBSKIT = {
    "exclude_paths": ["/health/", "/metrics/", "/admin/"],
    "track_metrics": True,
    "track_logging": True,
    "track_tracing": True,
}
```

---

## ObskitDjangoMiddleware

### What it provides per request

| Feature | Details |
|---|---|
| Correlation ID | Reads `X-Correlation-ID` header or auto-generates a UUID4; sets `request.correlation_id` |
| Structured logging | Logs method, path, status code, and duration on request completion |
| RED metrics | Records `<service>_requests_total`, `<service>_errors_total`, `<service>_request_duration_seconds` |
| Distributed tracing | Extracts `traceparent` / `tracestate` from headers; creates a root OTel span |
| Response headers | Adds `X-Correlation-ID` and `X-Trace-Id` to every response |

---

## Accessing correlation ID in views

The middleware sets `request.correlation_id` on every request:

```python
# views.py
from django.http import JsonResponse
from obskit.correlation import get_correlation_id

def orders_view(request):
    # From the request attribute (recommended for views)
    cid = request.correlation_id

    # Or from obskit context vars (works in services / tasks too)
    cid = get_correlation_id()

    return JsonResponse({"correlation_id": cid})
```

---

## WSGI and ASGI support

obskit-django works transparently with both deployment modes:

```python
# wsgi.py (Gunicorn, uWSGI)
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

# asgi.py (Uvicorn, Daphne)
from django.core.asgi import get_asgi_application
application = get_asgi_application()
```

For ASGI deployments with Django Channels or Daphne, each request/response cycle is fully async-safe because obskit uses `contextvars.ContextVar` for all context storage.

---

## Custom error handling

Subclass `ObskitDjangoMiddleware` to extend error handling:

```python
# middleware.py
from obskit.middleware.django import ObskitDjangoMiddleware
from obskit.logging import get_logger

logger = get_logger(__name__)

class MyObskitMiddleware(ObskitDjangoMiddleware):
    def process_exception(self, request, exception):
        # Call the parent to record metrics and log
        response = super().process_exception(request, exception)

        # Additional alerting
        logger.error(
            "unhandled_exception",
            path=request.path,
            error=str(exception),
            error_type=type(exception).__name__,
        )
        return response
```

```python
# settings.py
MIDDLEWARE = [
    "myapp.middleware.MyObskitMiddleware",
    ...
]
```

---

## Health endpoint (Django view)

```python
# views.py
import asyncio
from django.http import JsonResponse
from obskit.health import get_health_checker
from obskit.health.checks import create_tcp_check

checker = get_health_checker()
checker.add_readiness_check(
    "postgres",
    create_tcp_check(host="postgres", port=5432),
)

def health(request):
    result = asyncio.run(checker.check_health())
    status = 200 if result.healthy else 503
    return JsonResponse(result.to_dict(), status=status)

def liveness(request):
    result = asyncio.run(checker.check_liveness())
    return JsonResponse(result.to_dict(), status=200 if result.healthy else 503)

def readiness(request):
    result = asyncio.run(checker.check_readiness())
    return JsonResponse(result.to_dict(), status=200 if result.healthy else 503)
```

```python
# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("health/", views.health),
    path("health/live/", views.liveness),
    path("health/ready/", views.readiness),
]
```

---

## Metrics endpoint (Django view)

```python
# views.py
from django.http import HttpResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

def metrics(request):
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
```

```python
# urls.py
path("metrics/", views.metrics),
```

---

## AppConfig integration

For Django applications using `AppConfig`, configure obskit in `ready()`:

```python
# apps.py
from django.apps import AppConfig

class OrdersConfig(AppConfig):
    name = "orders"

    def ready(self):
        from obskit.config import configure
        from obskit.tracing import setup_tracing

        configure(
            service_name="order-service",
            environment="production",
            version="2.0.0",
            otlp_endpoint="http://tempo:4317",
            trace_sample_rate=0.1,
        )
        setup_tracing(
            exporter_endpoint="http://tempo:4317",
            sample_rate=0.1,
            instrument=["django", "sqlalchemy"],
        )
```

---

## Full settings example

```python
# settings.py

from obskit.config import configure

configure(
    service_name="order-service",
    environment="production",
    version="2.0.0",
    otlp_endpoint="http://tempo:4317",
    trace_sample_rate=0.1,
    log_level="INFO",
    log_format="json",
    metrics_enabled=True,
    tracing_enabled=True,
)

MIDDLEWARE = [
    "obskit.middleware.django.ObskitDjangoMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

OBSKIT = {
    "exclude_paths": ["/health/", "/metrics/"],
    "track_metrics": True,
    "track_logging": True,
    "track_tracing": True,
}
```

---

## Kubernetes probe configuration

```yaml
livenessProbe:
  httpGet:
    path: /health/live/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 15

readinessProbe:
  httpGet:
    path: /health/ready/
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

---

## Settings reference

| Setting | Env var | Default | Effect |
|---|---|---|---|
| `service_name` | `OBSKIT_SERVICE_NAME` | `"unknown"` | RED metrics namespace and `service` log field |
| `log_level` | `OBSKIT_LOG_LEVEL` | `"INFO"` | Request log verbosity |
| `log_format` | `OBSKIT_LOG_FORMAT` | `"json"` | `json` (production) or `console` |
| `metrics_enabled` | `OBSKIT_METRICS_ENABLED` | `True` | Toggle metric collection |
| `tracing_enabled` | `OBSKIT_TRACING_ENABLED` | `True` | Toggle OTel span creation |
| `trace_sample_rate` | `OBSKIT_TRACE_SAMPLE_RATE` | `1.0` | Fraction of requests traced |
| `health_check_timeout` | `OBSKIT_HEALTH_CHECK_TIMEOUT` | `5.0` | Per-check timeout in seconds |
