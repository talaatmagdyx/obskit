# Configuration Reference

Complete reference for all obskit configuration options.

---

## Configuration Methods

### 1. Environment Variables (Recommended)

```bash
# All variables use OBSKIT_ prefix
export OBSKIT_SERVICE_NAME="order-service"
export OBSKIT_ENVIRONMENT="production"
export OBSKIT_LOG_LEVEL="INFO"
```

### 2. Programmatic Configuration

```python
from obskit import configure

configure(
    service_name="order-service",
    environment="production",
    log_level="INFO",
)
```

### 3. .env File

```bash
# .env file in project root
OBSKIT_SERVICE_NAME=order-service
OBSKIT_ENVIRONMENT=production
OBSKIT_LOG_LEVEL=INFO
```

**Priority:** Environment Variables > Programmatic > .env > Defaults

---

## Configuration Categories

### Service Identification

| Setting | Env Variable | Type | Default | Description |
|---------|--------------|------|---------|-------------|
| `service_name` | `OBSKIT_SERVICE_NAME` | str | "unknown" | Service name in logs/metrics |
| `environment` | `OBSKIT_ENVIRONMENT` | str | "development" | Deployment environment |
| `version` | `OBSKIT_VERSION` | str | "0.0.0" | Service version |

```python
configure(
    service_name="order-api",
    environment="production",
    version="1.2.3",
)
```

---

### Logging Configuration

| Setting | Env Variable | Type | Default | Description |
|---------|--------------|------|---------|-------------|
| `log_level` | `OBSKIT_LOG_LEVEL` | str | "INFO" | DEBUG/INFO/WARNING/ERROR |
| `log_format` | `OBSKIT_LOG_FORMAT` | str | "json" | "json" or "console" |
| `log_include_timestamp` | `OBSKIT_LOG_INCLUDE_TIMESTAMP` | bool | True | Include timestamps |
| `log_sample_rate` | `OBSKIT_LOG_SAMPLE_RATE` | float | 1.0 | 0.0-1.0 sampling rate |
| `logging_backend` | `OBSKIT_LOGGING_BACKEND` | str | "structlog" | "structlog" or "loguru" |

```python
configure(
    log_level="INFO",
    log_format="json",
    log_sample_rate=0.1,  # Sample 10% of logs
)
```

---

### Metrics Configuration

| Setting | Env Variable | Type | Default | Description |
|---------|--------------|------|---------|-------------|
| `metrics_enabled` | `OBSKIT_METRICS_ENABLED` | bool | True | Enable metrics |
| `metrics_port` | `OBSKIT_METRICS_PORT` | int | 9090 | Metrics server port |
| `metrics_path` | `OBSKIT_METRICS_PATH` | str | "/metrics" | Metrics endpoint path |
| `metrics_method` | `OBSKIT_METRICS_METHOD` | str | "red" | "red"/"golden"/"use"/"all" |
| `metrics_sample_rate` | `OBSKIT_METRICS_SAMPLE_RATE` | float | 1.0 | 0.0-1.0 sampling rate |
| `use_histogram` | `OBSKIT_USE_HISTOGRAM` | bool | True | Use Prometheus histograms |
| `use_summary` | `OBSKIT_USE_SUMMARY` | bool | False | Use Prometheus summaries |

```python
configure(
    metrics_enabled=True,
    metrics_port=9090,
    metrics_sample_rate=0.1,
)
```

---

### Tracing Configuration

