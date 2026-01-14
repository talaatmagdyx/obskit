# Migration Guide

This guide helps you migrate from other observability libraries to obskit.

## Why Migrate to obskit?

obskit provides a unified, opinionated approach to observability that:

- **Reduces boilerplate**: One configuration instead of three
- **Ensures consistency**: Same patterns across metrics, logs, and traces
- **Improves correlation**: Automatic context propagation between all telemetry
- **Simplifies operations**: Pre-built dashboards, alerts, and health checks

## Migration Paths

```{toctree}
:maxdepth: 1

from-prometheus
from-opentelemetry
from-structlog
from-datadog
```

## Quick Comparison

| Feature | Raw Libraries | obskit |
|---------|--------------|--------|
| Setup time | Hours | Minutes |
| Configuration files | 3+ | 1 |
| Correlation IDs | Manual | Automatic |
| Health checks | Custom | Built-in |
| Dashboard templates | None | Included |
| Best practices | Research needed | Enforced |

## General Migration Strategy

1. **Audit current setup**: Document which observability tools you're using
2. **Install obskit**: `pip install obskit[all]`
3. **Configure once**: Replace multiple configurations with obskit.configure()
4. **Migrate incrementally**: Start with one component (e.g., metrics)
5. **Test thoroughly**: Verify telemetry data flows correctly
6. **Remove old libraries**: Once confirmed working

## Getting Help

- [GitHub Issues](https://github.com/talaatmagdyx/obskit/issues)
- [Documentation](https://obskit.readthedocs.io)

