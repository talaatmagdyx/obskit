# ADR-001: Python Namespace Packages for Monorepo Split

**Date:** 2026-02-01
**Status:** Accepted
**Deciders:** Talaat Magdy

## Context

obskit v1 was a single-package monolith (`pip install obskit`). As the library grew to 65+ modules spanning tracing, metrics, logging, health checks, chaos engineering, compliance, and more, it became unwieldy. Users who only wanted Prometheus metrics had to install OpenTelemetry, FastAPI, SQLAlchemy instrumentation, and a dozen other transitive dependencies.

The team decided to split the monolith into focused packages. The core challenge: maintaining backward compatibility so that `from obskit.logging import get_logger` continues to work **without any import changes**, regardless of whether the user installed `obskit-logging` or the full `obskit` meta-package.

## Decision

Use **Python namespace packages** (PEP 420 / PEP 451). Each sub-package contributes to the `obskit.*` namespace without owning `obskit/__init__.py`. Only the meta-package `obskit` provides `obskit/__init__.py`.

**Rules:**
- `packages/obskit-logging/src/obskit/` → **no `__init__.py`** (namespace root)
- `packages/obskit-logging/src/obskit/logging/` → **has `__init__.py`** (regular package)
- `packages/obskit/src/obskit/` → **has `__init__.py`** (meta-package only)

Python's import system merges all contributions at runtime, so `import obskit.logging` and `import obskit.metrics` both work even though they come from different installed packages.

## Consequences

**Positive:**
- Zero import changes for users upgrading from v1
- `pip install obskit-metrics` gives metrics without OTel overhead
- `pip install obskit` gives everything (backward compatible with v1)
- Each package can be versioned and released independently

**Negative:**
- Developers must never accidentally add `__init__.py` to namespace roots
- Tools that don't understand namespace packages (some linters, IDEs) may report false errors
- Install-order edge cases with namespace packages resolved by setuptools `namespaces=true`

## Alternatives Considered

1. **Separate top-level packages** (`obskit_logging`, `obskit_metrics`) — rejected because it breaks all existing imports
2. **Import shim** in a compatibility layer — rejected as too complex to maintain
3. **Keep monolith** — rejected because it forces unnecessary dependencies
