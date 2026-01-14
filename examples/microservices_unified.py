"""
Example: Unified Observability for Microservices
================================================

This example shows how to set up unified observability across
multiple microservices using obskit.

Use Case:
- Multiple microservices (API Gateway, Order Service, Payment Service)
- Shared correlation IDs across services
- Unified metrics format
- Distributed tracing
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request

from obskit import (
    configure,
    extract_trace_context,
    get_health_checker,
    get_logger,
    get_red_metrics,
    inject_trace_context,
    start_http_server,
)
from obskit.core import get_correlation_id
from obskit.middleware import ObskitMiddleware
from obskit.tracing import configure_tracing

# =============================================================================
# Service Configuration (shared across all microservices)
# =============================================================================


def setup_observability(service_name: str, metrics_port: int = 9090) -> None:
    """
    Standard observability setup for any microservice.

    Call this at service startup to enable:
    - Structured logging with correlation IDs
    - RED metrics (Rate, Errors, Duration)
    - Distributed tracing
    - Health checks
    """
    # Configure obskit
    configure(
        service_name=service_name,
        environment="production",
        log_level="INFO",
        log_format="json",
    )

    # Configure tracing (sends to Jaeger/OTLP collector)
    configure_tracing(
        service_name=service_name,
        otlp_endpoint="http://jaeger:4317",
    )

    # Start metrics server
    start_http_server(port=metrics_port)

    print(f"✅ {service_name} observability initialized")
    print(f"   Metrics: http://localhost:{metrics_port}/metrics")


# =============================================================================
# API Gateway Service
# =============================================================================


def create_api_gateway() -> FastAPI:
    """API Gateway that routes to backend services."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_observability("api-gateway", metrics_port=9090)
        yield

    app = FastAPI(title="API Gateway", lifespan=lifespan)
    app.add_middleware(ObskitMiddleware)

    logger = get_logger("api-gateway")
    metrics = get_red_metrics()
    health = get_health_checker()

    # Health check for downstream services
    async def check_order_service() -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://order-service:8001/health", timeout=2.0)
                return resp.status_code == 200
        except Exception:
            return False

    health.add_readiness_check("order_service", check_order_service)

    @app.get("/api/orders/{order_id}")
    async def get_order(order_id: str, request: Request):
        """Forward request to Order Service with trace context."""
        correlation_id = get_correlation_id()

        # Validate order_id to prevent SSRF
        # Only allow alphanumeric, hyphens, and underscores
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', order_id):
            logger.warning(
                "invalid_order_id",
                order_id=order_id,
                correlation_id=correlation_id,
            )
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid order ID format")

        logger.info(
            "routing_request",
            order_id=order_id,
            target="order-service",
            correlation_id=correlation_id,
        )

        # Inject trace context for downstream service
        headers = inject_trace_context(
            {
                "X-Correlation-ID": correlation_id,
            }
        )

        # Use URL encoding to safely construct the URL
        from urllib.parse import quote
        safe_order_id = quote(order_id, safe='')
        
        async with httpx.AsyncClient() as client:
            with metrics.track_request("proxy_to_order_service"):
                response = await client.get(
                    f"http://order-service:8001/orders/{safe_order_id}",
                    headers=headers,
                )

        return response.json()

    @app.get("/health")
    async def health_check():
        return await health.check_health()

    return app


# =============================================================================
# Order Service
# =============================================================================


