# Installation

obskit is a **single package** with optional extras. The core package always installs the essentials (structured logging, config, types), and you add integrations only when you need them. This keeps your Docker images lean and your dependency graph clean.

---

## System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.11 | 3.12+ |
| pip | 23.0 | latest |
| OS | Linux, macOS, Windows | Linux (production) |

!!! warning "Python 3.10 and below are not supported"
    obskit uses `tomllib` (stdlib in 3.11), `ExceptionGroup` syntax, and `typing` features that require Python 3.11 or later. If you are on 3.10, stay on obskit v1.x until you can upgrade your runtime.

---

## Installing obskit

### Core Package

The bare install includes the always-on essentials: `structlog`, `PyYAML`, and `pydantic-settings`. It is enough to get structured logging, health checks, and configuration out of the box.

```bash
pip install obskit
```

### Installing with Extras

Add one or more extras to unlock heavier integrations. Only the dependencies you request are pulled in.

| Extra | What it adds | Install |
|-------|-------------|---------|
| `prometheus` | `prometheus-client` | `pip install "obskit[prometheus]"` |
| `otlp` | `opentelemetry-api`, `opentelemetry-sdk`, OTLP exporter | `pip install "obskit[otlp]"` |
| `loguru` | Loguru adapter for obskit logging | `pip install "obskit[loguru]"` |
| `fastapi` | `fastapi`, `starlette` middleware | `pip install "obskit[fastapi]"` |
| `flask` | `flask`, `werkzeug` middleware | `pip install "obskit[flask]"` |
| `django` | `django` middleware | `pip install "obskit[django]"` |
| `sqlalchemy` | SQLAlchemy 2.0 query tracking | `pip install "obskit[sqlalchemy]"` |
| `kafka` | `kafka-python` instrumentation | `pip install "obskit[kafka]"` |
| `rabbitmq` | `pika` instrumentation | `pip install "obskit[rabbitmq]"` |
| `redis` | `redis` instrumentation | `pip install "obskit[redis]"` |
| `httpx` | `httpx` instrumentation | `pip install "obskit[httpx]"` |
| `all` | Every extra above | `pip install "obskit[all]"` |

Multiple extras can be combined in a single install command by separating them with commas.

### Typical Microservice Examples

=== "FastAPI service"

    ```bash
    # Structured logging + Prometheus metrics + OTel tracing + FastAPI middleware
    pip install "obskit[prometheus,otlp,fastapi]"
    ```

=== "Flask service"

    ```bash
    pip install "obskit[prometheus,otlp,flask]"
    ```

=== "Django service"

    ```bash
    pip install "obskit[prometheus,otlp,django,sqlalchemy]"
    ```

=== "Background worker (Kafka)"

    ```bash
    pip install "obskit[prometheus,otlp,kafka]"
    ```

=== "Full install"

    ```bash
    # Everything — every extra included
    pip install "obskit[all]"
    ```

---

## Docker

### Minimal Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose application and Prometheus metrics ports
EXPOSE 8000 9090

ENV OBSKIT_SERVICE_NAME=order-service \
    OBSKIT_ENVIRONMENT=production \
    OBSKIT_LOG_FORMAT=json \
    OBSKIT_LOG_LEVEL=INFO

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Example `requirements.txt`

```text
"obskit[prometheus,otlp,fastapi]==2.2.0"
fastapi==0.115.0
uvicorn[standard]==0.30.0
```

!!! tip "Pin exact versions in production"
    Use `pip-compile` (from `pip-tools`) or `uv lock` to generate a fully-resolved lockfile. Pinning obskit to `==2.2.0` prevents accidental upgrades from breaking your observability config.

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

## Smoke Test

After installing, verify that the package is wired up correctly:

```bash
python -c "import obskit.logging; print('obskit.logging OK')"
python -c "import obskit.metrics; print('obskit.metrics OK')"
python -c "import obskit.tracing; print('obskit.tracing OK')"
python -c "import obskit.health; print('obskit.health OK')"
```

### Full Diagnostic Report

The built-in diagnostic tool inspects the installed obskit package, checks that environment variables are set, validates connectivity to your OTLP endpoint, and prints a structured report.

```bash
python -m obskit.core.diagnose
```

Expected output (all extras installed, OTLP reachable):

```
obskit v2.2.0 — Diagnostic Report
══════════════════════════════════════════════════════════════
  Component          Status
  ─────────────────────────────────────────────────────────
  obskit             2.2.0     OK
  prometheus         OK
  otlp               OK
  fastapi            OK
  sqlalchemy         OK

  Environment
  ─────────────────────────────────────────────────────────
  OBSKIT_SERVICE_NAME    order-service
  OBSKIT_ENVIRONMENT     production
  OBSKIT_OTLP_ENDPOINT   http://tempo:4317   (reachable)
  OBSKIT_LOG_LEVEL       INFO
  OBSKIT_LOG_FORMAT      json

══════════════════════════════════════════════════════════════
  All checks passed.
```

!!! note "Extra not available?"
    If a component shows `NOT INSTALLED`, install the corresponding extra. For example, `pip install "obskit[prometheus]"` for Prometheus support. Install everything with `pip install "obskit[all]"`.

---

## Development Install from Source

If you want to contribute or test unreleased changes, clone the repository and install in editable mode.

```bash
# 1. Clone the repository
git clone https://github.com/talaatmagdyx/obskit.git
cd obskit

# 2. Create an isolated virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows PowerShell

# 3a. Install all extras in editable mode (pip)
pip install -e ".[all]"

# 3b. Or use uv (faster)
uv sync --all-extras

# 4. Install pre-commit hooks
pre-commit install

# 5. Run the full test suite
pytest tests/unit/ -x --tb=short
```

### Running Docs Locally

```bash
pip install mkdocs-material mkdocstrings[python]
mkdocs serve
# → http://localhost:8000
```

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
OBSKIT_VERSION=2.2.0

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
OBSKIT_VERSION=2.2.0

OBSKIT_OTLP_ENDPOINT=http://otel-collector.monitoring.svc.cluster.local:4317
OBSKIT_OTLP_INSECURE=false
OBSKIT_TRACE_SAMPLE_RATE=0.1

OBSKIT_LOG_LEVEL=INFO
OBSKIT_LOG_FORMAT=json

OBSKIT_METRICS_PORT=9090
```

---

## Upgrade from v1

If you are upgrading an existing v1 project, see the [Migration Guide](migration.md) for a complete step-by-step walkthrough including import mapping, configuration changes, and a rollback strategy.

---

## Next Steps

- [Quick Start](quickstart.md) — up and running in 5 minutes
- [Your First Observable App](first-app.md) — a full FastAPI Order Service tutorial
- [Configuration Reference](../reference/configuration.md) — every `OBSKIT_*` variable documented
