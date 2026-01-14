# Observability Concepts

Understanding **why** each observability concept matters is crucial for building
reliable systems. This guide explains the theory behind obskit's features.

## What is Observability?

**Observability** is the ability to understand a system's internal state by examining
its outputs. Unlike monitoring (which tells you *if* something is wrong), observability
helps you understand *why* something is wrong.

### The Three Pillars

```{mermaid}
flowchart LR
    subgraph Observability
        M[Metrics]
        L[Logs]
        T[Traces]
    end
    
    M --> |"What happened?"| Q[Questions]
    L --> |"Why did it happen?"| Q
    T --> |"Where did it happen?"| Q
```

| Pillar | Purpose | Example Question |
|--------|---------|------------------|
| **Metrics** | Quantitative data over time | "What's our error rate?" |
| **Logs** | Discrete events | "Why did this request fail?" |
| **Traces** | Request flow across services | "Where is the bottleneck?" |

## Why Metrics Matter

### The Problem Without Metrics

Imagine your service is slow. Without metrics, you're debugging blind:

- "Is it slow for everyone or just some users?"
- "When did it start being slow?"
- "Is it getting worse?"

### The Solution: Metrics

Metrics give you quantitative answers:

```
request_duration_seconds{endpoint="/api/users"} = 2.5s (p99)
```

Now you know:
- The p99 latency is 2.5 seconds
- It's specifically the `/api/users` endpoint
- You can compare to yesterday's metrics

## Why Logs Matter

### The Problem Without Structured Logs

```
ERROR: Something went wrong
```

This tells you nothing useful:
- What went wrong?
- Which user was affected?
- What was the request?

### The Solution: Structured Logs

```json
{
  "level": "error",
  "message": "Payment failed",
  "user_id": "12345",
  "order_id": "ord_789",
  "error": "Card declined",
  "trace_id": "abc123"
}
```

Now you can:
- Search by user_id to see their full journey
- Find all orders with payment failures
- Correlate with traces for full context

## Why Traces Matter

### The Problem Without Traces

A request touches 5 services. It's slow. Which service is the problem?

```
User → API Gateway → Auth → Users → Orders → Payments
                     ???      ???     ???      ???
```

### The Solution: Distributed Tracing

```{mermaid}
gantt
    title Request Trace
    dateFormat X
    axisFormat %L ms
    
    section API Gateway
    Receive Request :0, 10
    
    section Auth Service
    Validate Token :10, 50
    
    section Users Service
    Get User :50, 100
    
    section Orders Service
    Create Order :100, 300
    
    section Payments Service
    Process Payment :300, 800
```

Now you can see that Payments took 500ms - that's your bottleneck.

## The RED Method

**R**ate, **E**rrors, **D**uration - the essential metrics for any service.

### Why RED?

These three metrics answer the most common questions:

| Metric | Question | Alert Condition |
|--------|----------|-----------------|
| **Rate** | How much traffic? | Sudden drops = outage |
| **Errors** | What's failing? | Error rate > threshold |
| **Duration** | How fast? | Latency > SLO |

### When to Use RED

Use RED for **request-driven services**:
- APIs
- Web services
- Microservices

```python
from obskit import get_red_metrics

metrics = get_red_metrics(service_name="api")

# All three metrics recorded automatically
with metrics.track_request(endpoint="/users", method="GET"):
    response = get_users()
```

## The Golden Signals

Google's four essential metrics for monitoring services.

### Why Golden Signals?

RED is great, but misses one critical dimension: **Saturation**.

| Signal | Meaning | Why It Matters |
|--------|---------|----------------|
| **Latency** | How long requests take | User experience |
| **Traffic** | How many requests | Capacity planning |
| **Errors** | How many failures | Reliability |
| **Saturation** | How "full" the service is | Predict problems |

### Saturation: The Missing Piece

Your service might have good latency *now*, but if CPU is at 90%, it's about to get bad.

```python
from obskit.metrics import GoldenSignals

signals = GoldenSignals(service_name="api")
signals.set_saturation("cpu", 0.90)  # 90% CPU usage
```

## The USE Method

**U**tilization, **S**aturation, **E**rrors - for infrastructure monitoring.

### Why USE?

USE helps you understand resource constraints:

