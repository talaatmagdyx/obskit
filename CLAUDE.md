# obskit — Claude Code Context

## Project Overview

**obskit** is a production-ready observability toolkit for Python microservices.
Version: 3.3.0 | License: MIT | Python: ≥3.11

Provides: structured logging, RED metrics, distributed tracing (OTel), health checks,
circuit breakers, rate limiters, SLO tracking, PII redaction, and ASGI middleware — all
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
  core/           context.py (correlation ID), shutdown.py
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
  resilience/     circuit_breaker.py, rate_limiter.py, retry.py,
                  adaptive.py, combined.py, distributed.py, factory.py
  middleware/     fastapi.py, flask.py, django.py, grpc.py
  slo/            (SLO tracking and error budget)
  alerts/         builder.py (AlertRule, AlertGroup, export_yaml)
  queue/          (async queue utilities)
  db/             (database observability)
  decorators/     (function-level observability decorators)
  testing/        mocks.py (test helpers)
  config.py       ObskitSettings (pydantic-settings, env-driven)
  interfaces.py   shared protocols
```

---

## Key Patterns

### Configuration
```python
from obskit import configure
configure(
    service_name="my-service",
    environment="production",
    version="1.0.0",
    tracing_enabled=True,
    otlp_endpoint="http://tempo:4317",
)
```
`configure()` must be called **before** any other obskit import. Settings read from
`OBSKIT_*` env vars (prefix set in `ObskitSettings`).

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

### Circuit Breaker
```python
from obskit.resilience import CircuitBreaker
cb = CircuitBreaker(name="payment-gw", failure_threshold=5, recovery_timeout=30.0)
@cb
async def call_payment(): ...
```
Uses `time.monotonic()` — immune to NTP clock adjustments.

### Rate Limiter
```python
from obskit.resilience.rate_limiter import RateLimiter
limiter = RateLimiter(requests=100, window_seconds=60.0)
```
Sliding window + token bucket, both using `time.monotonic()`.

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

- `alerts/builder.py` — fluent builder (`AlertRule`, `AlertGroup`, `export_yaml`); no hardcoded thresholds
- `health/router.py` — `build_health_router(checks, readiness_checks, liveness_checks, prefix)`; caller provides callables
- `health/checker.py` — `HealthCheck` accepts `check=` (preferred) or `check_fn=` (legacy)
- `HealthStatus`: `healthy` / `degraded` / `unhealthy` — non-critical failure → degraded; critical failure → unhealthy
- `middleware/fastapi.py` — raw ASGI (not `BaseHTTPMiddleware`); measures full response duration including streaming
- All time-based resilience logic uses `time.monotonic()` — never `time.time()`
- `metrics/red.py` regex: `^[a-zA-Z0-9_]+$` (char check) then `elif len > 128` (length truncation) — these are two separate tiers, not combined

---

## Version History (recent)

- **3.3.0** — 8 production-hardening fixes: monotonic clock, thread join, cardinality guard,
  span drop observability, baggage byte validation, multiprocess cleanup, secret masking,
  404 route normalisation; pymdownx pinned to <10.0.0 to fix docs build
- **3.2.0** — `obskit.logging.redaction`, `obskit.metrics.multiprocess`, 100% test coverage
- **3.1.0** — adaptive sampling, OpenMetrics exemplars, SLO error budgets
