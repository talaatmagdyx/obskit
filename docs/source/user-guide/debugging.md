# Debugging & Analysis (v1.3.0)

obskit v1.3.0 includes powerful debugging and analysis tools.

## Flame Graph Profiler

Profile CPU and memory usage with visualization.

### Basic Usage

```python
from obskit import (
    FlameGraphProfiler,
    get_flamegraph_profiler,
    profile_function
)

profiler = get_flamegraph_profiler()

# Profile a code section
with profiler.profile("order_processing"):
    result = process_orders(orders)

# Get results
result = profiler.get_result("order_processing")
print(f"Duration: {result.duration_seconds}s")
print(f"Total function calls: {result.total_calls}")

# Top functions by time
for func_name, time_ms, calls in result.top_functions[:10]:
    print(f"  {func_name}: {time_ms:.2f}ms ({calls} calls)")
```

### Export Visualizations

```python
# Export as SVG flame graph
profiler.export_svg("order_processing.svg")

# Export as JSON (for custom visualization)
profiler.export_json("order_processing.json")
```

### Decorator Usage

```python
@profile_function
def expensive_computation():
    # This function will be profiled
    return compute_result()

# Or with custom name
@profile_function(name="custom_computation")
def my_function():
    pass
```

## Query Analyzer

Analyze SQL queries for optimization opportunities.

### Basic Usage

```python
from obskit import (
    QueryAnalyzer,
    QueryType,
    get_query_analyzer
)

analyzer = get_query_analyzer()

# Analyze a query
analysis = analyzer.analyze(
    query="SELECT * FROM users WHERE email = 'test@example.com'",
    explain_output=db.execute("EXPLAIN " + query)
)

print(f"Query type: {analysis.query_type}")
print(f"Estimated cost: {analysis.estimated_cost}")

# Check for issues
if analysis.issues:
    print("Issues found:")
    for issue in analysis.issues:
        print(f"  - [{issue.severity}] {issue.message}")

# Get suggestions
if analysis.suggestions:
    print("Suggestions:")
    for suggestion in analysis.suggestions:
        print(f"  - {suggestion}")
```

### Automatic Slow Query Tracking

```python
# Enable automatic slow query tracking
analyzer.enable_slow_query_tracking(threshold_ms=100)

# Queries slower than 100ms are automatically analyzed and logged
```

### Common Issues Detected

- Missing indexes
- Full table scans
- N+1 query patterns
- Unnecessary columns (SELECT *)
- Large result sets without limits

## Root Cause Analyzer

Automated incident root cause analysis.

### Report Anomalies

```python
from obskit import (
    RootCauseAnalyzer,
    Anomaly,
    AnomalySeverity,
    get_root_cause_analyzer
)

rca = get_root_cause_analyzer()

# Report an anomaly
rca.report_anomaly(
    service="payment-service",
    metric="error_rate",
    current_value=0.15,
    expected_value=0.01,
    severity=AnomalySeverity.HIGH
)

rca.report_anomaly(
    service="database",
    metric="latency_p99",
    current_value=500,
    expected_value=50,
    severity=AnomalySeverity.MEDIUM
)
```

### Analyze Incident

```python
from datetime import datetime, timedelta

# Analyze root cause
result = rca.analyze(
    incident_id="INC-12345",
    affected_services=["payment-service", "order-service"],
    time_range=(
        datetime.now() - timedelta(hours=1),
        datetime.now()
    )
)

print(f"Root cause: {result.root_cause}")
print(f"Confidence: {result.confidence:.2%}")

print("Contributing factors:")
for factor in result.contributing_factors:
    print(f"  - {factor.description}")
    print(f"    Correlation: {factor.correlation:.2%}")
```

## Error Fingerprinting

Automatically group similar errors.

### Fingerprint Errors

```python
from obskit import (
    ErrorFingerprinter,
    get_error_fingerprinter,
    get_fingerprint,
    get_error_group
)

fingerprinter = get_error_fingerprinter()

try:
    risky_operation()
except Exception as e:
    # Generate fingerprint
    fingerprint = fingerprinter.fingerprint(e)
    
    print(f"Error fingerprint: {fingerprint.hash}")
    print(f"Error group: {fingerprint.group_id}")
    
    # Log with fingerprint for grouping
    logger.error(
        "operation_failed",
        fingerprint=fingerprint.hash,
        group_id=fingerprint.group_id,
        exc_info=True
    )
```

### View Error Groups

