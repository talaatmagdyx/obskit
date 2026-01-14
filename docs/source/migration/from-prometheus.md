# Migrating from prometheus-client

This guide shows how to migrate from raw `prometheus-client` to obskit.

## Before: Raw prometheus-client

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Define metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=[.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0]
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Number of active HTTP requests'
)

def start_metrics_server():
    start_http_server(9090)

# In your application
def handle_request(method, endpoint):
    ACTIVE_REQUESTS.inc()
    start = time.time()
    
    try:
        result = process_request()
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status='200').inc()
        return result
    except Exception as e:
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status='500').inc()
        raise
    finally:
        ACTIVE_REQUESTS.dec()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(time.time() - start)
```

## After: obskit

```python
# main.py
from obskit import configure, get_red_metrics, start_http_server

# One-time configuration
configure(
    service_name="my-service",
    metrics_port=9090,
)

# Get pre-configured metrics
metrics = get_red_metrics()

# In your application
def handle_request(method, endpoint):
    with metrics.track_request(f"{method}_{endpoint}"):
        return process_request()
```

## Step-by-Step Migration

### Step 1: Install obskit

```bash
pip install obskit[metrics]
```

### Step 2: Replace metrics definitions

**Before:**
```python
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('requests_total', 'Total requests', ['operation', 'status'])
REQUEST_LATENCY = Histogram('request_latency', 'Request latency', ['operation'])
```

**After:**
```python
from obskit import configure, get_red_metrics

configure(service_name="my-service")
metrics = get_red_metrics()

# RED metrics (Rate, Errors, Duration) are pre-defined
# - requests_total
# - request_errors_total
# - request_duration_seconds
```

### Step 3: Update metric recording

**Before:**
```python
start_time = time.time()
try:
    result = do_work()
    REQUEST_COUNT.labels(operation="process", status="success").inc()
except Exception:
    REQUEST_COUNT.labels(operation="process", status="error").inc()
    raise
finally:
    REQUEST_LATENCY.labels(operation="process").observe(time.time() - start_time)
```

**After:**
```python
with metrics.track_request("process"):
    result = do_work()
# Automatically records:
# - Increments request counter
# - Records duration in histogram
# - Tracks errors if exception raised
```

### Step 4: Update custom gauges

**Before:**
```python
from prometheus_client import Gauge

QUEUE_SIZE = Gauge('queue_size', 'Current queue size')
QUEUE_SIZE.set(42)
```

**After:**
```python
from obskit.metrics import Gauge

queue_size = Gauge('queue_size', 'Current queue size')
queue_size.set(42)
```

### Step 5: Start metrics server

**Before:**
```python
from prometheus_client import start_http_server
start_http_server(9090)
```

**After:**
```python
from obskit import start_http_server
start_http_server(9090)
# Or set metrics_port in configure()
```

## Feature Mapping

| prometheus-client | obskit |
|------------------|--------|
| `Counter` | `obskit.metrics.Counter` |
| `Gauge` | `obskit.metrics.Gauge` |
| `Histogram` | `obskit.metrics.Histogram` |
| `Summary` | `obskit.metrics.Summary` |
| `start_http_server()` | `obskit.start_http_server()` |
| `REGISTRY` | `obskit.metrics.get_registry()` |
| Manual labels | Automatic with `track_request()` |

## Benefits After Migration

1. **Less code**: ~70% reduction in metric-related code
2. **Consistent naming**: Follows Prometheus naming conventions
3. **Pre-tuned histograms**: Optimized bucket configurations
4. **Automatic correlation**: Metrics tied to logs and traces
5. **Built-in best practices**: RED method, Golden Signals support

## Keeping Custom Metrics

You can still use custom prometheus-client metrics alongside obskit:

```python
from prometheus_client import Counter
from obskit import configure, get_red_metrics

configure(service_name="my-service")
metrics = get_red_metrics()

# Custom metric
CUSTOM_COUNTER = Counter('my_custom_metric', 'Description')

# Both work together
with metrics.track_request("operation"):
    CUSTOM_COUNTER.inc()
    do_work()
```

## Gradual Migration

For large codebases, migrate gradually:

1. **Week 1**: Install obskit, configure service
2. **Week 2**: Migrate new endpoints to use obskit
3. **Week 3**: Migrate existing endpoint metrics
4. **Week 4**: Remove old prometheus-client direct usage
5. **Week 5**: Clean up unused metrics

