# obskit — Claude Code Context

## Project Overview

**obskit** is a production-ready observability toolkit for Python microservices.
Version: 1.0.0 | License: MIT | Python: ≥3.11

Provides: structured logging, RED metrics, distributed tracing (OTel), health checks,
SLO tracking, PII redaction, and ASGI middleware — all
from a single package with optional extras.

---

## Commands

```bash
# Tests
make test               # unit tests + coverage (100% required)
make test-fast          # unit tests without coverage, parallel
make test-coverage      # full HTML + XML coverage report
make test-file FILE=tests/unit/metrics/test_red.py
make test-single TEST=tests/unit/metrics/test_red.py::TestREDMetrics::test_observe

# Quality
make lint               # ruff check + format --check
make typecheck          # mypy src/
uv run ruff format src/ tests/   # auto-format

# Docs
make docs               # mkdocs build --strict
make docs-serve         # mkdocs serve (http://127.0.0.1:8000)

# Direct invocations (when uv not in PATH)
.venv/bin/pytest tests/unit/ -q -n auto --dist=worksteal --no-cov
.venv/bin/pytest tests/unit/<pkg>/test_<module>.py -v
.venv/bin/pytest --co -q tests/unit/<pkg>/    # list tests only
python -m mypy src/obskit/ --config-file pyproject.toml --no-incremental
```

---

## Package Map

```
src/obskit/
  core/           context.py (correlation ID), shutdown.py,
                  observability.py (Observability facade),
                  observability_config.py (ObservabilityConfig dataclasses),
                  deprecation.py (deprecation utilities)
  logging/        factory.py, logger.py, redaction.py, sampling.py,
                  trace_correlation.py, dynamic.py, async_ring.py
                  adapters/   (structlog processors)
  metrics/        red.py, types.py, registry.py, cardinality.py,
                  golden.py, tenant.py, multiprocess.py, otlp.py,
                  presets.py, statsd_emitter.py, threadsafe_aggregator.py,
                  exemplar.py, openmetrics.py, pushgateway.py,
                  async_recording.py, auth.py, self_metrics.py, use.py
  tracing/        tracer.py, setup.py, auto.py
  health/         checker.py, checks.py, router.py, aggregator.py,
                  server.py, slo_check.py
                  adaptive.py, combined.py, distributed.py, factory.py
  middleware/     fastapi.py, flask.py, django.py,
                  core.py (MiddlewareCore — shared request instrumentation),
                  instrument.py (instrument_fastapi/flask/django)
  slo/            (SLO tracking and error budget)
  integrations/   db/ (tracker, sqlalchemy, psycopg2, psycopg3)
                  queue/ (tracker, tracing, kafka, rabbitmq)
                  grpc.py
  testing/        mocks.py (test helpers)
  _experimental/  (experimental modules — API may change)
  config.py       ObskitSettings + configure_observability()
  interfaces.py   shared protocols
```

---

## Key Patterns

### Configuration (recommended)
```python
from obskit import configure_observability, instrument_fastapi

obs = configure_observability(
    service_name="my-service",
    environment="production",
    version="1.0.0",
    otlp_endpoint="http://tempo:4317",
    trace_sample_rate=0.1,
)
# obs.tracer  — OpenTelemetry tracer
# obs.metrics — RED metrics recorder
# obs.logger  — structured logger
# obs.config  — immutable ObservabilityConfig

app = FastAPI()
instrument_fastapi(app)
```

`configure_observability()` returns an `Observability` facade. The legacy
`configure()` / `get_settings()` API also works. Settings read from
`OBSKIT_*` env vars (prefix set in `ObskitSettings`).

### ObservabilityConfig (structured config)
```python
obs.config.service.name           # "my-service"
obs.config.tracing.sample_rate    # 0.1
obs.config.metrics.port           # 9090
obs.config.logging.level          # "INFO"
```

### Correlation ID
- Always propagated via `x-correlation-id` header
- Validated with `^[a-zA-Z0-9\-_\.]{1,128}$` — invalid IDs are silently dropped and regenerated
- Use `async_correlation_context()` / `get_correlation_id()` from `obskit.core.context`

### RED Metrics
```python
from obskit.metrics.red import get_red_metrics
metrics = get_red_metrics()
metrics.observe_request(operation="create_order", duration_seconds=0.05, status="success")
```
- Operation labels: alphanumeric + underscore only (`^[a-zA-Z0-9_]+$`)
- Invalid characters → normalised to `"invalid_operation"` (warning logged)
- Labels >128 chars → hash-suffixed truncation (119 + "_" + 8-char md5)
- 404 with no matched route → `"unmatched_route"` (prevents cardinality explosion)