```python
# Get statistics for an error group
group = get_error_group(fingerprint.group_id)

print(f"Error group: {group.group_id}")
print(f"Total occurrences: {group.count}")
print(f"First seen: {group.first_seen}")
print(f"Last seen: {group.last_seen}")
print(f"Sample stack trace:\n{group.sample_stack}")
```

## Latency Breakdown

Track latency by phase.

### Basic Usage

```python
from obskit import LatencyBreakdown, track_breakdown

breakdown = LatencyBreakdown("api_request")

# Track each phase
with breakdown.phase("authentication"):
    await authenticate_user(token)

with breakdown.phase("authorization"):
    await check_permissions(user, resource)

with breakdown.phase("database"):
    data = await fetch_data(query)

with breakdown.phase("serialization"):
    response = serialize(data)

# Get breakdown summary
summary = breakdown.get_summary()
print(f"Total latency: {summary.total_ms:.2f}ms")

for phase in summary.phases:
    bar = "█" * int(phase.percentage / 5)
    print(f"  {phase.name}: {phase.duration_ms:.2f}ms ({phase.percentage:.1f}%) {bar}")
```

### Output Example

```
Total latency: 150.00ms
  authentication: 10.00ms (6.7%) █
  authorization: 5.00ms (3.3%) █
  database: 120.00ms (80.0%) ████████████████
  serialization: 15.00ms (10.0%) ██
```

### Decorator Usage

```python
@track_breakdown("process_order")
async def process_order(order):
    # Phases tracked automatically from function calls
    pass
```

## Hot Path Detector

Identify critical code paths.

### Track Paths

```python
from obskit import (
    HotPathDetector,
    track_path,
    get_hot_path_detector
)

detector = get_hot_path_detector()

@track_path("order_creation")
async def create_order(order_data):
    with detector.track("validation"):
        validate(order_data)
    
    with detector.track("persistence"):
        await save_order(order_data)
    
    with detector.track("notification"):
        await notify_customer(order_data)
```

### Get Hot Paths

```python
# Get top 10 hot paths
hot_paths = detector.get_hot_paths(top_n=10)

for path in hot_paths:
    print(f"{path.name}:")
    print(f"  Total time: {path.total_time_ms:.2f}ms")
    print(f"  Calls: {path.call_count}")
    print(f"  Avg time: {path.avg_time_ms:.2f}ms")
    print(f"  Max time: {path.max_time_ms:.2f}ms")
```

## Dependency Graph

Visualize service dependencies.

### Build Graph

```python
from obskit import (
    DependencyGraph,
    get_dependency_graph
)

graph = get_dependency_graph()

# Register services and dependencies
graph.register_service(
    name="order-service",
    dependencies=["user-service", "inventory-service", "payment-service"]
)

graph.register_service(
    name="user-service",
    dependencies=["auth-service", "database"]
)

graph.register_service(
    name="payment-service",
    dependencies=["payment-gateway", "database"]
)
```

### Visualize

```python
# Generate visualization
viz = graph.generate_visualization()

# Export as DOT (for Graphviz)
viz.export_dot("dependencies.dot")

# Export as Mermaid (for documentation)
viz.export_mermaid("dependencies.md")
```

### Check Health Propagation

```python
# See how unhealthy services affect others
health_status = graph.get_health_status()

for service, status in health_status.items():
    print(f"{service}: {status.state}")
    if status.affected_by:
        print(f"  Affected by: {', '.join(status.affected_by)}")
```

## Best Practices

### 1. Profile in Production (Carefully)

```python
# Use sampling in production
if random.random() < 0.01:  # 1% of requests
    with profiler.profile("request_processing"):
        process_request()
else:
    process_request()
```

### 2. Correlate with Traces

```python
from obskit import get_correlation_id

# Include correlation ID in analysis
rca.report_anomaly(
    service="payment-service",
    metric="error_rate",
    correlation_id=get_correlation_id(),
    # ...
)
```

### 3. Set Up Alerting

```python
# Alert on hot path performance degradation
if path.avg_time_ms > path.baseline_avg_time_ms * 2:
    alert(f"Hot path {path.name} is 2x slower than baseline")
```

### 4. Regular Analysis

```python
# Schedule regular root cause analysis
@scheduler.scheduled_job('cron', hour=9)
def daily_analysis():
    result = rca.analyze_daily_anomalies()
    send_report(result)
```

## Next Steps

- [Advanced Resilience](advanced-resilience.md) - Chaos engineering, self-healing
- [Infrastructure Monitoring](infrastructure.md) - Pool metrics, DLQ tracking
- [Complete Feature Reference](../features/complete-reference.md) - All features
