<div align="center">

# 🎸 obskit-middleware-django

**Django middleware for automatic correlation IDs, RED metrics, and distributed tracing — add one line to MIDDLEWARE**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-middleware-django.svg?color=blue)](https://pypi.org/project/obskit-middleware-django/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Settings-driven configuration** — drop `"obskit.middleware.django.ObskitDjangoMiddleware"` into your `MIDDLEWARE` list and configure everything through the `OBSKIT` dict in `settings.py`; no code changes to views, models, or URL patterns required
- **First-class Django integration** — correlation IDs are set directly on `request.correlation_id`, operation names are derived from Django's URL resolver (using the url name or view name), and proxy IP headers (`X-Forwarded-For`, `X-Real-IP`) are handled correctly out of the box
- **Full compatibility** — works with Django REST Framework, class-based views, function-based views, async views, and the Django admin; the middleware uses Django's standard `__call__` protocol so it slots into any middleware ordering cleanly

---

## Installation

```bash
pip install obskit-middleware-django
```

To add distributed tracing export:

```bash
pip install "obskit-middleware-django" "obskit-tracing[opentelemetry,django]"
```

---

## Quick Start

In `settings.py`:

```python
MIDDLEWARE = [
    "obskit.middleware.django.ObskitDjangoMiddleware",  # add at the top
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

That's the entire setup. Every view now gets automatic instrumentation.

---

## Recommended Middleware Ordering

Position matters in Django's middleware stack. obskit should be **first** so that the correlation ID is available throughout the entire request lifecycle, including in other middleware:

```python
MIDDLEWARE = [
    # 1. obskit first — sets correlation_id on request before anything else runs
    "obskit.middleware.django.ObskitDjangoMiddleware",

    # 2. Django security middleware
    "django.middleware.security.SecurityMiddleware",

    # 3. Whitenoise (if used for static files)
    "whitenoise.middleware.WhiteNoiseMiddleware",

    # 4. Session, CSRF, auth — these can log with correlation IDs now
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

---

## Features

### Settings-Based Configuration

All obskit options live in a single `OBSKIT` dict in `settings.py`. No need to touch application code:

```python
# settings.py

OBSKIT = {
    "exclude_paths": [
        "/health/",
        "/ready/",
        "/live/",
        "/metrics/",
        "/__debug__/",   # Django Debug Toolbar
        "/static/",      # static files (if served by Django)
    ],
    "track_metrics": True,   # RED metrics for Prometheus
    "track_logging": True,   # Structured JSON access logs
    "track_tracing": True,   # OpenTelemetry trace propagation
}
```

### Accessing the Correlation ID in Views

The correlation ID is attached directly to the `request` object and also available through obskit's context API:

```python
from django.http import JsonResponse
from obskit.core.context import get_correlation_id
from obskit.logging import get_logger

logger = get_logger(__name__)


def create_order(request):
    # Available via request attribute (set by middleware)
    cid = request.correlation_id

    # Also available via obskit context (works in async views too)
    cid = get_correlation_id()

    logger.info(
        "order_creating",
        customer_id=request.POST.get("customer_id"),
        correlation_id=cid,
    )

    # Forward to downstream services
    import httpx
    resp = httpx.post(
        "http://payment-service/charge",
        json={"amount": float(request.POST.get("amount", 0))},
        headers={"X-Correlation-ID": cid},
    )

    return JsonResponse({"order_id": "ord-123", "status": "pending"})
```

### Django REST Framework Compatibility

`ObskitDjangoMiddleware` works transparently with DRF. The middleware runs before DRF's authentication and permission layers, so correlation IDs are present for all DRF log output:

```python
# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from obskit.logging import get_logger

logger = get_logger(__name__)


@api_view(["GET"])
def get_order(request, order_id: str):
    logger.info("order_fetch", order_id=order_id)
    # → {"event": "order_fetch", "order_id": "ord-892", "correlation_id": "..."}
    return Response({"order_id": order_id, "status": "confirmed"})


# viewsets.py
from rest_framework import viewsets
from rest_framework.response import Response


class OrderViewSet(viewsets.ViewSet):
    def list(self, request):
        # correlation_id on request automatically
        return Response({"orders": [], "correlation_id": request.correlation_id})

    def create(self, request):
        return Response({"order_id": "ord-456", "status": "pending"}, status=201)
```

### Django URL Names as Operation Labels

The middleware uses Django's URL resolver to derive operation names. Named URL patterns produce clean, stable metric labels rather than raw paths with variable segments:

```python
# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("orders/",              views.OrderListView.as_view(), name="order-list"),
    path("orders/<str:pk>/",     views.OrderDetailView.as_view(), name="order-detail"),
    path("orders/<str:pk>/pay/", views.OrderPayView.as_view(), name="order-pay"),
]

# Metric labels:
# GET /orders/ord-123/     → operation="order-detail"  (not "orders_ord-123_")
# POST /orders/ord-123/pay/ → operation="order-pay"
```

This means your Prometheus dashboards show `order-detail` instead of a high-cardinality path label.

### Async View Support

Django 4.1+ supports async views. `ObskitDjangoMiddleware` is a synchronous middleware (Django's standard), so it works correctly with async views through Django's automatic sync-to-async wrapping:

```python
import asyncio
from django.http import JsonResponse
from obskit.core.context import get_correlation_id
from obskit.logging import get_logger

logger = get_logger(__name__)


async def get_order_async(request, order_id: str):
    # correlation_id is available — it was set synchronously before the view ran
    cid = get_correlation_id()
    logger.info("async_order_fetch", order_id=order_id, correlation_id=cid)

    await asyncio.sleep(0)  # simulate async I/O

    return JsonResponse({"order_id": order_id, "status": "confirmed"})
```

### Excluding Paths

Kubernetes probes and Prometheus scrapes must be excluded so they do not inflate request counts or contaminate latency percentiles:

```python
OBSKIT = {
    "exclude_paths": [
        "/health/",
        "/ready/",
        "/live/",
        "/metrics/",
    ],
}
```

Note: Django paths typically end with `/` (Django's `APPEND_SLASH` default). Match the style your URLs actually use.

### Custom Exception Handling

Subclass `ObskitDjangoMiddleware` to add custom error handling while keeping automatic instrumentation:

```python
from obskit.middleware.django import ObskitDjangoMiddleware
from obskit.logging import get_logger

logger = get_logger(__name__)


class AppMiddleware(ObskitDjangoMiddleware):
    def process_exception(self, request, exception):
        # obskit has already recorded the error metric
        # Add your own alerting or custom handling here
        if isinstance(exception, PaymentGatewayError):
            logger.error(
                "payment_gateway_failure",
                error=str(exception),
                order_id=getattr(request, "order_id", None),
            )
```

In `settings.py`:

```python
MIDDLEWARE = [
    "myapp.middleware.AppMiddleware",  # your subclass instead
    ...
]
```

---

## What Every Request Gets

| Signal | Detail | Where it goes |
|--------|--------|---------------|
| `X-Correlation-ID` header | Generated UUID or forwarded from client | Response header + `request.correlation_id` |
| `request_started` log | method, path, operation, client_ip, user_id | Loki / stdout |
| `request_completed` log | status_code, duration_ms, correlation_id | Loki / stdout |
| `requests_total` counter | Labeled with URL name as operation | Prometheus |
| `request_duration_seconds` histogram | Full latency distribution | Prometheus |
| `traceparent` propagation | Extracted from META headers | Distributed trace graph |
| Error log on unhandled exception | error, error_type, duration_ms | Loki / stdout |

---

## Configuration Reference

```python
# settings.py
OBSKIT = {
    "exclude_paths": ["/health/", "/ready/", "/live/", "/metrics/"],  # default
    "track_metrics": True,   # default
    "track_logging": True,   # default
    "track_tracing": True,   # default
}
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `exclude_paths` | `list[str]` | `["/health/", "/ready/", "/live/", "/metrics/"]` | Path prefixes excluded from instrumentation |
| `track_metrics` | `bool` | `True` | Record RED metrics in Prometheus |
| `track_logging` | `bool` | `True` | Emit structured JSON access logs |
| `track_tracing` | `bool` | `True` | Extract and propagate OTel trace context |

---

## Complete Example: Order Service

```python
# settings.py
from obskit.tracing import setup_tracing

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "orders",
]

MIDDLEWARE = [
    "obskit.middleware.django.ObskitDjangoMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

OBSKIT = {
    "exclude_paths": ["/health/", "/metrics/"],
    "track_metrics": True,
    "track_logging": True,
    "track_tracing": True,
}

# Initialize tracing at settings load time
setup_tracing(service_name="order-service", exporter_endpoint="http://tempo:4317")
```

```python
# orders/views.py
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from obskit.logging import get_logger
from obskit.metrics import start_http_server

logger = get_logger(__name__)
start_http_server(9090)


def health(request):
    return JsonResponse({"status": "ok"})  # excluded, not instrumented


@api_view(["GET"])
def get_order(request, order_id: str):
    logger.info("order_fetch", order_id=order_id)
    return Response({"order_id": order_id, "status": "confirmed"})


@api_view(["POST"])
def create_order(request):
    logger.info("order_creating", customer_id=request.data.get("customer_id"))
    return Response({"order_id": "ord-789", "status": "pending"}, status=201)
```

---

## 🧩 Part of the obskit family

`obskit-middleware-django` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-middleware-django` | `pip install "obskit[all]"` |
