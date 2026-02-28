# ADR-002: Setuptools over Hatchling for Namespace Package Support

**Date:** 2026-02-01
**Status:** Accepted

## Context

obskit v1 used **Hatchling** as its build backend. When splitting into namespace packages, Hatchling was evaluated for namespace package support.

## Decision

Switch all sub-packages to **setuptools** with `namespaces = true` in `[tool.setuptools.packages.find]`.

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
namespaces = true   # ← critical
```

## Rationale

Hatchling's namespace package support requires explicit configuration that is fragile with `src/` layout and multi-package namespace roots. setuptools has first-class, battle-tested namespace package support via `namespaces = true` and is the de-facto standard for namespace packages in the Python ecosystem.

## Consequences

- All 12 packages use setuptools (slight build time increase vs Hatchling, negligible)
- Namespace merging works correctly: `import obskit.logging` and `import obskit.metrics` both resolve even when installed from different packages
