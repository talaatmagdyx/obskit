# Cardinality Protection

Cardinality protection helps prevent high-cardinality labels from exploding your Prometheus metrics storage and causing performance issues.

## The Problem

High cardinality occurs when metric labels have many unique values:

```python
# ❌ BAD: User IDs as labels can have millions of unique values
REQUESTS.labels(user_id=user.id).inc()  # Creates millions of time series!
```

This causes:
- **Memory explosion** in Prometheus
- **Slow queries** due to massive time series
- **Increased costs** for metrics storage
- **Dashboard timeouts**

## The Solution

Use `CardinalityProtector` to limit unique values per label:

```python
from obskit import get_cardinality_protector, protect_label

# Get the global protector
protector = get_cardinality_protector()

# Set limits for high-cardinality labels
protector.set_limit("user_id", 10000)      # Max 10k unique users
protector.set_limit("company_id", 1000)    # Max 1k companies

# Protect label values
safe_user = protector.protect("user_id", user.id, fallback="other")
REQUESTS.labels(user_id=safe_user).inc()
```

When the limit is reached, new values return the fallback instead.

## Quick Start

### Using Convenience Functions

```python
from obskit import protect_label, protect_id

# For string labels
tenant = protect_label("tenant_id", company.tenant_id, fallback="other")

# For ID labels (auto-converts to string)
user = protect_id("user_id", user.id, fallback="anonymous")

# Use protected values in metrics
REQUESTS.labels(tenant=tenant, user=user).inc()
```

### Using CardinalityProtector Directly

```python
from obskit import CardinalityProtector, CardinalityConfig

# Create with custom configuration
config = CardinalityConfig(
    default_limit=1000,      # Default limit for all labels
    ttl_seconds=3600.0,      # Values expire after 1 hour
    label_limits={           # Per-label overrides
        "user_id": 10000,
        "company_id": 500,
    },
)
protector = CardinalityProtector(config)

# Protect values
safe_value = protector.protect(
    label_name="user_id",
    value=user.id,
    fallback="other",
)
```

## Configuration Options

### CardinalityConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `default_limit` | int | 1000 | Default max unique values per label |
| `ttl_seconds` | float | 3600.0 | Time-to-live for tracked values |
| `label_limits` | dict | {} | Per-label limit overrides |

### protect() Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `label_name` | str | Name of the label being protected |
| `value` | T | The value to protect |
| `fallback` | T | Value to use when limit reached |
| `transform` | Callable | Optional function to normalize values |

## Monitoring Cardinality

The protector exposes Prometheus metrics:

```promql
# Rejections per label (high = limit being hit frequently)
rate(obskit_cardinality_rejections_total[5m])

# Current unique values per label
obskit_cardinality_current

# Configured limits
obskit_cardinality_limit
```

### Get Statistics Programmatically

```python
stats = protector.get_stats("user_id")
print(f"Current: {stats['current_count']}/{stats['limit']}")
print(f"Utilization: {stats['utilization']:.1%}")
print(f"At limit: {stats['at_limit']}")
```

## Best Practices

### 1. Identify High-Cardinality Labels

Common offenders:
- User IDs, session IDs
- Request IDs, trace IDs
- Timestamps, dates
- IP addresses
- Email addresses
- File paths

### 2. Set Appropriate Limits

```python
# Good: Different limits based on expected cardinality
protector.set_limit("company_id", 500)     # ~hundreds of companies
protector.set_limit("monitor_id", 5000)    # ~thousands of monitors
protector.set_limit("user_id", 10000)      # ~many users
```

### 3. Use Meaningful Fallbacks

```python
# Good: Descriptive fallback
protect_label("company_id", company_id, fallback="high_cardinality")

# Better: Domain-specific fallback
protect_label("plan_type", plan, fallback="unknown_plan")
```

### 4. Monitor and Alert

```yaml
# Alert when cardinality limit is frequently hit
- alert: HighCardinalityRejections
  expr: rate(obskit_cardinality_rejections_total[5m]) > 10
  labels:
    severity: warning
  annotations:
    summary: "High cardinality limit being hit for {{ $labels.label_name }}"
```

## Thread Safety

`CardinalityProtector` is fully thread-safe:
- Uses `threading.RLock` for all operations
- Safe for concurrent use across multiple threads
- Singleton pattern ensures consistent state

## Example: Real-World Usage

```python
from obskit import (
    get_cardinality_protector,
    protect_label,
    REDMetrics,
)

# Setup at application startup
protector = get_cardinality_protector()
protector.set_limit("company_id", 1000)
protector.set_limit("email_type", 50)

red = REDMetrics("email_service")

def process_email(email: Email):
    # Protect high-cardinality labels
    company = protect_label("company_id", email.company_id, "other")
    email_type = protect_label("email_type", email.type, "other")
    
    with red.track("process_email", company=company, email_type=email_type):
        # Process the email...
        pass
```

## API Reference

```python
# Main classes
from obskit import CardinalityProtector, CardinalityConfig

# Global accessor
from obskit import get_cardinality_protector, reset_cardinality_protector

# Convenience functions
from obskit import protect_label, protect_id
```