| Setting | Env Variable | Type | Default | Description |
|---------|--------------|------|---------|-------------|
| `tracing_enabled` | `OBSKIT_TRACING_ENABLED` | bool | True | Enable tracing |
| `otlp_endpoint` | `OBSKIT_OTLP_ENDPOINT` | str | "http://localhost:4317" | OTLP collector |
| `otlp_insecure` | `OBSKIT_OTLP_INSECURE` | bool | True | Use insecure connection |
| `trace_sample_rate` | `OBSKIT_TRACE_SAMPLE_RATE` | float | 1.0 | 0.0-1.0 sampling rate |
| `trace_export_queue_size` | `OBSKIT_TRACE_EXPORT_QUEUE_SIZE` | int | 2048 | Export queue size |
| `trace_export_batch_size` | `OBSKIT_TRACE_EXPORT_BATCH_SIZE` | int | 512 | Export batch size |
| `trace_export_timeout` | `OBSKIT_TRACE_EXPORT_TIMEOUT` | float | 30.0 | Export timeout (seconds) |

```python
configure(
    tracing_enabled=True,
    otlp_endpoint="http://jaeger:4317",
    otlp_insecure=False,  # Use TLS in production
    trace_sample_rate=0.1,
)
```

---

### Security Configuration

| Setting | Env Variable | Type | Default | Description |
|---------|--------------|------|---------|-------------|
| `metrics_auth_enabled` | `OBSKIT_METRICS_AUTH_ENABLED` | bool | False | Enable metrics auth |
| `metrics_auth_token` | `OBSKIT_METRICS_AUTH_TOKEN` | str | "" | Bearer token |
| `metrics_rate_limit_enabled` | `OBSKIT_METRICS_RATE_LIMIT_ENABLED` | bool | False | Enable rate limiting |
| `metrics_rate_limit_requests` | `OBSKIT_METRICS_RATE_LIMIT_REQUESTS` | int | 60 | Requests per minute |

```python
configure(
    metrics_auth_enabled=True,
    metrics_auth_token=os.getenv("METRICS_AUTH_TOKEN"),
    metrics_rate_limit_enabled=True,
    metrics_rate_limit_requests=100,
)
```

---

### Health Check Configuration

| Setting | Env Variable | Type | Default | Description |
|---------|--------------|------|---------|-------------|
| `health_check_timeout` | `OBSKIT_HEALTH_CHECK_TIMEOUT` | float | 5.0 | Check timeout (seconds) |

```python
configure(
    health_check_timeout=5.0,
)
```

---

### Circuit Breaker Configuration

| Setting | Env Variable | Type | Default | Description |
|---------|--------------|------|---------|-------------|
| `circuit_breaker_failure_threshold` | `OBSKIT_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | int | 5 | Failures before open |
| `circuit_breaker_recovery_timeout` | `OBSKIT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | float | 30.0 | Recovery wait (seconds) |
| `circuit_breaker_half_open_requests` | `OBSKIT_CIRCUIT_BREAKER_HALF_OPEN_REQUESTS` | int | 3 | Test requests |

```python
configure(
    circuit_breaker_failure_threshold=10,
    circuit_breaker_recovery_timeout=60.0,
    circuit_breaker_half_open_requests=3,
)
```

---

### Retry Configuration

| Setting | Env Variable | Type | Default | Description |
|---------|--------------|------|---------|-------------|
| `retry_max_attempts` | `OBSKIT_RETRY_MAX_ATTEMPTS` | int | 3 | Max attempts |
| `retry_base_delay` | `OBSKIT_RETRY_BASE_DELAY` | float | 1.0 | Base delay (seconds) |
| `retry_max_delay` | `OBSKIT_RETRY_MAX_DELAY` | float | 60.0 | Max delay (seconds) |
| `retry_exponential_base` | `OBSKIT_RETRY_EXPONENTIAL_BASE` | float | 2.0 | Backoff multiplier |

```python
configure(
    retry_max_attempts=5,
    retry_base_delay=0.5,
    retry_max_delay=30.0,
)
```

---

### Rate Limiting Configuration

| Setting | Env Variable | Type | Default | Description |
|---------|--------------|------|---------|-------------|
| `rate_limit_requests` | `OBSKIT_RATE_LIMIT_REQUESTS` | int | 100 | Requests per window |
| `rate_limit_window_seconds` | `OBSKIT_RATE_LIMIT_WINDOW_SECONDS` | float | 60.0 | Window size (seconds) |

