# Installation

obskit v2.0.0 is a **monorepo of namespace packages** — every package lives under the `obskit.*` Python namespace (PEP 420) and is installed independently. You pull in only what your service actually uses, which keeps your Docker image lean and your dependency graph clean.

---

## System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.11 | 3.12+ |
| pip | 23.0 | latest |
| OS | Linux, macOS, Windows | Linux (production) |

!!! warning "Python 3.10 and below are not supported"
    obskit v2 uses `tomllib` (stdlib in 3.11), `ExceptionGroup` syntax, and `typing` features that require Python 3.11 or later. If you are on 3.10, stay on obskit v1.x until you can upgrade your runtime.

---

## Installing Packages

### Focused Installs (Recommended)

Install only the packages your service needs. This is the preferred approach — it minimises transitive dependencies, speeds up CI, and keeps production images small.

=== "Logging only"

    ```bash
    pip install obskit-logging
    ```

=== "Metrics only"

    ```bash
    pip install obskit-metrics
    ```

=== "Tracing only"

    ```bash
    pip install obskit-tracing
    ```

=== "Health checks only"

    ```bash
    pip install obskit-health
    ```

=== "Typical microservice"

    ```bash
    # The combination used by most FastAPI/Flask services
    pip install \
      obskit-core \
      obskit-logging \
      obskit-metrics \
      obskit-tracing \
      obskit-health \
      obskit-middleware-fastapi
    ```

=== "All packages"

    ```bash
    # Convenience meta-package — installs every obskit-* package
    pip install "obskit[all]"
    ```

### Package Catalogue

| Package | What it provides | Key extras |
|---------|-----------------|------------|
| `obskit-core` | Context propagation, config, types, `obskit.core.diagnose` | — |
| `obskit-logging` | Structured JSON logger with trace correlation | `loguru`, `structlog` |
| `obskit-metrics` | RED / Golden / USE metrics, exemplars, cardinality guard | `prometheus` |
| `obskit-tracing` | OpenTelemetry tracing, auto-instrumentation | `opentelemetry`, `auto` |
| `obskit-health` | Liveness / readiness / health checks + tracing | — |
| `obskit-resilience` | Circuit breaker, retry, rate limiter, bulkhead | — |
| `obskit-slo` | Error-budget tracking, burn-rate alerts | — |
| `obskit-middleware-fastapi` | FastAPI `ObskitMiddleware` (metrics + logging + tracing) | — |
| `obskit-middleware-flask` | Flask `ObskitMiddleware` | — |
| `obskit-middleware-django` | Django `ObskitMiddleware` | — |
| `obskit-middleware-grpc` | gRPC interceptors | — |
| `obskit-db` | SQLAlchemy query tracking + analyzer | `sqlalchemy` |
| `obskit-queue` | Kafka / RabbitMQ observability | `kafka`, `rabbitmq` |
| `obskit-dashboards` | Grafana dashboard JSON generation | — |

---

## Optional Extras

Some packages ship optional dependency groups that activate heavier integrations.

```bash
# OpenTelemetry SDK only (no auto-instrumentors)
pip install "obskit-tracing[opentelemetry]"

# OTel SDK + ALL auto-instrumentors (FastAPI, SQLAlchemy, Redis, httpx, Celery …)
pip install "obskit-tracing[auto]"

# prometheus-client (included by default but pinnable)
pip install "obskit-metrics[prometheus]"

# Loguru adapter for obskit-logging
pip install "obskit-logging[loguru]"

# Structlog adapter for obskit-logging
pip install "obskit-logging[structlog]"

# SQLAlchemy integration in obskit-db
pip install "obskit-db[sqlalchemy]"
```

!!! tip "Use `[auto]` in development, `[opentelemetry]` in production"
    The `[auto]` extra auto-patches every detected library on import. It is great for local exploration but adds startup latency. In production, list explicit instrumentors in `setup_tracing(instrument=[...])` and use `[opentelemetry]`.

---

## Meta-Package: `obskit`

The bare `obskit` package is a **meta-package** — it declares all sub-packages as dependencies so a single install gets everything.

