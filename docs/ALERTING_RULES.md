# Configurable Alerting Rules

## Overview

obskit provides configurable Prometheus alerting rules that you can customize to match your service requirements. All thresholds, durations, and alert conditions can be adjusted.

## Quick Start

### Generate Default Rules

```python
from obskit.alerts.config import AlertConfig, generate_prometheus_rules

# Use default configuration
config = AlertConfig()
rules_yaml = generate_prometheus_rules(config)

# Write to file
with open("prometheus_rules.yml", "w") as f:
    f.write(rules_yaml)
```

### Customize Thresholds

```python
from obskit.alerts.config import AlertConfig, generate_prometheus_rules

# Create custom configuration
config = AlertConfig(
    error_rate_threshold=0.05,  # 5% instead of default 1%
    critical_error_rate_threshold=0.20,  # 20% instead of default 10%
    latency_p95_threshold=0.3,  # 300ms instead of default 500ms
    latency_p99_threshold=0.8,  # 800ms instead of default 1s
)

rules_yaml = generate_prometheus_rules(config)
```

## Configuration Options

### Error Rate Thresholds

```python
config = AlertConfig(
    error_rate_threshold=0.01,  # 1% - triggers HighErrorRate alert
    critical_error_rate_threshold=0.10,  # 10% - triggers CriticalErrorRate alert
)
```

### Latency Thresholds

```python
config = AlertConfig(
    latency_p95_threshold=0.5,  # 500ms - P95 latency threshold
    latency_p99_threshold=1.0,  # 1s - P99 latency threshold
)
```

### Saturation Thresholds

```python
config = AlertConfig(
    saturation_warning_threshold=0.90,  # 90% - warning level
    saturation_critical_threshold=0.95,  # 95% - critical level
)
```

### Infrastructure Thresholds

```python
config = AlertConfig(
    cpu_utilization_threshold=0.90,  # 90% CPU utilization
    memory_utilization_threshold=0.90,  # 90% memory utilization
    cpu_saturation_threshold=10.0,  # 10 processes waiting
)
```

### Service Degradation Thresholds

```python
config = AlertConfig(
    service_degraded_error_rate=0.05,  # 5% error rate
    service_degraded_latency=1.0,  # 1s latency
)
```

### SLO Thresholds

```python
config = AlertConfig(
    slo_error_budget_threshold=0.001,  # 0.1% error budget
    slo_latency_threshold=0.2,  # 200ms latency SLO
)
```

### Alert Timing

```python
config = AlertConfig(
    alert_intervals={
        "default": 30,  # 30 seconds
        "slo": 30,
    },
    alert_durations={
        "high_error_rate": 300,  # 5 minutes
        "critical_error_rate": 120,  # 2 minutes
        "high_latency_p95": 600,  # 10 minutes
        # ... etc
    },
)
```

## Environment Variables

You can configure alerts via environment variables:

```bash
export OBSKIT_ALERT_ERROR_RATE_THRESHOLD=0.05
export OBSKIT_ALERT_CRITICAL_ERROR_RATE_THRESHOLD=0.20
export OBSKIT_ALERT_LATENCY_P95_THRESHOLD=0.3
export OBSKIT_ALERT_LATENCY_P99_THRESHOLD=0.8
export OBSKIT_ALERT_SATURATION_WARNING_THRESHOLD=0.85
export OBSKIT_ALERT_SATURATION_CRITICAL_THRESHOLD=0.95
```

Then load from environment:

```python
from obskit.alerts.config import AlertConfig

config = AlertConfig.from_env()
rules_yaml = generate_prometheus_rules(config)
```

## Use Cases

### Strict Requirements (Low Latency, High Availability)

```python
config = AlertConfig(
    error_rate_threshold=0.005,  # 0.5%
    critical_error_rate_threshold=0.02,  # 2%
    latency_p95_threshold=0.1,  # 100ms
    latency_p99_threshold=0.2,  # 200ms
    saturation_warning_threshold=0.75,  # 75%
    saturation_critical_threshold=0.85,  # 85%
)
```

### High-Traffic Services (Lenient Thresholds)

```python
config = AlertConfig(
    error_rate_threshold=0.02,  # 2%
    critical_error_rate_threshold=0.20,  # 20%
    latency_p95_threshold=1.0,  # 1s
    latency_p99_threshold=2.0,  # 2s
    saturation_warning_threshold=0.95,  # 95%
    saturation_critical_threshold=0.98,  # 98%
)
```

### Batch Processing (Different Priorities)

```python
config = AlertConfig(
    error_rate_threshold=0.01,  # 1% - errors still important
    latency_p95_threshold=5.0,  # 5s - batch jobs are slower
    latency_p99_threshold=10.0,  # 10s
    queue_depth_threshold=5000,  # Higher queue depth acceptable
)
```

## Integration with Prometheus

1. Generate rules:

```python
from obskit.alerts.config import AlertConfig, generate_prometheus_rules

config = AlertConfig.from_env()  # or custom config
rules_yaml = generate_prometheus_rules(config)

with open("/etc/prometheus/obskit_rules.yml", "w") as f:
    f.write(rules_yaml)
```

2. Configure Prometheus:

```yaml
# prometheus.yml
rule_files:
  - "/etc/prometheus/obskit_rules.yml"
```

3. Reload Prometheus:

```bash
curl -X POST http://prometheus:9090/-/reload
```

## CLI Tool

You can also create a CLI tool:

```python
#!/usr/bin/env python3
"""Generate Prometheus alerting rules."""

import sys
from obskit.alerts.config import AlertConfig, generate_prometheus_rules

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--from-env":
        config = AlertConfig.from_env()
    else:
        config = AlertConfig()
    
    rules_yaml = generate_prometheus_rules(config)
    print(rules_yaml)
```

Usage:

```bash
# Default config
python generate_rules.py > prometheus_rules.yml

# From environment variables
python generate_rules.py --from-env > prometheus_rules.yml
```

## Best Practices

1. **Start with defaults** - The default thresholds are reasonable for most services
2. **Adjust based on SLOs** - Set thresholds based on your actual SLO requirements
3. **Test alerts** - Verify alerts fire correctly with your thresholds
4. **Review regularly** - Adjust thresholds as your service evolves
5. **Document changes** - Keep track of why thresholds were changed

## Available Alerts

### RED Method Alerts
- `HighErrorRate` - Error rate above threshold
- `CriticalErrorRate` - Error rate very high
- `HighLatencyP95` - P95 latency above threshold
- `CriticalLatencyP99` - P99 latency above threshold
- `LowRequestRate` - Request rate below threshold

### Golden Signals Alerts
- `HighSaturation` - Resource saturation warning
- `CriticalSaturation` - Resource saturation critical
- `HighQueueDepth` - Queue depth above threshold

### USE Method Alerts
- `HighCPUUtilization` - CPU utilization high
- `HighMemoryUtilization` - Memory utilization high
- `CPUSaturation` - CPU saturation (processes waiting)
- `InfrastructureErrors` - Infrastructure errors detected

### Service Health Alerts
- `ServiceDown` - Service appears down
- `ServiceDegraded` - Service degraded (high errors + latency)

### SLO-Based Alerts
- `HighErrorBudgetBurnRate` - Error budget being consumed too fast
- `LatencySLOViolation` - Latency SLO violation

## See Also

- [Production Deployment Guide](PRODUCTION_DEPLOYMENT.md)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Alerting Best Practices](https://prometheus.io/docs/practices/alerting/)