### Baggage / Tracing
- W3C traceparent + baggage propagation
- Baggage validation uses **byte length** (`len(value.encode("ascii"))`), not char length
- `get_span_drop_count()` — returns cumulative dropped spans from `BatchSpanProcessor`

### Secret Masking
- `ObskitSettings.model_dump()` redacts `metrics_auth_token` → `[REDACTED]`
- `obskit.logging.redaction.make_redaction_processor(fields)` — structlog processor
  for PII/credential scrubbing; supports recursive dict traversal

### Multiprocess Metrics (Gunicorn)
```python
from obskit.metrics.multiprocess import setup_multiprocess_registry, child_exit
# In gunicorn config:
# child_exit = child_exit  ← cleans up worker .db files on exit
```
Set `PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc` before importing prometheus_client.

---

## Testing Conventions

- Mirror layout: `src/obskit/<pkg>/foo.py` → `tests/unit/<pkg>/test_foo.py`
- **100% branch coverage required** — `--cov-fail-under=100`
- Add `# pragma: no cover` **only** for `if TYPE_CHECKING:` blocks and `# pragma: no cover` defensive guards for code that provably cannot execute
- Tests use `pytest-randomly` — failures may be order-dependent; use `--randomly-seed=last` to reproduce
- FastAPI route paths include prefix: use `any(p.endswith("/live") for p in paths)` not exact match
- `asyncio.wait_for()` requires awaitable: call first, check `asyncio.iscoroutine(result)`
- `ObskitMiddleware` is raw ASGI (not `BaseHTTPMiddleware`) — test with raw scope dicts or `TestClient`

### New Feature Checklist
1. `src/obskit/<package>/<module>.py`
2. `tests/unit/<package>/test_<module>.py` (100% coverage)
3. `docs/packages/<pkg>.md` — API reference section
4. `docs/user-guide/<feature>.md` — usage guide (if user-facing)
5. `mkdocs.yml` nav entry
6. `CHANGELOG.md` `[Unreleased]` section
7. `pyproject.toml` version bump (patch/minor/major per semver)

---

## Architecture Decisions

- **Structlog** for structured JSON logging (ADR-003)
- **OpenTelemetry** SDK for tracing — no vendor lock-in (ADR-004)
- **Namespace packages** (`obskit.*`) — installable as single wheel (ADR-001)
- **Setuptools** as build backend (ADR-002)
- **Adaptive sampling** — head-based, configurable per-operation (ADR-004)
- **Exemplars** in OpenMetrics format (ADR-005)
- `# pragma: no cover` policy for genuinely unreachable guards (ADR-006)

---

## CI / Workflows

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `ci.yml` | push / PR | pytest 100%, mypy, ruff |
| `security.yml` | schedule + push | pip-audit (ignores GHSA-5239-wwwm-4pmq — pygments ReDoS, no fix) |
| `docs.yml` | push to main | `mkdocs build --strict` → GitHub Pages |
| `mutation.yml` | schedule | mutmut mutation testing |
| `release.yml` | tag push | build + publish to PyPI |
| `release-please.yml` | push to main | auto-PR for version bumps |
| `codeql.yml` | schedule | CodeQL static analysis |

---

## obskit-specific Rules

- `health/router.py` — `build_health_router(checks, readiness_checks, liveness_checks, prefix)`; caller provides callables
- `health/checker.py` — `HealthCheck` accepts `check=` (preferred) or `check_fn=` (legacy)
- `HealthStatus`: `healthy` / `degraded` / `unhealthy` — non-critical failure → degraded; critical failure → unhealthy
- `middleware/fastapi.py` — raw ASGI (not `BaseHTTPMiddleware`); measures full response duration including streaming
- `metrics/red.py` regex: `^[a-zA-Z0-9_]+$` (char check) then `elif len > 128` (length truncation) — these are two separate tiers, not combined

---

## Version History

- **1.0.0** — Initial production release. Unified `configure_observability()` API,
  `Observability` facade, `ObservabilityConfig` dataclasses, `MiddlewareCore` shared
  instrumentation, `instrument_fastapi/flask/django()` helpers, `_experimental/` and
  `_internal/` namespace packages, lazy imports for optional deps; 4,168 tests, 100% coverage
