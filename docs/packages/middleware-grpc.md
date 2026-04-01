# gRPC Middleware

gRPC server and client interceptors that bring full obskit observability to gRPC services: RED metrics, structured logging, distributed trace context propagation, correlation ID management, and error tracking mapped to gRPC status codes.

## Installation

```bash
pip install "obskit[grpc]"
```

---

## Overview

gRPC uses interceptors (the equivalent of HTTP middleware) to intercept calls before they reach the service handler. obskit provides two gRPC interceptors:

| Interceptor | Side | Use |
|---|---|---|
| `ObskitServerInterceptor` | Server | Add observability to every incoming RPC |
| `ObskitClientInterceptor` | Client | Propagate trace context and correlation IDs on outgoing calls |

Both support `grpc.aio` (async) only. For synchronous gRPC servers, wrap the handler with an async adapter or use Python's `grpc.server` thread-pool model — the interceptors will still be called on the thread-pool threads.

---

## ObskitServerInterceptor

### What it provides per RPC

| Feature | Details |
|---|---|
| Correlation ID | Reads `x-correlation-id` from gRPC metadata; auto-generates if absent |
| Structured logging | Logs RPC method name, status code, and duration |
| RED metrics | Records rate, errors, and duration labeled by RPC method name |
| Distributed tracing | Extracts `traceparent` from gRPC metadata; creates a span for each call |
| Error tracking | Maps non-OK gRPC status codes to `status="failure"` in metrics |

### Setup (grpc.aio server)

```python
import grpc
from grpc import aio
from obskit.integrations.grpc import ObskitServerInterceptor
from obskit.config import configure
from obskit.tracing import setup_tracing

configure(
    service_name="order-service",
    environment="production",
    otlp_endpoint="http://tempo:4317",
)

setup_tracing(
    exporter_endpoint="http://tempo:4317",
    instrument=["grpc_server"],
)

interceptor = ObskitServerInterceptor(
    service_name="order-service",   # defaults to ObskitSettings.service_name
    track_metrics=True,
    track_logging=True,
    track_tracing=True,
)

async def serve():
    server = aio.server(interceptors=[interceptor])
    # Add servicer and start as normal
    order_pb2_grpc.add_OrderServiceServicer_to_server(OrderServicer(), server)
    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `service_name` | `str \| None` | `None` | Service name for metrics; falls back to `ObskitSettings.service_name` |
| `track_metrics` | `bool` | `True` | Enable RED metrics per RPC |
| `track_logging` | `bool` | `True` | Emit structured log entry per RPC |
| `track_tracing` | `bool` | `True` | Create OTel span per RPC |

### Metric labels

RPC method names are extracted from the gRPC method path (`/package.Service/Method`) and mapped to a human-readable `operation` label:

```
# Example for /order.OrderService/CreateOrder
order_service_requests_total{operation="order.OrderService.CreateOrder", status="success"} 42
order_service_request_duration_seconds_bucket{operation="order.OrderService.CreateOrder", le="0.1"} 38
```

### Accessing correlation ID in servicers

```python
from obskit.correlation import get_correlation_id

class OrderServicer(order_pb2_grpc.OrderServiceServicer):
    async def CreateOrder(self, request, context):
        # Correlation ID is set in context vars by the interceptor
        cid = get_correlation_id()

        # Also available from gRPC metadata
        metadata = dict(context.invocation_metadata())
        cid_from_meta = metadata.get("x-correlation-id")

        return order_pb2.CreateOrderResponse(order_id="ord-123")
```

---

## ObskitClientInterceptor

Injects trace context and correlation IDs into outgoing gRPC calls so that downstream services can continue the trace chain.

```python
from obskit.integrations.grpc import ObskitClientInterceptor

interceptor = ObskitClientInterceptor(
    track_metrics=True,    # record RED metrics for outgoing calls
    propagate_trace=True,  # inject traceparent into outgoing metadata
)

