# ADR-005: OpenMetrics Exemplar Format for Trace Linking

**Date:** 2026-02-01
**Status:** Accepted

## Context

Metrics and traces are two separate pillars of observability. Jumping from a Grafana metric graph ("latency spike at 14:32") to the exact trace that caused it requires some form of linkage. Two options were considered: custom labels and OpenMetrics Exemplars.

## Decision

Use **OpenMetrics Exemplars** via `prometheus_client >= 0.16.0`.

```python
histogram.observe(0.045, exemplar={"trace_id": "4bf92f3...", "span_id": "00f067..."})
```

## Rationale

- Exemplars are the **OpenMetrics standard** — supported natively by Prometheus 2.43+ and Grafana Tempo
- No extra labels added to metric time-series (avoids cardinality explosion)
- Grafana displays exemplars as dots on metric graphs with one-click jump to Tempo
- Graceful degradation: `observe_with_exemplar()` falls back to plain `observe()` on `TypeError` (old prometheus-client), so no breaking changes

## Consequences

- Requires `prometheus_client >= 0.16.0` for exemplar support (gracefully degrades on older versions)
- Exemplars are only visible in OpenMetrics scrape format (`Accept: application/openmetrics-text`)
- `is_exemplar_available()` provides runtime introspection
