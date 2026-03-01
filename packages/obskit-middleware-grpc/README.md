<div align="center">

# 🔗 obskit-middleware-grpc

**gRPC server and client interceptors for automatic correlation IDs and distributed trace propagation**

---

[![PyPI](https://img.shields.io/pypi/v/obskit-middleware-grpc.svg?color=blue)](https://pypi.org/project/obskit-middleware-grpc/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![obskit](https://img.shields.io/badge/part%20of-obskit-blueviolet.svg)](https://github.com/talaatmagdyx/obskit)

</div>

## What it does

- **Server-side instrumentation** — `ObskitServerInterceptor` wraps every incoming RPC call with a structured log line, RED metrics, and correlation ID extraction from gRPC metadata, so the upstream trace context flows into your service automatically
- **Client-side propagation** — `ObskitClientInterceptor` injects the current correlation ID and W3C `traceparent` / `tracestate` into outgoing RPC metadata, ensuring that downstream gRPC services receive the full distributed trace context without any manual metadata management
- **All RPC patterns covered** — interceptors handle unary-unary, unary-stream, stream-unary, and stream-stream calls with a consistent observability contract across all four interaction patterns

---

## Installation

```bash
pip install obskit-middleware-grpc
```

The package depends only on `obskit-core` and `obskit-tracing`. gRPC itself (`grpcio`) must be installed separately since it is a large dependency that may already be present in your environment:

```bash
pip install grpcio grpcio-tools
```

For full tracing export to Tempo or Jaeger:

```bash
pip install "obskit-tracing[opentelemetry,grpc]"
```

---

## Quick Start

### Server

```python
import grpc
import grpc.aio
from concurrent import futures
from obskit.middleware.grpc import ObskitServerInterceptor

# your generated protobuf service
import orders_pb2_grpc


async def serve():
    interceptor = ObskitServerInterceptor()

    server = grpc.aio.server(interceptors=[interceptor])
    orders_pb2_grpc.add_OrderServiceServicer_to_server(OrderService(), server)
    server.add_insecure_port("[::]:50051")

    await server.start()
    await server.wait_for_termination()
```

### Client

```python
import grpc
import grpc.aio
from obskit.middleware.grpc import ObskitClientInterceptor

import orders_pb2
import orders_pb2_grpc


async def get_order(order_id: str):
    interceptor = ObskitClientInterceptor()

    channel = grpc.aio.insecure_channel(
        "order-service:50051",
        interceptors=[interceptor],
    )

    stub = orders_pb2_grpc.OrderServiceStub(channel)
    # correlation_id and traceparent are injected into metadata automatically
    response = await stub.GetOrder(orders_pb2.GetOrderRequest(order_id=order_id))
    return response
```

---

## Features

### ObskitServerInterceptor

The server interceptor runs before your servicer method and after it returns, recording the full RPC lifecycle:

```python
from obskit.middleware.grpc import ObskitServerInterceptor
from obskit.tracing import setup_tracing

setup_tracing(service_name="order-service", exporter_endpoint="http://tempo:4317")

interceptor = ObskitServerInterceptor(
    service_name="order-service",     # used as metric label
    track_metrics=True,               # RED metrics per RPC method
    track_logging=True,               # Structured log on start + completion
    track_tracing=True,               # OTel span per RPC
    excluded_methods=[
        "grpc.health.v1.Health/Check",  # exclude health checks
    ],
)

server = grpc.aio.server(interceptors=[interceptor])
```

For every non-excluded RPC call, the interceptor:

1. Extracts `x-correlation-id` from the incoming metadata and sets it in the request context
2. Logs `grpc_request_started` with the method name and correlation ID
3. Records a RED metric on completion with `operation`, `status`, and `error_type` labels
4. Logs `grpc_request_completed` with duration in milliseconds

```
{"event": "grpc_request_started",   "method": "/orders.OrderService/GetOrder", "operation": "orders.OrderService.GetOrder", "correlation_id": "a1b2-..."}
{"event": "grpc_request_completed", "method": "/orders.OrderService/GetOrder", "status": "success", "duration_ms": 2.14, "correlation_id": "a1b2-..."}
```

### ObskitClientInterceptor

The client interceptor runs before every outgoing RPC call, injecting observability context into the metadata:

```python
from obskit.middleware.grpc import ObskitClientInterceptor

interceptor = ObskitClientInterceptor(
    track_metrics=True,              # Record outgoing call latency
    track_logging=True,              # Log outgoing calls
    propagate_trace=True,            # Inject traceparent into metadata
    propagate_correlation_id=True,   # Inject x-correlation-id into metadata
)

channel = grpc.aio.insecure_channel("payment-service:50051", interceptors=[interceptor])
```

The injected metadata keys are:

| Metadata key | Source | Standard |
|---|---|---|
| `x-correlation-id` | `get_correlation_id()` from obskit context | obskit convention |
| `traceparent` | Active OTel span | W3C Trace Context |
| `tracestate` | Active OTel span | W3C Trace Context |

### Complete Server and Client Setup

A realistic order service that calls a payment service over gRPC, with full trace propagation on both sides:

```python
# order_service/main.py
import asyncio
import grpc
import grpc.aio
from obskit.middleware.grpc import ObskitServerInterceptor, ObskitClientInterceptor
from obskit.tracing import setup_tracing
from obskit.logging import get_logger

import orders_pb2
import orders_pb2_grpc
import payments_pb2
import payments_pb2_grpc

logger = get_logger(__name__)


class OrderService(orders_pb2_grpc.OrderServiceServicer):
    def __init__(self):
        # Client interceptor propagates correlation ID to payment service
        self._payment_interceptor = ObskitClientInterceptor()
        self._payment_channel = grpc.aio.insecure_channel(
            "payment-service:50052",
            interceptors=[self._payment_interceptor],
        )
        self._payment_stub = payments_pb2_grpc.PaymentServiceStub(self._payment_channel)

    async def CreateOrder(self, request, context):
        logger.info("order_creating", customer_id=request.customer_id, total=request.total)

        # correlation_id from server interceptor is in context —
        # the client interceptor will forward it to payment-service automatically
        charge_resp = await self._payment_stub.Charge(
            payments_pb2.ChargeRequest(
                customer_id=request.customer_id,
                amount=request.total,
            )
        )

        logger.info("order_created", payment_id=charge_resp.payment_id)
        return orders_pb2.Order(order_id="ord-456", status="confirmed")

    async def GetOrder(self, request, context):
        logger.info("order_fetch", order_id=request.order_id)
        return orders_pb2.Order(order_id=request.order_id, status="confirmed")


async def serve():
    setup_tracing(service_name="order-service", exporter_endpoint="http://tempo:4317")

    server_interceptor = ObskitServerInterceptor(
        service_name="order-service",
        excluded_methods=["grpc.health.v1.Health/Check"],
    )

    server = grpc.aio.server(interceptors=[server_interceptor])
    orders_pb2_grpc.add_OrderServiceServicer_to_server(OrderService(), server)
    server.add_insecure_port("[::]:50051")

    print("order-service listening on :50051")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
```

### Excluding Health Check Methods

gRPC health checks should not pollute your operational metrics. Exclude them by their full method path:

```python
interceptor = ObskitServerInterceptor(
    excluded_methods=[
        "grpc.health.v1.Health/Check",   # standard gRPC health protocol
        "grpc.health.v1.Health/Watch",
    ],
)
```

### Selective Instrumentation

Each observability pillar can be disabled independently:

```python
# Metrics only — no logging, no trace export
server_interceptor = ObskitServerInterceptor(
    track_metrics=True,
    track_logging=False,
    track_tracing=False,
)

# Client: propagate context but don't add metrics overhead
client_interceptor = ObskitClientInterceptor(
    track_metrics=False,
    track_logging=False,
    propagate_trace=True,
    propagate_correlation_id=True,
)
```

---

## What Every Request Gets

| Signal | Detail | Where it goes |
|--------|--------|---------------|
| `x-correlation-id` extraction | Read from incoming metadata, set in context | obskit context + log fields |
| `grpc_request_started` log | method, operation, correlation_id | Loki / stdout |
| `grpc_request_completed` log | method, status, duration_ms, error_type | Loki / stdout |
| `requests_total` counter | `operation=orders.OrderService.GetOrder`, `status=success/failure` | Prometheus |
| `request_duration_seconds` histogram | Full latency distribution per RPC method | Prometheus |
| `traceparent` injection (client) | From active OTel span | Downstream gRPC metadata |
| `x-correlation-id` injection (client) | From obskit context | Downstream gRPC metadata |

---

## Configuration Reference

### ObskitServerInterceptor

```python
ObskitServerInterceptor(
    service_name=None,          # defaults to obskit settings.service_name
    track_metrics=True,
    track_logging=True,
    track_tracing=True,
    excluded_methods=[],        # list of full method paths to skip
)
```

### ObskitClientInterceptor

```python
ObskitClientInterceptor(
    track_metrics=True,
    track_logging=True,
    propagate_trace=True,
    propagate_correlation_id=True,
)
```

---

## 🧩 Part of the obskit family

`obskit-middleware-grpc` is part of the [obskit](https://github.com/talaatmagdyx/obskit) monorepo — a production-ready observability toolkit for Python microservices.

| Install only this package | Install everything |
|---|---|
| `pip install obskit-middleware-grpc` | `pip install "obskit[all]"` |