```python
configure(
    rate_limit_requests=100,
    rate_limit_window_seconds=60.0,
)
```

---

### Internal Configuration

| Setting | Env Variable | Type | Default | Description |
|---------|--------------|------|---------|-------------|
| `async_metric_queue_size` | `OBSKIT_ASYNC_METRIC_QUEUE_SIZE` | int | 10000 | Async queue size |
| `enable_self_metrics` | `OBSKIT_ENABLE_SELF_METRICS` | bool | True | Enable self-monitoring |

```python
configure(
    async_metric_queue_size=50000,
    enable_self_metrics=True,
)
```

---

## Complete Production Configuration

```python
from obskit import configure
import os

configure(
    # ==========================================================================
    # Service Identity
    # ==========================================================================
    service_name=os.getenv("SERVICE_NAME", "my-service"),
    environment="production",
    version=os.getenv("VERSION", "1.0.0"),
    
    # ==========================================================================
    # Security (REQUIRED)
    # ==========================================================================
    metrics_auth_enabled=True,
    metrics_auth_token=os.getenv("METRICS_AUTH_TOKEN"),
    metrics_rate_limit_enabled=True,
    metrics_rate_limit_requests=100,
    
    # ==========================================================================
    # Logging
    # ==========================================================================
    log_level="INFO",
    log_format="json",
    log_sample_rate=0.1,
    
    # ==========================================================================
    # Metrics
    # ==========================================================================
    metrics_enabled=True,
    metrics_port=9090,
    metrics_sample_rate=0.1,
    
    # ==========================================================================
    # Tracing
    # ==========================================================================
    tracing_enabled=True,
    otlp_endpoint=os.getenv("OTLP_ENDPOINT", "http://jaeger:4317"),
    otlp_insecure=False,
    trace_sample_rate=0.1,
    
    # ==========================================================================
    # Resilience
    # ==========================================================================
    circuit_breaker_failure_threshold=10,
    circuit_breaker_recovery_timeout=60.0,
    retry_max_attempts=3,
    
    # ==========================================================================
    # Self-Monitoring
    # ==========================================================================
    enable_self_metrics=True,
    async_metric_queue_size=10000,
)
```

---

## Validation

Validate your configuration:

```python
from obskit import validate_config

is_valid, errors = validate_config()
if not is_valid:
    for error in errors:
        print(f"Config error: {error}")
```

---

## Environment-Specific Examples

### Development

```bash
export OBSKIT_SERVICE_NAME="order-service"
export OBSKIT_ENVIRONMENT="development"
export OBSKIT_LOG_LEVEL="DEBUG"
export OBSKIT_LOG_FORMAT="console"
export OBSKIT_METRICS_AUTH_ENABLED="false"
```

### Staging

```bash
export OBSKIT_SERVICE_NAME="order-service"
export OBSKIT_ENVIRONMENT="staging"
export OBSKIT_LOG_LEVEL="INFO"
export OBSKIT_LOG_FORMAT="json"
export OBSKIT_METRICS_AUTH_ENABLED="true"
export OBSKIT_METRICS_AUTH_TOKEN="staging-token"
```

### Production

```bash
export OBSKIT_SERVICE_NAME="order-service"
export OBSKIT_ENVIRONMENT="production"
export OBSKIT_LOG_LEVEL="INFO"
export OBSKIT_LOG_FORMAT="json"
export OBSKIT_METRICS_AUTH_ENABLED="true"
export OBSKIT_METRICS_AUTH_TOKEN="$SECURE_TOKEN"
export OBSKIT_METRICS_RATE_LIMIT_ENABLED="true"
export OBSKIT_METRICS_SAMPLE_RATE="0.1"
export OBSKIT_LOG_SAMPLE_RATE="0.1"
export OBSKIT_TRACE_SAMPLE_RATE="0.1"
export OBSKIT_OTLP_INSECURE="false"
```