def create_order_service() -> FastAPI:
    """Order Service that processes orders."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_observability("order-service", metrics_port=9091)
        yield

    app = FastAPI(title="Order Service", lifespan=lifespan)
    app.add_middleware(ObskitMiddleware)

    logger = get_logger("order-service")
    metrics = get_red_metrics()

    @app.get("/orders/{order_id}")
    async def get_order(order_id: str, request: Request):
        """Get order details, calling Payment Service for status."""
        # Extract trace context from incoming request
        extract_trace_context(dict(request.headers))
        correlation_id = get_correlation_id()

        # Validate order_id to prevent SSRF
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', order_id):
            logger.warning(
                "invalid_order_id",
                order_id=order_id,
                correlation_id=correlation_id,
            )
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid order ID format")

        logger.info(
            "processing_order_request",
            order_id=order_id,
            correlation_id=correlation_id,
        )

        # Simulate database lookup
        with metrics.track_request("db_query"):
            await asyncio.sleep(0.01)  # Simulated DB call
            order = {
                "id": order_id,
                "customer": "customer-123",
                "total": 99.99,
            }

        # Call Payment Service for payment status
        headers = inject_trace_context(
            {
                "X-Correlation-ID": correlation_id,
            }
        )

        # Use URL encoding to safely construct the URL
        from urllib.parse import quote
        safe_order_id = quote(order_id, safe='')

        async with httpx.AsyncClient() as client:
            with metrics.track_request("call_payment_service"):
                payment_resp = await client.get(
                    f"http://payment-service:8002/payments/order/{safe_order_id}",
                    headers=headers,
                )

        order["payment_status"] = payment_resp.json().get("status", "unknown")

        logger.info(
            "order_retrieved",
            order_id=order_id,
            payment_status=order["payment_status"],
            correlation_id=correlation_id,
        )

        return order

    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app


# =============================================================================
# Payment Service
# =============================================================================


def create_payment_service() -> FastAPI:
    """Payment Service that handles payments."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_observability("payment-service", metrics_port=9092)
        yield

    app = FastAPI(title="Payment Service", lifespan=lifespan)
    app.add_middleware(ObskitMiddleware)

    logger = get_logger("payment-service")
    metrics = get_red_metrics()

    @app.get("/payments/order/{order_id}")
    async def get_payment_status(order_id: str, request: Request):
        """Get payment status for an order."""
        correlation_id = get_correlation_id()

        logger.info(
            "checking_payment_status",
            order_id=order_id,
            correlation_id=correlation_id,
        )

        # Simulate payment gateway call
        with metrics.track_request("payment_gateway"):
            await asyncio.sleep(0.005)

        return {
            "order_id": order_id,
            "status": "completed",
            "amount": 99.99,
        }

    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app


# =============================================================================
# Docker Compose Configuration
# =============================================================================

DOCKER_COMPOSE = """
# docker-compose.yml for microservices with unified observability

version: '3.8'

services:
  api-gateway:
    build: .
    command: uvicorn examples.microservices_unified:create_api_gateway --factory --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
      - "9090:9090"  # Metrics
    environment:
      - SERVICE_NAME=api-gateway
      - OTLP_ENDPOINT=http://jaeger:4317
    depends_on:
      - order-service
      - jaeger

  order-service:
    build: .
    command: uvicorn examples.microservices_unified:create_order_service --factory --host 0.0.0.0 --port 8001
    ports:
      - "8001:8001"
      - "9091:9091"
    environment:
      - SERVICE_NAME=order-service
      - OTLP_ENDPOINT=http://jaeger:4317
    depends_on:
      - payment-service
      - jaeger

  payment-service:
    build: .
    command: uvicorn examples.microservices_unified:create_payment_service --factory --host 0.0.0.0 --port 8002
    ports:
      - "8002:8002"
      - "9092:9092"
    environment:
      - SERVICE_NAME=payment-service
      - OTLP_ENDPOINT=http://jaeger:4317
    depends_on:
      - jaeger

  # Observability Stack
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9093:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC
    environment:
      - COLLECTOR_OTLP_ENABLED=true

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
"""

PROMETHEUS_CONFIG = """
# prometheus.yml - Scrape all microservices

global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'api-gateway'
    static_configs:
      - targets: ['api-gateway:9090']

  - job_name: 'order-service'
    static_configs:
      - targets: ['order-service:9091']

  - job_name: 'payment-service'
    static_configs:
      - targets: ['payment-service:9092']
"""


if __name__ == "__main__":
    print("Unified Observability Example")
    print("=" * 50)
    print("\nThis example demonstrates:")
    print("1. Shared correlation IDs across services")
    print("2. Distributed tracing with OpenTelemetry")
    print("3. Unified RED metrics from all services")
    print("4. Health checks with dependency tracking")
    print("\nTo run:")
    print("  docker-compose up")
    print("\nThen access:")
    print("  API Gateway: http://localhost:8000")
    print("  Jaeger UI:   http://localhost:16686")
    print("  Grafana:     http://localhost:3000")
    print("  Prometheus:  http://localhost:9093")
