# Installation

## Requirements

- Python 3.11 or higher
- pip (Python package installer)

## Basic Installation

Install obskit from PyPI:

```bash
pip install obskit
```

This installs the core package with logging capabilities.

## Optional Dependencies

obskit has optional dependencies for different features:

### Metrics (Prometheus)

```bash
pip install obskit[metrics]
```

Includes:
- `prometheus-client` - Prometheus metrics client

### Tracing (OpenTelemetry)

```bash
pip install obskit[tracing]
```

Includes:
- `opentelemetry-api` - OpenTelemetry API
- `opentelemetry-sdk` - OpenTelemetry SDK
- `opentelemetry-exporter-otlp` - OTLP exporter

### All Features

```bash
pip install obskit[all]
```

Installs all optional dependencies.

### Development

For contributing to obskit:

```bash
pip install obskit[dev]
```

Includes:
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `mypy` - Type checking
- `ruff` - Linting and formatting

## Verify Installation

```python
import obskit

print(obskit.__version__)
```

## Next Steps

- [Quick Start](quickstart.md) - Get up and running in 5 minutes
- [Your First App](first-app.md) - Build a complete observable application

