# Architecture Overview

This document describes the internal architecture of obskit and how its components
work together to provide comprehensive observability.

## High-Level Architecture

```{mermaid}
flowchart TB
    subgraph Application["Your Application"]
        Code[Application Code]
        MW[Middleware]
    end
    
    subgraph obskit["obskit Package"]
        direction TB
        Config[Configuration]
        
        subgraph Core["Core"]
            Context[Context Manager]
            Types[Types & Enums]
        end
        
        subgraph Metrics["Metrics"]
            RED[RED Metrics]
            Golden[Golden Signals]
            USE[USE Metrics]
            Registry[Prometheus Registry]
        end
        
        subgraph Logging["Logging"]
            Logger[Structured Logger]
            PII[PII Redactor]
        end
        
        subgraph Tracing["Tracing"]
            Tracer[OpenTelemetry Tracer]
            Propagation[Context Propagation]
        end
        
        subgraph Health["Health"]
            Checker[Health Checker]
            Probes[Liveness/Readiness]
        end
        
        subgraph Resilience["Resilience"]
            CB[Circuit Breaker]
            Retry[Retry Logic]
            RL[Rate Limiter]
        end
    end
    
    subgraph Backends["Observability Backends"]
        Prometheus[(Prometheus)]
        Jaeger[(Jaeger/OTLP)]
        LogAgg[(Log Aggregator)]
    end
    
    Code --> MW
    MW --> Config
    Config --> Core
    Core --> Metrics
    Core --> Logging
    Core --> Tracing
    Core --> Health
    Core --> Resilience
    
    Metrics --> Prometheus
    Tracing --> Jaeger
    Logging --> LogAgg
```

## Component Responsibilities

### Configuration (`obskit.config`)

The configuration module provides centralized settings management:

- Environment variable loading via `pydantic-settings`
- Thread-safe singleton pattern
- Validation at startup

```python
from obskit.config import get_settings, ObskitSettings

settings = get_settings()
# or configure programmatically:
settings = ObskitSettings(
    service_name="my-service",
    log_level="INFO",
)
```

### Core (`obskit.core`)

Foundation components used across all modules:

- **Context**: Thread/async-safe correlation ID and tenant tracking
- **Types**: Shared type definitions and enums

### Metrics (`obskit.metrics`)

Prometheus-compatible metrics collection:

| Component | Purpose |
|-----------|---------|
| `REDMetrics` | Request rate, errors, duration |
| `GoldenSignals` | Latency, traffic, errors, saturation |
| `USEMetrics` | Utilization, saturation, errors |
| `Registry` | Prometheus metric registry management |

### Logging (`obskit.logging`)

Structured logging with context propagation:

- JSON-formatted output
- Automatic correlation ID injection
- Optional PII redaction

### Tracing (`obskit.tracing`)

OpenTelemetry-based distributed tracing:

- Span creation and management
- W3C Trace Context propagation
- OTLP export

### Health (`obskit.health`)

Kubernetes-style health checks:

- Liveness probes (is the app running?)
- Readiness probes (can it serve traffic?)

### Resilience (`obskit.resilience`)

Fault tolerance patterns:

- Circuit breakers (fail fast)
- Retry with backoff
- Rate limiting

## Data Flow

### Request Processing

```{mermaid}
sequenceDiagram
    participant Client
    participant MW as Middleware
    participant App as Application
    participant M as Metrics
    participant T as Tracing
    participant L as Logging
    
    Client->>MW: HTTP Request
    
    MW->>T: Extract/Create Trace Context
    MW->>L: Log Request Start
    MW->>M: Start Request Timer
    
    MW->>App: Forward Request
    App->>App: Business Logic
    App-->>MW: Response
    
    MW->>M: Record Duration & Status
    MW->>L: Log Request End
    MW->>T: End Span
    
    MW-->>Client: HTTP Response
```

### Correlation ID Propagation

```{mermaid}
flowchart LR
    subgraph Service_A["Service A"]
        A_MW[Middleware]
        A_Code[Handler]
        A_Log[Logger]
    end
    
    subgraph Service_B["Service B"]
        B_MW[Middleware]
        B_Code[Handler]
        B_Log[Logger]
    end
    
    Client -->|"Request"| A_MW
    A_MW -->|"Set correlation_id"| A_Code
    A_Code --> A_Log
    A_Log -->|"Log includes correlation_id"| Logs[(Logs)]
    
    A_Code -->|"X-Correlation-ID header"| B_MW
    B_MW -->|"Extract correlation_id"| B_Code
    B_Code --> B_Log
    B_Log -->|"Same correlation_id"| Logs
```

## Thread Safety

obskit uses several patterns to ensure thread safety:

### Singleton Pattern

Global instances use double-checked locking:

```python
_settings: ObskitSettings | None = None
_settings_lock = threading.Lock()

def get_settings() -> ObskitSettings:
    global _settings
    if _settings is None:
        with _settings_lock:
            if _settings is None:
                _settings = ObskitSettings()
    return _settings
```

### Context Variables

For async-safe context propagation:

```python
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

def get_correlation_id() -> str | None:
    return _correlation_id.get()

def set_correlation_id(value: str) -> None:
    _correlation_id.set(value)
```

## Extension Points

### Custom Metrics

```python
from prometheus_client import Counter
from obskit.metrics import get_registry

registry = get_registry()
custom_counter = Counter(
    "custom_events_total",
    "My custom events",
    registry=registry,
)
```

### Custom Log Processors

```python
from obskit import configure_logging

def my_processor(logger, method_name, event_dict):
    event_dict["custom_field"] = "value"
    return event_dict

logger = configure_logging(
    service_name="api",
    extra_processors=[my_processor],
)
```

### Custom Health Checks

```python
from obskit import get_health_checker

health = get_health_checker()
health.add_readiness_check("custom", my_check_function)
```

## Module Dependencies

```{mermaid}
flowchart BT
    Config[config]
    Core[core]
    Metrics[metrics]
    Logging[logging]
    Tracing[tracing]
    Health[health]
    Resilience[resilience]
    Middleware[middleware]
    SLO[slo]
    Alerts[alerts]
    
    Core --> Config
    Metrics --> Core
    Logging --> Core
    Tracing --> Core
    Health --> Core
    Resilience --> Core
    SLO --> Metrics
    Alerts --> SLO
    Middleware --> Metrics
    Middleware --> Tracing
    Middleware --> Logging
```

## Performance Considerations

### Metrics Overhead

- Counter increments: ~100ns
- Histogram observations: ~500ns
- With labels: add ~200ns per label

### Logging Overhead

- JSON serialization: ~1-5μs per log
- PII redaction: ~10-50μs depending on complexity

### Tracing Overhead

- Span creation: ~1-5μs
- Context propagation: ~100ns
- Export (batched): ~1ms per batch

## Next Steps

- **[Diagrams](diagrams.md)** - Detailed architecture diagrams
- **[Performance](../performance/index.md)** - Performance tuning guide
- **[Configuration](../config/index.md)** - All configuration options

