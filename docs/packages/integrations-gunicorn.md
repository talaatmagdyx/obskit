# Gunicorn Integration

`ObskitGunicornConfig` is a base class for Gunicorn configuration files that automatically wires the Prometheus multiprocess registry so every worker contributes to the same `/metrics` endpoint — with zero boilerplate.

---

## Installation

```bash
pip install obskit
```

No extra dependencies are required. `ObskitGunicornConfig` defers its Prometheus imports so the class can be imported even when `prometheus-client` is not installed.

---

## Overview

When running a Gunicorn multi-worker application, Prometheus metrics must be aggregated across all worker processes. This requires two hooks in your Gunicorn config file:

| Hook | What it does |
|---|---|
| `on_starting(server)` | Initialises the shared `PROMETHEUS_MULTIPROC_DIR` before workers fork |
| `child_exit(server, worker)` | Removes the exiting worker's `.db` files so stale metrics are not scraped |

`ObskitGunicornConfig` implements both hooks. Inherit from it and your app gets correct multiprocess metrics automatically.

---

## Quick Start

### Minimal config

```python
# gunicorn.conf.py
from obskit.integrations.gunicorn import ObskitGunicornConfig

class Config(ObskitGunicornConfig):
    bind = "0.0.0.0:8000"
    workers = 4
    worker_class = "uvicorn.workers.UvicornWorker"
```

```bash
PROMETHEUS_MULTIPROC_DIR=/tmp/prom_multiproc \
gunicorn myapp:app -c gunicorn.conf.py
```

### With custom hooks

`ObskitGunicornConfig` hooks are regular methods, so you can extend them with `super()`:

```python
from obskit.integrations.gunicorn import ObskitGunicornConfig

class Config(ObskitGunicornConfig):
    bind = "0.0.0.0:8000"
    workers = 4

    def on_starting(self, server):
        super().on_starting(server)          # ← wires multiprocess registry
        print("Gunicorn is starting …")     # ← your custom logic

    def child_exit(self, server, worker):
        super().child_exit(server, worker)   # ← cleans up .db files
        print(f"Worker {worker.pid} exited")
```

---

## Environment variable requirement

Set `PROMETHEUS_MULTIPROC_DIR` to a writable directory before starting Gunicorn.  obskit validates that it exists; if it is missing, a warning is logged and metric exports will not work.

```bash
mkdir -p /tmp/prom_multiproc
export PROMETHEUS_MULTIPROC_DIR=/tmp/prom_multiproc
```

In Kubernetes, use an `emptyDir` volume:

```yaml
env:
  - name: PROMETHEUS_MULTIPROC_DIR
    value: /tmp/prom_multiproc
volumeMounts:
  - name: prom-multiproc
    mountPath: /tmp/prom_multiproc
volumes:
  - name: prom-multiproc
    emptyDir: {}
```

---

## FastAPI + Gunicorn example

```python
# gunicorn.conf.py
from obskit.integrations.gunicorn import ObskitGunicornConfig
from obskit import configure_observability

class Config(ObskitGunicornConfig):
    bind = "0.0.0.0:8000"
    workers = 4
    worker_class = "uvicorn.workers.UvicornWorker"

    def post_fork(self, server, worker):
        # Configure obskit in each worker after forking
        configure_observability(
            service_name="my-api",
            environment="production",
            version="2.0.0",
        )
```

```python
# app.py
from fastapi import FastAPI
from obskit import instrument_fastapi

app = FastAPI()
instrument_fastapi(app)

@app.get("/metrics")
async def metrics():
    from obskit.metrics.registry import generate_latest
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(generate_latest())
```

---

## API reference

### `ObskitGunicornConfig`

```python
from obskit.integrations.gunicorn import ObskitGunicornConfig
```

#### `on_starting(server)`

Called once in the master process before workers are forked.  Calls
`obskit.metrics.multiprocess.setup_multiprocess_registry()` to ensure
`PROMETHEUS_MULTIPROC_DIR` is initialised before any worker inherits the
process state.

#### `child_exit(server, worker)`

Called in the master process whenever a worker exits (normally or abnormally).
Calls `obskit.metrics.multiprocess.child_exit(server, worker)` to remove the
worker's per-process `.db` files from `PROMETHEUS_MULTIPROC_DIR`.

---

## Comparison: before and after

=== "Before (manual)"
    ```python
    # gunicorn.conf.py
    from prometheus_client import multiprocess, CollectorRegistry

    def on_starting(server):
        import os
        os.makedirs(os.environ.get("PROMETHEUS_MULTIPROC_DIR", "/tmp/prom"), exist_ok=True)

    def child_exit(server, worker):
        multiprocess.mark_process_dead(worker.pid)
    ```

=== "After (obskit)"
    ```python
    # gunicorn.conf.py
    from obskit.integrations.gunicorn import ObskitGunicornConfig

    class Config(ObskitGunicornConfig):
        bind = "0.0.0.0:8000"
        workers = 4
    ```