| Metric | Meaning | Example |
|--------|---------|---------|
| **Utilization** | % of resource used | CPU at 80% |
| **Saturation** | Work waiting | 10 requests queued |
| **Errors** | Error count | 5 disk errors |

### When to Use USE

Use USE for **resources**:
- CPU
- Memory
- Disk
- Network
- Connection pools

```python
from obskit.metrics import USEMetrics

use = USEMetrics(resource_name="db_pool")
use.set_utilization(0.75)  # 75% of connections used
use.set_saturation(5)      # 5 requests waiting
```

## SLOs: Service Level Objectives

### Why SLOs Matter

Without SLOs, "good enough" is subjective:
- Developer: "99% uptime is great!"
- Business: "99% means 3.65 days of downtime per year!"

### The Error Budget Concept

SLOs create **error budgets** - a quantified amount of acceptable unreliability.

```
SLO: 99.9% availability
Error Budget: 0.1% = 8.76 hours/year
```

If you've used 8 hours of your error budget this year, you have 46 minutes left.

```python
from obskit.slo import SLOTracker

slo = SLOTracker(
    name="api_availability",
    target=0.999,  # 99.9%
    window_days=30,
)

# Track success/failure
slo.record_success()
slo.record_failure()

# Check budget
print(f"Error budget remaining: {slo.budget_remaining_percent}%")
```

## PII Redaction

### Why PII Redaction Matters

Logs and traces often contain sensitive data:
- Email addresses
- Phone numbers
- Credit card numbers
- API keys

Without redaction, you risk:
- **GDPR fines** (up to €20M or 4% of revenue)
- **Data breaches** (logs are often less protected)
- **Compliance failures**

### How obskit Helps

```python
from obskit import configure_logging
from obskit.compliance import redact_pii

# Configure logging with PII redaction
logger = configure_logging(
    service_name="api",
    pii_redaction=True,
)

# Input: "User email: john@example.com"
# Output: "User email: [EMAIL REDACTED]"
logger.info(f"User email: {user.email}")
```

## Circuit Breakers

### Why Circuit Breakers Matter

Without circuit breakers, one failing service can cascade:

```{mermaid}
flowchart LR
    A[Service A] --> B[Service B]
    B --> C[Service C]
    C --> D["Database (DOWN)"]
    
    D -.->|Timeout| C
    C -.->|Timeout| B
    B -.->|Timeout| A
    A -.->|503| User
```

Every service waits for timeouts, exhausting resources.

### How Circuit Breakers Help

```{mermaid}
stateDiagram-v2
    [*] --> Closed
    Closed --> Open: 5 failures
    Open --> HalfOpen: After 30s
    HalfOpen --> Closed: Success
    HalfOpen --> Open: Failure
```

When open, requests fail **immediately** without waiting:

```python
from obskit import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
)

async with breaker:
    # Fails fast when circuit is open
    response = await call_external_api()
```

## Multi-Tenancy

### Why Tenant Metrics Matter

In multi-tenant systems, aggregate metrics hide problems:

```
Overall error rate: 0.5% ✓
Tenant A error rate: 0.1% ✓
Tenant B error rate: 15% ✗  ← Hidden!
```

### Per-Tenant Observability

```python
from obskit.metrics import TenantREDMetrics

metrics = TenantREDMetrics(service_name="api")

# Metrics labeled with tenant_id
with metrics.track_request(
    endpoint="/users",
    method="GET",
    tenant_id="tenant_b",
):
    process_request()
```

Now you can:
- Alert when any tenant's error rate spikes
- Bill tenants based on usage
- Identify noisy neighbors

## Summary

| Concept | When to Use | Why |
|---------|-------------|-----|
| **RED** | Request-driven services | Core service health |
| **Golden Signals** | Services with resource limits | Predict saturation |
| **USE** | Infrastructure/resources | Capacity planning |
| **SLOs** | Customer-facing services | Define "good enough" |
| **PII Redaction** | Any service with user data | Compliance |
| **Circuit Breakers** | External dependencies | Fault isolation |
| **Tenant Metrics** | Multi-tenant services | Per-customer visibility |

## Next Steps

- **[Metrics Guide](metrics.md)** - Implement RED, Golden Signals, and USE
- **[SLO Tracking](slo.md)** - Define and track service level objectives
- **[PII Redaction](pii.md)** - Protect sensitive data

