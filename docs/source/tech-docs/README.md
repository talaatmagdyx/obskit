# obskit Technical Documentation

**Version:** 1.3.0  
**Status:** ✅ Production Ready  
**Last Updated:** 2026-01-19  
**Total Features:** 52+

---

## 📚 Complete Feature Reference

**[→ docs/FEATURES.md](../docs/FEATURES.md)** - Comprehensive documentation of all 52+ features with code examples.

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [00_PRODUCTION_REVIEW.md](00_PRODUCTION_REVIEW.md) | Production readiness review |
| [00_STAFF_ENGINEER_REVIEW.md](00_STAFF_ENGINEER_REVIEW.md) | Staff engineer technical review |
| [01_QUICK_START.md](01_QUICK_START.md) | Get started in 5 minutes |
| [02_CONFIGURATION.md](02_CONFIGURATION.md) | Complete configuration reference |
| [03_METRICS.md](03_METRICS.md) | RED, Golden Signals, USE guide |
| [04_HEALTH_CHECKS.md](04_HEALTH_CHECKS.md) | Health checks and probes |
| [05_RESILIENCE.md](05_RESILIENCE.md) | Circuit breaker, retry, rate limiting |
| [06_SLO_TRACKING.md](06_SLO_TRACKING.md) | SLO and error budget management |
| [07_SECURITY.md](07_SECURITY.md) | Security hardening guide |
| [08_KUBERNETES_DEPLOYMENT.md](08_KUBERNETES_DEPLOYMENT.md) | K8s deployment manifests |
| [09_TROUBLESHOOTING.md](09_TROUBLESHOOTING.md) | Common issues and solutions |

---

## Quick Links

### Getting Started

```bash
# Install
pip install obskit[all]

# Configure
export OBSKIT_SERVICE_NAME="my-service"
export OBSKIT_ENVIRONMENT="production"
export OBSKIT_METRICS_AUTH_TOKEN="$(openssl rand -base64 32)"
```

### Minimal Code

```python
from obskit import configure, get_logger
from obskit.middleware.fastapi import ObskitMiddleware
from obskit.health import HealthChecker
from obskit.metrics import start_http_server

# Configure
configure(
    service_name="my-service",
    environment="production",
    metrics_auth_enabled=True,
    metrics_auth_token=os.getenv("METRICS_AUTH_TOKEN"),
)

# Start metrics server
start_http_server(port=9090)

# Add middleware to FastAPI
app.add_middleware(ObskitMiddleware)
```

---

## Feature Status

All features are **production stable**:

### Core Observability
| Feature | Status | Guide |
|---------|--------|-------|
| RED Metrics | ✅ Stable | [03_METRICS.md](03_METRICS.md) |
| Golden Signals | ✅ Stable | [03_METRICS.md](03_METRICS.md) |
| USE Metrics | ✅ Stable | [03_METRICS.md](03_METRICS.md) |
| Async Metrics | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Tenant Metrics | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| OTLP Export | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Pushgateway | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Structured Logging | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Distributed Tracing | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |

### Health & Resilience
| Feature | Status | Guide |
|---------|--------|-------|
| Health Checks | ✅ Stable | [04_HEALTH_CHECKS.md](04_HEALTH_CHECKS.md) |
| Circuit Breaker | ✅ Stable | [05_RESILIENCE.md](05_RESILIENCE.md) |
| Distributed CB | ✅ Stable | [05_RESILIENCE.md](05_RESILIENCE.md) |
| Retry & Backoff | ✅ Stable | [05_RESILIENCE.md](05_RESILIENCE.md) |
| Rate Limiting | ✅ Stable | [05_RESILIENCE.md](05_RESILIENCE.md) |
| Load Shedding | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Graceful Degradation | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Self-Healing | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Chaos Engineering | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Failover Coordinator | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |

### SLO & Operations
| Feature | Status | Guide |
|---------|--------|-------|
| SLO Tracking | ✅ Stable | [06_SLO_TRACKING.md](06_SLO_TRACKING.md) |
| Error Budgets | ✅ Stable | [06_SLO_TRACKING.md](06_SLO_TRACKING.md) |
| Alertmanager | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Alert Deduplication | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Runbook Integration | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Incident Timeline | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| SLA Predictor | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Capacity Planner | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |

### Debugging & Analysis
| Feature | Status | Guide |
|---------|--------|-------|
| Flame Graph Profiler | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Query Analyzer | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Dependency Graph | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Root Cause Analyzer | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Error Fingerprinting | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Latency Breakdown | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Hot Path Detector | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |

### Infrastructure
| Feature | Status | Guide |
|---------|--------|-------|
| Connection Pool Metrics | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| DLQ Tracking | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Consumer Lag | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| External API SLA | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Executor Metrics | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Memory/GC Metrics | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Distributed Locking | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |

### Security & Compliance
| Feature | Status | Guide |
|---------|--------|-------|
| Security Hardening | ✅ Stable | [07_SECURITY.md](07_SECURITY.md) |
| PII Redaction | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Audit Trail | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Secrets Detection | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |
| Compliance Reporter | ✅ Stable | [FEATURES.md](../docs/FEATURES.md) |

---

## Production Checklist

### Required

- [ ] Set `service_name` and `environment`
- [ ] Enable metrics authentication
- [ ] Configure health endpoints
- [ ] Set up Prometheus scraping

### Recommended

- [ ] Enable rate limiting
- [ ] Enable sampling (for high-traffic)
- [ ] Configure self-metrics alerting
- [ ] Set up Grafana dashboards

### Advanced

- [ ] Enable distributed circuit breaker
- [ ] Configure SLO tracking
- [ ] Implement PII redaction

---

## Support

- **Documentation:** This folder
- **Examples:** `examples/` folder
- **GitHub Issues:** Bug reports and feature requests
- **Discussions:** Questions and feedback

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.3.0 | 2026-01-19 | 39 new features: Chaos Engineering, Self-Healing, Flame Graph, Root Cause Analysis, and more |
| 1.2.0 | 2026-01-15 | Infrastructure monitoring: Pools, DLQ, Consumer Lag, Memory/GC |
| 1.1.0 | 2026-01-10 | Batch tracking, Business metrics, Performance budgets |
| 1.0.0 | 2026-01-05 | Production stable release |
| 0.1.0 | 2025-12-01 | Initial release |

---

**obskit v1.3.0** - Complete Observability for Python Microservices (52+ Features)
