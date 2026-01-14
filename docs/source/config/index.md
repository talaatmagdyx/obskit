# Configuration Reference

Complete reference for all obskit configuration options.

## Configuration Sources

obskit loads configuration from (in order of precedence):

1. **Programmatic** - Direct Python code
2. **Environment variables** - `OBSKIT_*` prefixed
3. **`.env` files** - Loaded automatically
4. **Defaults** - Built-in sensible defaults

## Environment Variables

### Core Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OBSKIT_SERVICE_NAME` | string | `"unknown"` | Service name for metrics/logs/traces |
| `OBSKIT_ENVIRONMENT` | string | `"development"` | Deployment environment |
| `OBSKIT_DEBUG` | bool | `false` | Enable debug mode |

### Logging

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OBSKIT_LOG_LEVEL` | string | `"INFO"` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `OBSKIT_LOG_FORMAT` | string | `"json"` | Log format (json, console) |
| `OBSKIT_LOG_SAMPLE_RATE` | float | `1.0` | Log sampling rate (0.0-1.0) |
| `OBSKIT_PII_REDACTION` | bool | `false` | Enable PII redaction in logs |

### Metrics

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OBSKIT_METRICS_ENABLED` | bool | `true` | Enable metrics collection |
| `OBSKIT_METRICS_PORT` | int | `9090` | Metrics HTTP server port |
| `OBSKIT_METRICS_PATH` | string | `"/metrics"` | Metrics endpoint path |
| `OBSKIT_METRICS_SAMPLE_RATE` | float | `1.0` | Metrics sampling rate |
| `OBSKIT_METRICS_AUTH_ENABLED` | bool | `false` | Enable metrics endpoint auth |
| `OBSKIT_METRICS_AUTH_TOKEN` | string | `None` | Bearer token for metrics auth |

### Tracing

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OBSKIT_TRACING_ENABLED` | bool | `true` | Enable distributed tracing |
| `OBSKIT_OTLP_ENDPOINT` | string | `None` | OTLP collector endpoint |
| `OBSKIT_TRACE_SAMPLE_RATE` | float | `1.0` | Trace sampling rate (0.0-1.0) |
| `OBSKIT_OTLP_RATE_LIMIT` | int | `None` | Max traces per second to export |

### Resilience

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OBSKIT_CIRCUIT_BREAKER_THRESHOLD` | int | `5` | Default failure threshold |
| `OBSKIT_CIRCUIT_BREAKER_TIMEOUT` | float | `30.0` | Default recovery timeout |
| `OBSKIT_RETRY_MAX_ATTEMPTS` | int | `3` | Default max retry attempts |
| `OBSKIT_RETRY_BASE_DELAY` | float | `1.0` | Default base delay seconds |

## Programmatic Configuration

```python
from obskit.config import ObskitSettings, configure

# Create settings object
settings = ObskitSettings(
    service_name="my-service",
    environment="production",
    log_level="INFO",
    log_format="json",
    metrics_enabled=True,
    metrics_port=9090,
    tracing_enabled=True,
    otlp_endpoint="http://jaeger:4317",
    trace_sample_rate=0.1,
)

# Apply settings
configure(settings)
```

## .env File

```bash
# .env
OBSKIT_SERVICE_NAME=my-service
OBSKIT_ENVIRONMENT=production
OBSKIT_LOG_LEVEL=INFO
OBSKIT_OTLP_ENDPOINT=http://jaeger:4317
OBSKIT_TRACE_SAMPLE_RATE=0.1
```

## Settings Class

```python
from pydantic_settings import BaseSettings

class ObskitSettings(BaseSettings):
    """obskit configuration settings."""
    
    # Core
    service_name: str = "unknown"
    environment: str = "development"
    debug: bool = False
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    log_sample_rate: float = 1.0
    pii_redaction: bool = False
    
    # Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    metrics_sample_rate: float = 1.0
    metrics_auth_enabled: bool = False
    metrics_auth_token: str | None = None
    
    # Tracing
    tracing_enabled: bool = True
    otlp_endpoint: str | None = None
    trace_sample_rate: float = 1.0
    otlp_rate_limit: int | None = None
    
    # Resilience
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 30.0
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0
    
    class Config:
        env_prefix = "OBSKIT_"
        env_file = ".env"
        env_file_encoding = "utf-8"
```

## Per-Component Configuration

### REDMetrics

```python
from obskit import get_red_metrics

metrics = get_red_metrics(
    service_name="my-service",
    duration_buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
    sample_rate=0.1,
)
```

### Circuit Breaker

```python
from obskit import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_max_calls=3,
)
```

### Rate Limiter

```python
from obskit.resilience import RateLimiter

limiter = RateLimiter(
    rate=100,    # requests per second
    burst=20,    # burst capacity
)
```

## Validation

```python
from obskit import validate_config

# Validate current configuration
errors = validate_config()

if errors:
    for error in errors:
        print(f"Config error: {error}")
```

## Runtime Reconfiguration

### Log Level

```python
from obskit.logging import set_log_level, get_log_level

# Get current level
current = get_log_level()  # "INFO"

# Change at runtime
set_log_level("DEBUG")
```

### Metrics Sampling

```python
# Cannot change after initialization
# Configure before first use
```

## Best Practices

### 1. Use Environment Variables in Production

```yaml
# kubernetes deployment
env:
  - name: OBSKIT_SERVICE_NAME
    value: "my-service"
  - name: OBSKIT_LOG_LEVEL
    valueFrom:
      configMapKeyRef:
        name: app-config
        key: log_level
```

### 2. Different Configs per Environment

```python
# config.py
import os

ENV = os.getenv("OBSKIT_ENVIRONMENT", "development")

CONFIGS = {
    "development": {
        "log_level": "DEBUG",
        "trace_sample_rate": 1.0,
    },
    "staging": {
        "log_level": "INFO",
        "trace_sample_rate": 0.5,
    },
    "production": {
        "log_level": "WARNING",
        "trace_sample_rate": 0.01,
    },
}

config = CONFIGS[ENV]
```

### 3. Secrets Management

```python
# Don't hardcode tokens
# Use environment variables or secret managers

import os
from obskit.config import ObskitSettings

settings = ObskitSettings(
    metrics_auth_token=os.getenv("METRICS_TOKEN"),
)
```

## Next Steps

- **[Troubleshooting](../troubleshooting/index.md)** - Common configuration issues
- **[Examples](../examples/fastapi.md)** - Complete configuration examples
- **[API Reference](../api/index.rst)** - Full settings documentation