channel = aio.insecure_channel(
    "order-service:50051",
    interceptors=[interceptor],
)
stub = order_pb2_grpc.OrderServiceStub(channel)
```

### What it injects into outgoing metadata

| Metadata key | Value | Purpose |
|---|---|---|
| `traceparent` | W3C trace context | Enables distributed tracing across services |
| `tracestate` | W3C trace state | Vendor-specific trace state |
| `x-correlation-id` | Current correlation ID | Correlates logs across services |

---

## gRPC status code mapping

| gRPC status | metrics `status` | Counted as |
|---|---|---|
| `OK` | `success` | Normal |
| `CANCELLED` | `failure` | Client cancelled |
| `DEADLINE_EXCEEDED` | `failure` | Timeout |
| `NOT_FOUND` | `failure` | Business logic error |
| `PERMISSION_DENIED` | `failure` | Auth error |
| `INTERNAL` | `failure` | Server error |
| Any non-OK | `failure` | Generic failure |

---

## OTel auto-instrumentation for gRPC

When `opentelemetry-instrumentation-grpc` is installed, `setup_tracing()` can auto-instrument gRPC at a lower level:

```bash
pip install opentelemetry-instrumentation-grpc
```

```python
from obskit.tracing import setup_tracing

setup_tracing(
    exporter_endpoint="http://tempo:4317",
    instrument=["grpc_server", "grpc_client"],
)
```

This patches the gRPC channel factory globally. Use the `ObskitServerInterceptor` alongside it for higher-level observability (metrics and logging) that OTel auto-instrumentation does not provide.

---

## Full server example

```python
import asyncio
import grpc
from grpc import aio
from obskit.config import configure
from obskit.tracing import setup_tracing
from obskit.integrations.grpc import ObskitServerInterceptor

# generated stubs
import order_pb2
import order_pb2_grpc

class OrderServicer(order_pb2_grpc.OrderServiceServicer):
    async def CreateOrder(self, request, context):
        return order_pb2.CreateOrderResponse(order_id="ord-123")

async def serve():
    configure(
        service_name="order-service",
        environment="production",
        otlp_endpoint="http://tempo:4317",
        trace_sample_rate=0.1,
    )
    setup_tracing(
        exporter_endpoint="http://tempo:4317",
        sample_rate=0.1,
        instrument=["grpc_server"],
    )

    interceptor = ObskitServerInterceptor(track_tracing=True)

    server = aio.server(interceptors=[interceptor])
    order_pb2_grpc.add_OrderServiceServicer_to_server(OrderServicer(), server)
    server.add_insecure_port("[::]:50051")

    await server.start()
    print("gRPC server listening on :50051")
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
```

---

## Full client example

```python
import asyncio
from grpc import aio
from obskit.config import configure
from obskit.tracing import setup_tracing, async_trace_span
from obskit.integrations.grpc import ObskitClientInterceptor
import order_pb2
import order_pb2_grpc

async def main():
    configure(service_name="api-gateway", environment="production")
    setup_tracing(instrument=["grpc_client"])

    interceptor = ObskitClientInterceptor(propagate_trace=True)

    async with aio.insecure_channel(
        "order-service:50051",
        interceptors=[interceptor],
    ) as channel:
        stub = order_pb2_grpc.OrderServiceStub(channel)

        async with async_trace_span("gateway.create_order"):
            response = await stub.CreateOrder(
                order_pb2.CreateOrderRequest(user_id="u-123", total=99.99)
            )
            print(f"Created: {response.order_id}")

asyncio.run(main())
```

---

## Kubernetes probe configuration

Expose a health endpoint alongside your gRPC service. One common pattern is to run a minimal HTTP server (e.g., a FastAPI app) on a separate port for Kubernetes probes:

```yaml
spec:
  containers:
    - name: order-service
      ports:
        - containerPort: 50051
          name: grpc
        - containerPort: 8000
          name: http
      livenessProbe:
        httpGet:
          path: /health/live
          port: http
        initialDelaySeconds: 10
        periodSeconds: 15
      readinessProbe:
        httpGet:
          path: /health/ready
          port: http
        initialDelaySeconds: 5
        periodSeconds: 10
```

---

## Settings reference

| Setting | Env var | Default | Effect |
|---|---|---|---|
| `service_name` | `OBSKIT_SERVICE_NAME` | `"unknown"` | RED metrics namespace |
| `log_level` | `OBSKIT_LOG_LEVEL` | `"INFO"` | RPC log verbosity |
| `log_format` | `OBSKIT_LOG_FORMAT` | `"json"` | Output format |
| `metrics_enabled` | `OBSKIT_METRICS_ENABLED` | `True` | Toggle metric collection |
| `tracing_enabled` | `OBSKIT_TRACING_ENABLED` | `True` | Toggle OTel span creation |
| `trace_sample_rate` | `OBSKIT_TRACE_SAMPLE_RATE` | `1.0` | Fraction of RPCs traced |
