# ADR-006: Coverage Pragma Pattern for Untestable OTLP Branches

**Date:** 2026-02-01
**Status:** Accepted

## Context

The OTLP exporter branch in `configure_tracing()` requires a live OTLP collector endpoint to test. Including it in unit tests would require either a real network connection or a complex mock. The branch is marked `# pragma: no cover`.

A side-effect was discovered: coverage.py v7 propagates `# pragma: no cover` from an `if` clause to **sibling `elif` clauses** in the same compound statement. The `elif debug:` branch (which IS unit-testable) was being excluded from coverage tracking.

## Decision

Instead of `if endpoint...: ... elif debug:`, use a **flag variable + separate `if`**:

```python
_provider_registered = False
if endpoint and settings.tracing_enabled:  # pragma: no cover
    ...
    _provider_registered = True

# Separate `if` — not `elif` — so coverage.py tracks it independently
if debug and not _provider_registered:
    trace.set_tracer_provider(provider)
    ...
```

The comment in the code explains the rationale so future maintainers understand the unusual pattern.

## Additionally

A test was added that patches `get_settings()` to return `otlp_endpoint=None` explicitly. This makes the test hermetic regardless of whether `OBSKIT_OTLP_ENDPOINT` is set in the developer's environment.

## Consequences

- The debug-only path is fully covered by unit tests (100% coverage)
- The OTLP path remains `# pragma: no cover` (integration-tested separately)
- The code pattern is slightly unusual but is clearly documented
