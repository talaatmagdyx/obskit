# Migrating from obskit v1.x to v2.0.0

obskit v2.0.0 is a **monorepo split**: the single `obskit` wheel you installed in
v1.x has been reorganised into 16 focused namespace packages that share the `obskit`
Python namespace.  The public API surface, configuration model, and behaviour are
unchanged — you only update install commands and (optionally) a handful of imports.

---

## Why We Split the Monolith

| Problem in v1.x | Solution in v2.0.0 |
|---|---|
| Installing `obskit` pulled in OpenTelemetry, Prometheus, structlog, pydantic-settings, PyYAML — even if you only needed logging | Each package declares only the deps it needs |
| A bug in the Kafka integration caused a release block for the FastAPI middleware | Packages release independently |
| Tree-shaking was impossible — dead code from unused sub-systems lived in every deployment | Install only what you use |
| mypy struggled with a 10 000-line namespace | Smaller, focused packages are easier to type-check |
| Contributors had to understand the full codebase to add a new integration | Each package has its own `pyproject.toml`, tests, and README |

---

## Compatibility Guarantee

!!! success "Drop-in compatible"
    `pip install "obskit[all]"` in v2.0.0 installs **all 16 packages** and exposes
    the **exact same Python namespace** as v1.x.  Your existing `from obskit import …`
    statements continue to work without modification.

The only things that changed in v2.0.0 are:

1. How you **install** the library (per-package vs. monolith).
2. A handful of **preferred** import paths that are now more explicit (the old paths
   still work via the meta-package).
