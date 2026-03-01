# ADR-001: Consolidate to Single obskit Package

**Date:** 2026-03-01
**Status:** Accepted — supersedes the previous namespace package approach
**Deciders:** Talaat Magdy

## Context

obskit v1 was a single-package monolith (`pip install obskit`). In an earlier revision (v2.0), it was split into 16 separate namespace packages (`obskit-core`, `obskit-logging`, `obskit-metrics`, etc.) using PEP 420 implicit namespace packages so that `from obskit.logging import get_logger` would work regardless of which sub-packages were installed.

While the namespace approach preserved backward-compatible imports, it introduced significant operational complexity:

- 16 independent PyPI distributions to publish, each requiring its own trusted publisher configuration.
- Coordinated version bumps across all packages on every release, enforced by tooling but error-prone.
- Namespace package rules (no `__init__.py` at the `obskit/` root in sub-packages) were easy to violate accidentally, breaking the entire import system silently.
- Some editors and static analysis tools reported false errors due to incomplete namespace package support.
- Users were confused by the split: `pip install "obskit[prometheus]"` installed one package while `pip install obskit-logging` installed another, yet both contributed to the same `obskit.*` namespace.
- CI pipelines had to publish 16 packages sequentially, increasing release time and the risk of partial failures.

The dependency isolation goal — pulling in Prometheus without OpenTelemetry, for example — can be achieved within a single package using **optional extras** (`pip install "obskit[prometheus]"`), without the namespace complexity.

## Decision

Consolidate all 16 packages back into a single `obskit` package with optional extras.

- Source lives in `src/obskit/` (a regular package with `__init__.py`).
- Tests live in `tests/unit/` (a flat test tree instead of per-package trees under `packages/*/tests/`).
- Optional integrations are gated behind `pyproject.toml` extras:

  ```
  pip install obskit                              # core: structlog, PyYAML, pydantic-settings
  pip install "obskit[prometheus]"               # + prometheus-client
  pip install "obskit[otlp]"                     # + opentelemetry-api/sdk/exporter
  pip install "obskit[fastapi]"                  # + fastapi, starlette
  pip install "obskit[flask]"                    # + flask, werkzeug
  pip install "obskit[django]"                   # + django
  pip install "obskit[sqlalchemy]"               # + sqlalchemy 2.0
  pip install "obskit[kafka]"                    # + kafka-python
  pip install "obskit[rabbitmq]"                 # + pika
  pip install "obskit[redis]"                    # + redis
  pip install "obskit[httpx]"                    # + httpx
  pip install "obskit[loguru]"                   # + loguru
  pip install "obskit[all]"                      # every extra above
  ```

- All existing imports (`from obskit.logging import get_logger`, etc.) remain unchanged.
- A single PyPI trusted publisher is configured for the one `obskit` distribution.

## Consequences

**Positive:**

- One package to publish, one version to bump, one trusted publisher to maintain.
- `pip install "obskit[prometheus,otlp,fastapi]"` is self-documenting and unambiguous.
- No namespace package rules to enforce; standard Python package structure throughout.
- Editor and static analysis tool support works correctly out of the box.
- Release pipeline is simpler: one build, one upload.
- Dependency isolation is preserved through extras — users still do not pay for integrations they do not use.

**Negative:**

- The single `obskit` package version now represents the entire library; there is no longer independent versioning per integration area.
- Users who previously pinned individual sub-packages (`obskit-metrics==2.0.0`) must migrate to the unified extras syntax.

## Alternatives Considered

1. **Keep the 16-package namespace approach** — rejected due to operational overhead (16 publishers, coordinated releases, namespace pitfalls) that outweighed the independent-versioning benefit.
2. **Separate top-level packages** (`obskit_logging`, `obskit_metrics`) — rejected because it would break all existing `from obskit.logging import ...` imports.
3. **Import shim compatibility layer** — rejected as an extra layer of complexity with no clear long-term benefit.
