# obskit Technical Documentation

**Version:** 1.0.0  
**Status:** ✅ Production Ready  
**Last Updated:** 2026-01-13

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [00_PRODUCTION_REVIEW.md](00_PRODUCTION_REVIEW.md) | Production readiness review |
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

| Feature | Status | Guide |
|---------|--------|-------|
| RED Metrics | ✅ Stable | [03_METRICS.md](03_METRICS.md) |
| Golden Signals | ✅ Stable | [03_METRICS.md](03_METRICS.md) |
| USE Metrics | ✅ Stable | [03_METRICS.md](03_METRICS.md) |
| Health Checks | ✅ Stable | [04_HEALTH_CHECKS.md](04_HEALTH_CHECKS.md) |
| Circuit Breaker | ✅ Stable | [05_RESILIENCE.md](05_RESILIENCE.md) |
| Distributed CB | ✅ Stable | [05_RESILIENCE.md](05_RESILIENCE.md) |
| SLO Tracking | ✅ Stable | [06_SLO_TRACKING.md](06_SLO_TRACKING.md) |
| Self-Metrics | ✅ Stable | [02_CONFIGURATION.md](02_CONFIGURATION.md) |
| Security | ✅ Stable | [07_SECURITY.md](07_SECURITY.md) |

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
| 1.0.0 | 2026-01-13 | All features stable |
| 0.1.0 | 2024-01-15 | Initial release |

---

**obskit v1.0.0** - Production-Ready Observability for Python Microservices