3. The removal of several **experimental** modules that were never part of the
   documented public API (see [Breaking Changes](#breaking-changes)).

---

## Breaking Changes

### Removed experimental modules

The following modules were marked `# experimental` in v1.x and are **not** present
in v2.0.0 packages.  They were never part of the documented API.

| Removed module | Reason | v2 alternative |
|---|---|---|
| `obskit.capacity` | Unused; superseded by `USEMetrics` | `obskit.metrics.USEMetrics` |
| `obskit.chaos` | Never stabilised | Use [chaos-monkey](https://pypi.org/project/chaosmonkey/) directly |
| `obskit.compliance.pii` | Replaced by `obskit-core` error redaction | `obskit.errors.responses` |
| `obskit.compliance_reporter` | Removed in v1.3 | No replacement |
| `obskit.deployment` | Unused | `obskit.core.context` for build metadata |
| `obskit.feature_flags` | Scope creep | Use [flagsmith](https://pypi.org/project/flagsmith/) directly |
| `obskit.flamegraph` | Unused | `py-spy` directly |
| `obskit.incident_timeline` | Unused | Grafana annotations |
| `obskit.resource_predictor` | ML dependency pulled in scikit-learn | Removed |
| `obskit.root_cause` | Unused | — |
| `obskit.runbook` | Unused | — |
| `obskit.secrets_detector` | Security-scanning belongs in CI | `detect-secrets` pre-commit hook |
| `obskit.self_healing` | Kubernetes-native feature | Kubernetes probes + HPA |

### configure_logging() renamed to get_logger()

```python
# v1.x
from obskit import configure_logging
logger = configure_logging(service_name="my-service")

# v2.0.0 — preferred
from obskit.logging import get_logger
logger = get_logger(__name__)
```

`configure_logging()` still exists in the meta-package for backward compatibility
but emits a `DeprecationWarning` since v2.0.0.

### get_red_metrics() replaced by REDMetrics constructor

```python
# v1.x
from obskit import get_red_metrics
metrics = get_red_metrics()
metrics.track_request(endpoint="/api/orders", method="POST")

# v2.0.0 — preferred
from obskit.metrics.red import REDMetrics
red = REDMetrics("order_service")
red.record_request("/api/orders", "POST", status="success", duration=0.045)
```

### Health check API simplified

```python
# v1.x
from obskit import get_health_checker
health = get_health_checker()
health.add_liveness_check("db", check_db)

# v2.0.0 — preferred
from obskit.health import HealthChecker
checker = HealthChecker()
checker.add_check("db", check_db)
```

### Tracing setup consolidated

```python
# v1.x
from obskit import configure_tracing, get_tracer
configure_tracing(service_name="my-service", otlp_endpoint="http://tempo:4317")
tracer = get_tracer()

# v2.0.0 — preferred
from obskit.tracing import setup_tracing, trace_span
setup_tracing(exporter_endpoint="http://tempo:4317")
```

---

## Step-by-Step Migration

### Step 1 — Assess your current installation

```bash
# See what you have installed today
pip show obskit
pip freeze | grep obskit
```

### Step 2 — Choose a migration strategy

**Option A — Minimal change (recommended for large codebases)**

Replace the monolith with the meta-package.  Zero import changes required.

```bash
pip uninstall obskit
pip install "obskit[all]"
```

**Option B — Selective install (recommended for new services)**

Only install the packages you actually use.  Update imports to the new paths.

```bash
pip install obskit-core obskit-logging obskit-metrics obskit-tracing obskit-health
```

**Option C — Incremental (recommended for teams)**

Keep `obskit[all]` installed and migrate one sub-system at a time over several
sprints.  Each sub-system migration is independently verifiable.

### Step 3 — Update your dependency file

=== "requirements.txt (Option A)"

    ```diff
    -obskit==1.5.0
    +obskit[all]==2.0.0
    ```

=== "requirements.txt (Option B)"

    ```diff
    -obskit==1.5.0
    +obskit-core==2.0.0
    +obskit-logging==2.0.0
    +obskit-metrics==2.0.0
    +obskit-tracing==2.0.0
    +obskit-health==2.0.0
    ```

=== "pyproject.toml"

    ```diff
     [project.dependencies]
    -  "obskit>=1.5.0,<2.0.0",
    +  "obskit[all]>=2.0.0,<3.0.0",
    ```

=== "setup.cfg"

    ```diff
     [options]
     install_requires =
    -    obskit>=1.5.0,<2.0.0
    +    obskit[all]>=2.0.0,<3.0.0
    ```

### Step 4 — Update imports (if using Option B or C)

Use the complete import mapping table in the next section.  A one-liner to find all
obskit imports in your project:

```bash
grep -r "from obskit import\|import obskit" src/ --include="*.py" -l
```

### Step 5 — Run your test suite

```bash
pytest tests/ -x -q
```

All tests should pass without modification if you chose Option A.

### Step 6 — Verify with obskit diagnose

```bash
python -m obskit.core.diagnose
```

This prints a table showing which packages are installed and which integrations are
available.  Confirm every package your application uses shows as installed.

---

## Complete Import Mapping Table

### Logging

| v1.x import | v2.0.0 import | Notes |
|---|---|---|
| `from obskit import configure_logging` | `from obskit.logging import get_logger` | Deprecated; emits warning |
| `from obskit import get_logger` | `from obskit.logging import get_logger` | Same name, new module |
| `from obskit.logging import get_logger` | `from obskit.logging import get_logger` | Unchanged |
| `from obskit.logging.logger import ObskitLogger` | `from obskit.logging.logger import ObskitLogger` | Unchanged |
| `from obskit.logging.factory import create_logger` | `from obskit.logging.factory import create_logger` | Unchanged |
| `from obskit.logging.sampling import SamplingFilter` | `from obskit.logging.sampling import SamplingFilter` | Unchanged |
| `from obskit.logging.dynamic import set_log_level` | `from obskit.logging.dynamic import set_log_level` | Unchanged |
| `from obskit.logging.adapters.structlog_adapter import StructlogAdapter` | `from obskit.logging.adapters.structlog_adapter import StructlogAdapter` | Unchanged |
| `from obskit.logging.adapters.loguru_adapter import LoguruAdapter` | `from obskit.logging.adapters.loguru_adapter import LoguruAdapter` | Unchanged |
| `from obskit.adaptive_sampling import AdaptiveSampler` | `from obskit.adaptive_sampling import AdaptiveSampler` | Package: obskit-logging |
| `from obskit.audit import AuditLogger` | `from obskit.audit import AuditLogger` | Package: obskit-logging |

### Metrics

| v1.x import | v2.0.0 import | Notes |
|---|---|---|
| `from obskit import get_red_metrics` | `from obskit.metrics.red import REDMetrics` | Constructor-based |
| `from obskit.metrics import REDMetrics` | `from obskit.metrics import REDMetrics` | Unchanged |
| `from obskit.metrics import GoldenSignals` | `from obskit.metrics import GoldenSignals` | Unchanged |
| `from obskit.metrics import USEMetrics` | `from obskit.metrics import USEMetrics` | Unchanged |
| `from obskit.metrics import TenantMetrics` | `from obskit.metrics import TenantMetrics` | Unchanged |
| `from obskit.metrics.cardinality import CardinalityGuard` | `from obskit.metrics.cardinality import CardinalityGuard` | Unchanged |
| `from obskit.metrics.exemplar import observe_with_exemplar` | `from obskit.metrics.exemplar import observe_with_exemplar` | New in v2 |
| `from obskit.annotations import track_metric` | `from obskit.annotations import track_metric` | Package: obskit-metrics |

### Tracing

| v1.x import | v2.0.0 import | Notes |
|---|---|---|
| `from obskit import configure_tracing` | `from obskit.tracing import setup_tracing` | New name; old still works |
| `from obskit import get_tracer` | `from obskit.tracing import get_tracer` | Unchanged |
| `from obskit.tracing import setup_tracing` | `from obskit.tracing import setup_tracing` | Unchanged |
| `from obskit.tracing import trace_span` | `from obskit.tracing import trace_span` | Unchanged |
| `from obskit.tracing import async_trace_span` | `from obskit.tracing import async_trace_span` | Unchanged |
| `from obskit.tracing import set_baggage` | `from obskit.tracing import set_baggage` | Unchanged |
| `from obskit.tracing import get_baggage` | `from obskit.tracing import get_baggage` | Unchanged |
| `from obskit.tracing import clear_baggage` | `from obskit.tracing import clear_baggage` | Unchanged |
| `from obskit.tracing import get_current_trace_id` | `from obskit.tracing import get_current_trace_id` | Unchanged |

### Health Checks

| v1.x import | v2.0.0 import | Notes |
|---|---|---|
| `from obskit import get_health_checker` | `from obskit.health import HealthChecker` | Constructor-based |
| `from obskit.health import HealthChecker` | `from obskit.health import HealthChecker` | Unchanged |
| `from obskit.health import HealthResult` | `from obskit.health import HealthResult` | Unchanged |
| `from obskit.health import HealthStatus` | `from obskit.health import HealthStatus` | Unchanged |
| `from obskit.health import create_http_check` | `from obskit.health import create_http_check` | Unchanged |
| `from obskit.health import create_tcp_check` | `from obskit.health import create_tcp_check` | Unchanged |

### Resilience

| v1.x import | v2.0.0 import | Notes |
|---|---|---|
| `from obskit.resilience import CircuitBreaker` | `from obskit.resilience import CircuitBreaker` | Unchanged |
| `from obskit.resilience import retry` | `from obskit.resilience import retry` | Unchanged |
| `from obskit.resilience import async_retry` | `from obskit.resilience import async_retry` | Unchanged |
| `from obskit.resilience import RateLimiter` | `from obskit.resilience import RateLimiter` | Unchanged |
| `from obskit.resilience import CircuitState` | `from obskit.resilience import CircuitState` | Unchanged |

### SLO

| v1.x import | v2.0.0 import | Notes |
|---|---|---|
| `from obskit.slo import SLOTracker` | `from obskit.slo import SLOTracker` | Unchanged |
| `from obskit.slo import SLOType` | `from obskit.slo import SLOType` | Unchanged |
| `from obskit.slo import with_slo_tracking` | `from obskit.slo import with_slo_tracking` | Unchanged |

### Configuration

| v1.x import | v2.0.0 import | Notes |
|---|---|---|
| `from obskit import configure` | `from obskit.config import configure` | Unchanged |
| `from obskit import get_settings` | `from obskit.config import get_settings` | Unchanged |
| `from obskit.config import ObskitSettings` | `from obskit.config import ObskitSettings` | Unchanged |

---

## CI/CD Changes

### GitHub Actions

```diff
 - name: Install dependencies
   run: |
-    pip install obskit==1.5.0
+    pip install "obskit[all]==2.0.0"
```

If you pin individual packages:

```yaml
- name: Install dependencies
  run: |
    pip install \
      obskit-core==2.0.0 \
      obskit-logging==2.0.0 \
      obskit-metrics==2.0.0 \
      obskit-tracing==2.0.0 \
      obskit-health==2.0.0 \
      obskit-resilience==2.0.0
```

### Docker

```dockerfile
# Before
RUN pip install obskit==1.5.0

# After (minimal image)
RUN pip install obskit-core==2.0.0 obskit-logging==2.0.0 obskit-metrics==2.0.0

# After (full)
RUN pip install "obskit[all]==2.0.0"
```

---

## Testing Migration

After switching to v2.0.0, run this verification checklist:

```bash
# 1. Diagnose — confirms all packages are installed
python -m obskit.core.diagnose

# 2. Import smoke test — catches missing packages
python -c "
import obskit.logging, obskit.metrics, obskit.tracing
import obskit.health, obskit.resilience, obskit.slo
print('All imports OK')
"

# 3. Full test suite
pytest tests/ -x -q --tb=short

# 4. Integration tests (if applicable)
pytest tests/integration/ -v
```

Expected output from diagnose:

```
obskit Package Diagnostics
==========================
Package              Version  Status
--------------------  -------  ------
obskit-core           2.0.0   ✓
obskit-logging        2.0.0   ✓
obskit-metrics        2.0.0   ✓
obskit-tracing        2.0.0   ✓
obskit-health         2.0.0   ✓
obskit-resilience     2.0.0   ✓
obskit-slo            2.0.0   ✓
obskit-decorators     2.0.0   ✓
obskit-db             2.0.0   ✓
obskit-queue          2.0.0   ✓
...

Integrations:
  opentelemetry-sdk   ✓ (1.23.0)
  prometheus-client   ✓ (0.20.0)
  structlog           ✓ (24.1.0)
```

---

## Incremental Migration Strategy

For large teams, migrate one sub-system per sprint:

**Sprint 1** — Logging  
Replace `configure_logging()` calls with `get_logger(__name__)`.  No behaviour change.

**Sprint 2** — Metrics  
Replace `get_red_metrics()` calls with `REDMetrics("service_name")`.  Update
`track_request()` calls to `record_request()` with the new signature.

**Sprint 3** — Tracing  
Replace `configure_tracing()` with `setup_tracing()`.  Update any direct
`get_tracer()` usage to `trace_span()` context managers.

**Sprint 4** — Health Checks  
Replace `get_health_checker()` with `HealthChecker()`.  Update
`add_liveness_check()` to `add_check()`.

**Sprint 5** — Slim the install  
Once all code uses the v2.0.0 APIs, switch from `obskit[all]` to per-package
installs.  Run `python -m obskit.core.diagnose` to confirm only needed packages
are present.

---

## Frequently Asked Questions

**Q: Do I need to change anything if I use `obskit[all]`?**  
A: No.  The meta-package restores the full v1.x namespace.  Your existing imports
will continue to work.

**Q: Will obskit[all] v2 receive security updates?**  
A: Yes.  The meta-package is updated on every release.  We recommend pinning to a
minor version: `"obskit[all]>=2.0.0,<3.0.0"`.

**Q: Can I mix v1 and v2 packages in the same virtualenv?**  
A: No.  They share the `obskit` namespace; installing both will result in import
conflicts.  Upgrade in one step.

**Q: I'm using a removed module (e.g. `obskit.chaos`). What do I do?**  
A: See the [Removed experimental modules](#removed-experimental-modules) table for
recommended replacements.  If you have a strong use-case, open a GitHub issue.

**Q: Does obskit v2 support Python 3.10?**  
A: No.  v2.0.0 requires Python 3.11+.  This was already the recommended minimum in
v1.5.0.

**Q: How do I know which package provides which module?**  
A: Run `python -m obskit.core.diagnose` or check the
[Architecture Overview](../architecture/overview.md) dependency graph.

**Q: Does the `OBSKIT_*` environment variable prefix change?**  
A: No.  All environment variables are identical to v1.x.

**Q: Does the Prometheus metrics registry reset?**  
A: No.  Metric names and label sets are unchanged.  Your Grafana dashboards will
continue to work without modification.

**Q: What happens to my Prometheus histograms during the upgrade?**  
A: Nothing.  Prometheus scrapes `/metrics` from your running process.  The metric
names, help strings, and label sets in v2.0.0 are identical to v1.x.  There is no
gap in data.

**Q: Are there any changes to the OTLP exporter configuration?**  
A: The `OBSKIT_OTLP_ENDPOINT` variable and `setup_tracing(exporter_endpoint=…)`
parameter are unchanged.  If you were passing extra OTel resource attributes via
`configure_tracing()`, they are now set with `setup_tracing(resource_attributes={…})`.