```bash
# Install everything (equivalent to obskit[all])
pip install obskit

# Install with a specific feature set
pip install "obskit[all]"
```

---

## Verifying the Installation

### Quick Smoke Test

```bash
python -c "import obskit.logging; print('obskit-logging OK')"
python -c "import obskit.metrics; print('obskit-metrics OK')"
python -c "import obskit.tracing; print('obskit-tracing OK')"
python -c "import obskit.health; print('obskit-health OK')"
```

### Full Diagnostic Report

The built-in diagnostic tool inspects every installed obskit package, checks that environment variables are set, validates connectivity to your OTLP endpoint, and prints a structured report.

```bash
python -m obskit.core.diagnose
```

Expected output (all packages installed, OTLP reachable):

```
obskit v2.0.0 — Diagnostic Report
══════════════════════════════════════════════════════════════
  Package            Version   Status
  ─────────────────────────────────────────────────────────
  obskit-core        2.0.0     OK
  obskit-logging     2.0.0     OK
  obskit-metrics     2.0.0     OK
  obskit-tracing     2.0.0     OK
  obskit-health      2.0.0     OK
  obskit-resilience  2.0.0     OK
  obskit-slo         2.0.0     OK

  Environment
  ─────────────────────────────────────────────────────────
  OBSKIT_SERVICE_NAME    order-service
  OBSKIT_ENVIRONMENT     production
  OBSKIT_OTLP_ENDPOINT   http://tempo:4317   (reachable)
  OBSKIT_LOG_LEVEL       INFO
  OBSKIT_LOG_FORMAT      json

  Auto-instrumentors detected: fastapi, sqlalchemy, redis, httpx
══════════════════════════════════════════════════════════════
  All checks passed.
```

!!! note "Package not found?"
    If a package shows `NOT INSTALLED`, run `pip install obskit-<name>` or install the full set with `pip install "obskit[all]"`.

---

## Environment Variables

obskit reads its configuration exclusively from environment variables (no config files required). All variables use the `OBSKIT_` prefix.

### Core / Service Identity

| Variable | Default | Description |
|----------|---------|-------------|
| `OBSKIT_SERVICE_NAME` | `"unknown"` | Service name injected into every log, span, and metric label |
| `OBSKIT_ENVIRONMENT` | `"development"` | Deployment environment (`production`, `staging`, `development`) |
| `OBSKIT_VERSION` | `"0.0.0"` | Service version — set from your CI/CD pipeline |

### Tracing

| Variable | Default | Description |
|----------|---------|-------------|
| `OBSKIT_TRACING_ENABLED` | `true` | Toggle distributed tracing on/off |
| `OBSKIT_OTLP_ENDPOINT` | `"http://localhost:4317"` | OTLP/gRPC collector endpoint (Grafana Tempo, Jaeger, etc.) |
| `OBSKIT_OTLP_INSECURE` | `true` | Use plaintext gRPC (set `false` in production with TLS) |
| `OBSKIT_TRACE_SAMPLE_RATE` | `1.0` | Fraction of traces to keep (`0.1` = 10 %; `1.0` = 100 %) |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `OBSKIT_LOG_LEVEL` | `"INFO"` | Minimum log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `OBSKIT_LOG_FORMAT` | `"json"` | Output format: `json` for production, `console` for local dev |
| `OBSKIT_LOG_INCLUDE_TIMESTAMP` | `true` | Include ISO-8601 timestamp in every record |

### Metrics

| Variable | Default | Description |
|----------|---------|-------------|
| `OBSKIT_METRICS_ENABLED` | `true` | Toggle Prometheus metrics on/off |
| `OBSKIT_METRICS_PORT` | `9090` | Port for the standalone `/metrics` HTTP server |
| `OBSKIT_METRICS_PATH` | `"/metrics"` | Path for Prometheus scrape endpoint |

### Health Checks

| Variable | Default | Description |
|----------|---------|-------------|
| `OBSKIT_HEALTH_CHECK_TIMEOUT` | `5.0` | Per-check timeout in seconds |

### Example `.env` file

