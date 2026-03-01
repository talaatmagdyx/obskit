"""
Example service demonstrating obskit usage.

Run with: python example_service.py
"""

import asyncio
import random
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from obskit import (
    configure,
    configure_logging,
    configure_tracing,
    get_logger,
    with_observability,
    with_red_metrics,
    correlation_context,
    get_golden_signals,
    register_slo,
    track_slo,
    SLOType,
    health_check,
    get_health_registry,
    circuit_breaker,
    retry,
    rate_limit,
)

# Configure obskit
configure(
    service_name="example-service",
    environment="development",
    metrics_method="all",
)

# configure_logging() reads from settings, no parameters needed
configure_logging()
configure_tracing()

logger = get_logger(__name__)

# Register SLOs
register_slo("api_availability", SLOType.AVAILABILITY, 0.99)
register_slo("api_latency_p99", SLOType.LATENCY, 0.5, percentile=99)


# Health checks
@health_check("service")
def check_service():
    return True, "Service is healthy"


# Example operations with observability
@with_observability(component="OrderService", operation="create_order", threshold_ms=100)
def create_order(order_id: str) -> dict:
    """Simulate order creation with random latency."""
    latency = random.uniform(0.01, 0.2)
    time.sleep(latency)
    
    # Simulate occasional failures
    if random.random() < 0.05:
        raise ValueError("Order validation failed")
    
    track_slo("api_availability", success=True)
    track_slo("api_latency_p99", value=latency)
    
    return {"order_id": order_id, "status": "created"}


@with_red_metrics(component="PaymentService")
@circuit_breaker("payment_gateway", failure_threshold=3, recovery_timeout=10)
@retry(max_attempts=2, base_delay=0.5)
def process_payment(payment_id: str) -> dict:
    """Simulate payment processing with resilience patterns."""
    latency = random.uniform(0.05, 0.3)
    time.sleep(latency)
    
    # Simulate failures
    if random.random() < 0.1:
        raise ConnectionError("Payment gateway timeout")
    
    return {"payment_id": payment_id, "status": "processed"}


@rate_limit("inventory_api", requests_per_second=5)
def check_inventory(product_id: str) -> dict:
    """Simulate inventory check with rate limiting."""
    return {"product_id": product_id, "available": random.randint(0, 100)}


# Prometheus metrics endpoint
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for metrics and health endpoints."""
    
    def do_GET(self):
        if self.path == "/metrics" and PROMETHEUS_AVAILABLE:
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(generate_latest())
        
        elif self.path == "/health":
            import json
            # Run health checks synchronously for simplicity
            registry = get_health_registry()
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(registry.check_health())
            loop.close()
            
            status_code = 200 if result.is_healthy else 503
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result.to_dict()).encode())
        
        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"obskit example service\n")
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass  # NOSONAR


def run_server():
    """Run the HTTP server."""
    server = HTTPServer(("0.0.0.0", 8000), MetricsHandler)
    logger.info("Starting server", port=8000)
    server.serve_forever()


def simulate_traffic():
    """Simulate traffic to generate metrics."""
    logger.info("Starting traffic simulation")
    
    while True:
        try:
            with correlation_context():
                # Simulate various operations
                order_id = f"order-{random.randint(1000, 9999)}"
                try:
                    create_order(order_id)
                except Exception as e:
                    logger.warning("Order creation failed", error=str(e))
                
                payment_id = f"pay-{random.randint(1000, 9999)}"
                try:
                    process_payment(payment_id)
                except Exception as e:
                    logger.warning("Payment processing failed", error=str(e))
                
                product_id = f"prod-{random.randint(100, 999)}"
                try:
                    check_inventory(product_id)
                except Exception as e:
                    logger.warning("Inventory check failed", error=str(e))
            
            # Update saturation metrics
            golden = get_golden_signals()
            golden.set_saturation("cpu", random.uniform(0.3, 0.8))
            golden.set_saturation("memory", random.uniform(0.4, 0.7))
            golden.set_queue_depth("order_queue", random.randint(0, 50))
            
        except Exception as e:
            logger.error("Traffic simulation error", error=str(e))
        
        time.sleep(random.uniform(0.1, 0.5))


if __name__ == "__main__":
    # Start server in a thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Run traffic simulation
    try:
        simulate_traffic()
    except KeyboardInterrupt:
        logger.info("Shutting down")

