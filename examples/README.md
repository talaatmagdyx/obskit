# obskit Examples

Production-ready examples demonstrating obskit's observability capabilities.

## Examples

### 1. Unified Observability for Microservices

**File:** `microservices_unified.py`

Demonstrates:
- Shared correlation IDs across services
- Distributed tracing with OpenTelemetry
- Unified RED metrics from all services
- Health checks with dependency tracking

```bash
# Run with Docker Compose
docker-compose up

# Access
API Gateway: http://localhost:8000
Jaeger UI:   http://localhost:16686
Grafana:     http://localhost:3000
Prometheus:  http://localhost:9093
```

### 2. RED, Golden Signals, and USE Methodologies

**File:** `red_golden_use_methodologies.py`

Demonstrates:
- **RED Method**: Rate, Errors, Duration for APIs
- **Golden Signals**: Latency, Traffic, Errors, Saturation
- **USE Method**: Utilization, Saturation, Errors for infrastructure

```bash
python examples/red_golden_use_methodologies.py
```

### 3. SLO Tracking with Error Budgets

**File:** `slo_tracking.py`

Demonstrates:
- Define SLOs (availability, latency)
- Track error budgets
- Generate Prometheus alerting rules
- Alertmanager integration

```bash
python examples/slo_tracking.py
```

### 4. Distributed Circuit Breaker

**File:** `distributed_circuit_breaker.py`

Demonstrates:
- Redis-backed distributed circuit breaker
- State sharing across multiple instances
- Fallback responses
- Multi-service orchestration

```bash
python examples/distributed_circuit_breaker.py
```

## Quick Start

```bash
# Install obskit with all extras
pip install obskit[all]

# Run any example
python examples/<example_file>.py

# View metrics
curl http://localhost:9090/metrics
```

## Use Cases

| Example | Best For |
|---------|----------|
| Microservices Unified | Teams building microservice architectures |
| RED/Golden/USE | Teams standardizing monitoring methodologies |
| SLO Tracking | Organizations with reliability targets |
| Distributed Circuit Breaker | Services needing resilience patterns |

## Requirements

```bash
pip install obskit[all]

# For distributed circuit breaker
pip install redis

# For examples with Docker
docker-compose up
```
