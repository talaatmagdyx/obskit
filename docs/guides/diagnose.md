# How to Use obskit Diagnose

The `obskit diagnose` command inspects your Python environment and produces a
structured report of the obskit package, its version, and status of each installed extra (prometheus, otlp, fastapi, etc.).
Use it whenever you need to verify a deployment, debug a missing feature, or confirm
that a CI environment is configured correctly.

---

## Running the CLI

```bash
python -m obskit.core.diagnose
```

No arguments are required.  The command reads the current Python environment and prints
a formatted table to stdout.

### Sample output

```
obskit environment diagnostics
────────────────────────────────────────────────────────────────────────────────
Component                  Version    Status         Notes
────────────────────────────────────────────────────────────────────────────────
obskit                     1.0.0      ✓ installed

prometheus-client          0.20.0     ✓ available
  └─ trace-exemplars                  ✓ available

opentelemetry-api          1.27.0     ✓ available
opentelemetry-sdk          1.27.0     ✓ available
exporter-otlp-grpc         1.27.0     ✓ available
  └─ endpoint                         http://localhost:4317
  └─ service-name                     order-service

structlog                  24.1.0     ✓ available
  └─ trace-correlation               ✓ available

fastapi                    0.110.0    ✓ available
starlette                  0.36.3     ✓ available
────────────────────────────────────────────────────────────────────────────────
Python                     3.12.2
Platform                   macOS-15.0-arm64
obskit                     1.0.0
────────────────────────────────────────────────────────────────────────────────
```

---

## Reading the output

### Status column

| Symbol | Meaning |
|--------|---------|
| `✓ installed` | Component is present in the current environment |
| `not installed` | Component is absent (may or may not be expected) |
| `✓ available` | Optional integration dependency is installed and importable |
| `✗ not installed (optional)` | Optional dependency is absent — feature degrades gracefully |
| `✗ not installed` | Required dependency is absent — feature is broken |

### Integration rows

Each installed obskit component lists its key dependencies as indented rows.  A
dependency marked **optional** means the core package works without it, but certain
features will be unavailable:

- `obskit` without `structlog` → falls back to stdlib `logging` (install `obskit`).
- `obskit` without `trace-correlation` → logs omit `trace_id` / `span_id` (call setup_tracing() before logging).
- `obskit` without `prometheus-client` → metrics are silently no-ops (install `obskit[prometheus]`).
- `obskit` without `exporter-otlp-grpc` → traces are not exported anywhere (install `obskit[otlp]`).

---

## Python API

You can call the diagnose logic programmatically — for example, to include the results
in a `/diagnose` HTTP endpoint or a custom health check.

### `collect_diagnostics()`

Returns a list of `PackageInfo` objects describing every known obskit package.

```python
from obskit.core.diagnose import collect_diagnostics

packages = collect_diagnostics()
for pkg in packages:
    print(pkg.name, pkg.version or "not installed", pkg.installed)
    for integration in pkg.integrations:
        status = "ok" if integration.available else "missing"
        print(f"  {integration.name}: {integration.version or ''} ({status})")
```

### `run_diagnostics(out=None)`

Formats the diagnostics table and writes it to `out` (defaults to `sys.stdout`).
Use `io.StringIO` to capture the output as a string:

```python
import io
from obskit.core.diagnose import run_diagnostics

buffer = io.StringIO()
run_diagnostics(out=buffer)
report = buffer.getvalue()
print(f"Report length: {len(report)} chars")
```

### Dataclasses

```python
from obskit.core.diagnose import PackageInfo, IntegrationInfo

# PackageInfo
# -----------
# name: str               — e.g. "obskit"
# version: str | None     — e.g. "2.0.0", or None if not installed
# installed: bool         — True if importable
# integrations: list[IntegrationInfo]

# IntegrationInfo
# ---------------
# name: str               — e.g. "structlog"
# version: str | None     — installed version, or None
# available: bool         — True if importable / configured
# optional: bool          — True if the feature degrades gracefully without it
# note: str | None        — human-readable explanation (e.g. "endpoint: http://…")
```

---

## Adding a /diagnose endpoint to FastAPI

Expose the diagnose output over HTTP so that your platform team can check any running
pod without SSH access:

```python
import io
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from obskit.core.diagnose import collect_diagnostics, run_diagnostics

app = FastAPI()


@app.get("/diagnose", response_class=PlainTextResponse)
def diagnose_endpoint():
    """Return obskit environment diagnostics as plain text."""
    buffer = io.StringIO()
    run_diagnostics(out=buffer)
    return buffer.getvalue()


@app.get("/diagnose/json")
def diagnose_json():
    """Return obskit environment diagnostics as structured JSON."""
    packages = collect_diagnostics()
    return [
        {
            "package": pkg.name,
            "version": pkg.version,
            "installed": pkg.installed,
            "integrations": [
                {
                    "name": i.name,
                    "version": i.version,
                    "available": i.available,
                    "optional": i.optional,
                    "note": i.note,
                }
                for i in pkg.integrations
            ],
        }
        for pkg in packages
    ]
```

Example curl output for `/diagnose/json`:

```json
[
  {
    "package": "obskit",
    "version": "1.0.0",
    "installed": true,
    "integrations": [
      {"name": "opentelemetry-api", "version": "1.27.0", "available": true, "optional": false, "note": null},
      {"name": "opentelemetry-sdk", "version": "1.27.0", "available": true, "optional": false, "note": null},
      {"name": "endpoint",          "version": null,      "available": true, "optional": false,
       "note": "http://localhost:4317"}
    ]
  }
]
```

---

## Using diagnose in CI/CD

Add a step to your pipeline that asserts the expected obskit packages are installed
before running tests or deploying:

