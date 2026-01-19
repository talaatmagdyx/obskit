# Features Overview

obskit v1.3.0 includes **52+ production-ready features** for comprehensive observability.

## Feature Categories

### 🔍 Core Observability
| Feature | Description |
|---------|-------------|
| [RED Metrics](../user-guide/metrics.md) | Rate, Errors, Duration for APIs |
| [Golden Signals](../user-guide/metrics.md) | Latency, Traffic, Errors, Saturation |
| [USE Metrics](../user-guide/metrics.md) | Utilization, Saturation, Errors |
| [Structured Logging](../user-guide/logging.md) | JSON logs with correlation IDs |
| [Distributed Tracing](../user-guide/tracing.md) | OpenTelemetry-based tracing |

### 🛡️ Resilience & Reliability
| Feature | Description |
|---------|-------------|
| [Circuit Breaker](../user-guide/resilience.md) | Prevent cascading failures |
| [Distributed Circuit Breaker](../user-guide/resilience.md) | Redis-backed multi-instance |
| [Retry with Backoff](../user-guide/resilience.md) | Exponential backoff with jitter |
| [Rate Limiting](../user-guide/resilience.md) | Token bucket, sliding window |
| [Load Shedding](complete-reference.md#24-load-shedding) | Graceful request rejection |

### 🏥 Health & Operations
| Feature | Description |
|---------|-------------|
| [Health Checks](../user-guide/health-checks.md) | Kubernetes-ready probes |
| [SLO Tracking](../user-guide/slo.md) | Error budgets and compliance |
| [Alertmanager Integration](complete-reference.md#3-slo--error-budgets) | Send alerts programmatically |

### 🔬 v1.3.0 - Debugging & Analysis
| Feature | Description |
|---------|-------------|
| Flame Graph Profiler | CPU/memory profiling |
| Query Plan Analyzer | SQL optimization |
| Dependency Graph | Service visualization |
| Root Cause Analyzer | Incident analysis |
| Error Fingerprinting | Group similar errors |
| Latency Breakdown | Phase-by-phase analysis |
| Hot Path Detector | Critical code paths |

### 🔒 v1.3.0 - Security & Compliance
| Feature | Description |
|---------|-------------|
| Audit Trail | Immutable logging |
| Secrets Detection | Detect and redact |
| Compliance Reporter | GDPR/SOC2/HIPAA |
| PII Redaction | Automatic redaction |

### ⚡ v1.3.0 - Advanced Resilience
| Feature | Description |
|---------|-------------|
| Chaos Engineering | Failure injection |
| Graceful Degradation | Feature degradation |
| Self-Healing | Automatic remediation |
| Failover Coordinator | Primary/backup management |

### 📊 v1.3.0 - Infrastructure
| Feature | Description |
|---------|-------------|
| Connection Pool Metrics | DB/Redis pool tracking |
| DLQ Tracking | Dead letter queues |
| Consumer Lag | Message lag monitoring |
| External API SLA | Third-party SLA tracking |
| Memory/GC Metrics | Python memory tracking |
| Executor Metrics | ThreadPool tracking |

### 🚀 v1.3.0 - Operations
| Feature | Description |
|---------|-------------|
| Runbook Integration | Alert to runbook linking |
| Incident Timeline | Post-mortem support |
| SLA Predictor | Breach prediction |
| Capacity Planner | Resource forecasting |
| Alert Deduplication | Reduce noise |
| Grafana Annotations | Deployment markers |

## Complete Reference

For detailed documentation of all 52+ features with code examples:

```{toctree}
:maxdepth: 2

complete-reference
```