```dotenv
# .env (local development)
OBSKIT_SERVICE_NAME=order-service
OBSKIT_ENVIRONMENT=development
OBSKIT_VERSION=2.0.0

OBSKIT_OTLP_ENDPOINT=http://localhost:4317
OBSKIT_TRACE_SAMPLE_RATE=1.0

OBSKIT_LOG_LEVEL=DEBUG
OBSKIT_LOG_FORMAT=console

OBSKIT_METRICS_PORT=9090
```

```dotenv
# .env.production
OBSKIT_SERVICE_NAME=order-service
OBSKIT_ENVIRONMENT=production
OBSKIT_VERSION=2.1.0

OBSKIT_OTLP_ENDPOINT=http://otel-collector.monitoring.svc.cluster.local:4317
OBSKIT_OTLP_INSECURE=false
OBSKIT_TRACE_SAMPLE_RATE=0.1

OBSKIT_LOG_LEVEL=INFO
OBSKIT_LOG_FORMAT=json

OBSKIT_METRICS_PORT=9090
```

---

## Docker

### Minimal Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install only the packages your service needs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose Prometheus metrics port
EXPOSE 8000 9090

ENV OBSKIT_SERVICE_NAME=order-service \
    OBSKIT_ENVIRONMENT=production \
    OBSKIT_LOG_FORMAT=json \
    OBSKIT_LOG_LEVEL=INFO

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Example `requirements.txt`

```text
obskit-core==2.0.0
obskit-logging==2.0.0
obskit-metrics==2.0.0
obskit-tracing==2.0.0
obskit-health==2.0.0
obskit-middleware-fastapi==2.0.0
fastapi==0.115.0
uvicorn[standard]==0.30.0
```

!!! tip "Pin exact versions in production"
    Use `pip-compile` (from `pip-tools`) or `uv lock` to generate a fully-resolved lockfile. Pinning obskit packages to `==2.0.0` prevents accidental upgrades from breaking your observability config.

### Multi-Stage Build (smaller image)

```dockerfile
# --- Build stage ---
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime stage ---
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .

ENV PYTHONUNBUFFERED=1 \
    OBSKIT_SERVICE_NAME=order-service \
    OBSKIT_LOG_FORMAT=json

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Development Install from Source

If you want to contribute or test unreleased changes, clone the monorepo and install packages in editable mode.

```bash
# 1. Clone the repository
git clone https://github.com/talaatmagdyx/obskit.git
cd obskit

# 2. Create an isolated virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows PowerShell

# 3. Install the development toolchain
pip install --upgrade pip hatch pre-commit

# 4. Install all packages in editable mode
pip install -e "packages/obskit-core[dev]"
pip install -e "packages/obskit-logging[dev]"
pip install -e "packages/obskit-metrics[dev]"
pip install -e "packages/obskit-tracing[dev]"
pip install -e "packages/obskit-health[dev]"
pip install -e "packages/obskit-resilience[dev]"
pip install -e "packages/obskit-slo[dev]"
pip install -e "packages/obskit-middleware-fastapi[dev]"
pip install -e "packages/obskit-middleware-flask[dev]"
pip install -e "packages/obskit-middleware-django[dev]"
pip install -e "packages/obskit-middleware-grpc[dev]"

# 5. Install pre-commit hooks
pre-commit install

# 6. Run the full test suite
pytest packages/ -x --tb=short
```

!!! note "Editable installs and namespace packages"
    Because obskit uses PEP 420 implicit namespace packages (no `__init__.py` at the `obskit/` root), editable installs work correctly across all packages sharing the `obskit.*` namespace. Each sub-directory provides its own slice of the namespace.

### Running Docs Locally

```bash
pip install mkdocs-material mkdocstrings[python]
mkdocs serve
# → http://localhost:8000
```

---

## Upgrade from v1

If you are upgrading an existing v1 project, see the [Migration Guide](migration.md) for a complete step-by-step walkthrough including import mapping, configuration changes, and a rollback strategy.

---

## Next Steps

- [Quick Start](quickstart.md) — up and running in 5 minutes
- [Your First Observable App](first-app.md) — a full FastAPI Order Service tutorial
- [Configuration Reference](../reference/configuration.md) — every `OBSKIT_*` variable documented
