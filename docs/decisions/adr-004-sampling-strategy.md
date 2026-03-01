# ADR-004: W3C-compliant ParentBased Sampling Strategy

**Date:** 2026-02-01
**Status:** Accepted

## Context

When obskit added `sample_rate` support to its tracing module, a decision was needed on which OTel sampler to use.

## Decision

Use `ParentBased(TraceIdRatioBased(sample_rate))` — the W3C-recommended strategy.

```python
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

sampler = ParentBased(TraceIdRatioBased(sample_rate))
```

## Rationale

**`TraceIdRatioBased` alone** samples independently at each service boundary. This means a 10%-sampled upstream service might decide "keep this trace" but a 10%-sampled downstream service independently decides "drop this trace". The result: **broken traces** in Tempo/Jaeger where the root span exists but child spans are missing.

**`ParentBased(TraceIdRatioBased)`** propagates the sampling decision via the W3C `traceparent` header. If the upstream kept the trace, all downstream services also keep it. If the upstream dropped it, all downstream services also drop it. This produces **complete traces** at the configured rate.

## Consequences

- Traces are always complete — never have orphaned spans
- Sampling decision is deterministic based on `trace_id` (same trace always sampled or always dropped across restarts)
- Requires W3C TraceContext propagation (default in OTel SDK)