=== "GitHub Actions"

    ```yaml
    # .github/workflows/ci.yml
    - name: Verify obskit environment
      run: |
        python -m obskit.core.diagnose
        # Exit non-zero if a required package is missing
        python - <<'EOF'
        from obskit.core.diagnose import collect_diagnostics, PackageInfo
        required = {"obskit"}
        packages = collect_diagnostics()
        installed = {p.name for p in packages if p.installed}
        missing = required - installed
        if missing:
            import sys
            print(f"FAIL: missing required packages: {missing}", file=sys.stderr)
            sys.exit(1)
        print("OK: all required obskit packages installed")
        EOF
    ```

=== "Makefile"

    ```makefile
    .PHONY: check-obskit
    check-obskit:
    	python -m obskit.core.diagnose
    	python -c "
    	from obskit.core.diagnose import collect_diagnostics
    	required = {'obskit'}
    	missing = {p.name for p in collect_diagnostics() if p.name in required and not p.installed}
    	assert not missing, f'Missing: {missing}'
    	print('All required obskit packages installed.')
    	"
    ```

=== "pytest fixture"

    ```python
    # tests/conftest.py
    import pytest
    from obskit.core.diagnose import collect_diagnostics

    @pytest.fixture(scope="session", autouse=True)
    def assert_obskit_environment():
        """Fail the test session early if required obskit packages are absent."""
        required = {"obskit"}
        packages = {p.name: p for p in collect_diagnostics()}
        for name in required:
            pkg = packages.get(name)
            assert pkg and pkg.installed, (
                f"Required package '{name}' is not installed. "
                f"Run: pip install obskit"
            )
    ```

---

## Using diagnose in a health check

Create a custom `obskit-environment` health check that runs `collect_diagnostics()` and
returns `unhealthy` if any required package is missing:

```python
from obskit.health import HealthChecker
from obskit.core.diagnose import collect_diagnostics

REQUIRED_PACKAGES = {
    "obskit",
}


async def check_obskit_environment(name: str) -> dict:
    packages = collect_diagnostics()
    missing = [
        p.name
        for p in packages
        if p.name in REQUIRED_PACKAGES and not p.installed
    ]
    if missing:
        return {
            "status": "unhealthy",
            "error": f"Missing obskit packages: {', '.join(missing)}",
        }

    # Check that all required integrations are available
    broken_integrations = []
    for p in packages:
        if p.name in REQUIRED_PACKAGES:
            for integration in p.integrations:
                if not integration.available and not integration.optional:
                    broken_integrations.append(f"{p.name}/{integration.name}")

    if broken_integrations:
        return {
            "status": "degraded",
            "warning": f"Broken integrations: {', '.join(broken_integrations)}",
        }

    return {"status": "healthy", "packages": len(packages)}


checker = HealthChecker(service_name="order-service", version="2.0.0")
checker.add_check("obskit-environment", check_obskit_environment)
```

---

## Troubleshooting common diagnose outputs

### "otlp extra shows as not installed"

```bash
pip install "obskit[otlp]"
# Then verify:
python -m obskit.core.diagnose
```

If the package appears installed in `pip list` but `diagnose` still shows it as missing,
you may have multiple Python environments.  Check which Python is active:

```bash
which python
python -c "import sys; print(sys.prefix)"
pip show obskit
```

### "structlog shows as unavailable"

`obskit` is installed but `structlog` is not.  Install it:

```bash
pip install obskit
```

### "trace-correlation shows as unavailable"

`obskit[otlp]` is not installed, or the OTel SDK is present but `setup_tracing()`
has not been called.  `is_trace_correlation_available()` performs a runtime check,
so it returns `False` until the `TracerProvider` is initialised:

```python
from obskit.tracing import setup_tracing
setup_tracing(service_name="my-service", exporter_endpoint="http://localhost:4317")
# Now run diagnose again — trace-correlation will show as available
```

### "endpoint shows as not configured"

`obskit[otlp]` is installed but no OTLP endpoint has been provided.  Set the
environment variable or pass it to `setup_tracing()`:

```bash
export OBSKIT_OTLP_ENDPOINT=http://localhost:4317
```

```python
from obskit.tracing import setup_tracing
import os
setup_tracing(
    service_name="order-service",
    exporter_endpoint=os.environ["OBSKIT_OTLP_ENDPOINT"],
)
```

### "prometheus-client shows as unavailable"

```bash
pip install "prometheus-client>=0.16.0"
```

Versions below 0.16.0 do not support exemplars and may cause import errors in
`obskit[prometheus]`.

---

## Environment variables that affect diagnose

| Variable | Effect on diagnose output |
|----------|--------------------------|
| `OBSKIT_OTLP_ENDPOINT` | Shown as the `endpoint` integration note in the tracing section |
| `OBSKIT_SERVICE_NAME` | Shown as the `service-name` note in the tracing section |
| `OBSKIT_TRACING_ENABLED` | If set to `false`, tracing integrations show as disabled |
| `OBSKIT_LOG_LEVEL` | Shown in the logging section |
| `OBSKIT_CONFIG_FILE` | Path to the YAML config file; shown if the file exists and is valid |

---

## Summary

| Task | Command / Code |
|------|---------------|
| Run diagnose | `python -m obskit.core.diagnose` |
| Programmatic access | `from obskit.core.diagnose import collect_diagnostics` |
| Capture as string | `run_diagnostics(out=io.StringIO())` |
| FastAPI endpoint | `GET /diagnose` → `run_diagnostics(out=buffer)` |
| CI assertion | Assert `{p.name for p in collect_diagnostics() if p.installed}` ⊇ required set |
| Health check | Custom async check using `collect_diagnostics()` |
