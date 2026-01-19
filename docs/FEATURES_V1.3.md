# ObsKit v1.3 - Complete Feature Documentation

This document provides comprehensive documentation for all 52 features in ObsKit v1.3.

## Table of Contents

1. [Debugging & Analysis](#debugging--analysis)
2. [Resilience & Reliability](#resilience--reliability)
3. [Performance](#performance)
4. [Security & Compliance](#security--compliance)
5. [Operations](#operations)
6. [Deployment & Testing](#deployment--testing)
7. [Infrastructure](#infrastructure)

---

## Debugging & Analysis

### 1. Flame Graph Profiler

CPU and memory profiling with flame graph visualization export.

```python
from obskit import FlameGraphProfiler, profile_function, get_flamegraph_profiler

# Create profiler
profiler = FlameGraphProfiler()

# Profile a code block
with profiler.profile("expensive_operation"):
    result = process_data(large_dataset)

# Get results
result = profiler.get_profile("expensive_operation")
print(f"Duration: {result.duration_seconds}s")
print(f"Top functions: {result.top_functions[:5]}")

# Export for visualization
collapsed = profiler.export_collapsed("expensive_operation")
# Use with flamegraph.pl or speedscope.app

# Decorator usage
@profile_function("my_function")
def my_function():
    return heavy_computation()
```

### 2. Query Plan Analyzer

SQL query analysis and optimization suggestions.

```python
from obskit import QueryAnalyzer, get_query_analyzer

analyzer = QueryAnalyzer("my_database", slow_query_threshold_ms=100.0)

# Analyze a query
analysis = analyzer.analyze(
    "SELECT * FROM users WHERE email LIKE '%@example.com'",
    actual_time_ms=250.0,
)

print(f"Query type: {analysis.query_type}")
print(f"Tables: {analysis.tables_accessed}")
print(f"Needs optimization: {analysis.needs_optimization}")
print(f"Suggestions: {analysis.suggestions}")

# Get slow queries
slow = analyzer.get_slow_queries()
for q in slow:
    print(f"Slow query hash: {q.query_hash}, time: {q.actual_time_ms}ms")
```

### 3. Dependency Graph Visualizer

Service dependency visualization and health tracking.

```python
from obskit import DependencyGraph, DependencyType, get_dependency_graph

graph = DependencyGraph("my-service")

# Register dependencies
graph.add_dependency("postgres", DependencyType.DATABASE, is_critical=True)
graph.add_dependency("redis", DependencyType.CACHE)
graph.add_dependency("user-service", DependencyType.SERVICE)

# Record calls (automatically tracks latency, errors)
graph.record_call("postgres", latency_ms=5.0, success=True)
graph.record_call("user-service", latency_ms=50.0, success=False)

# Check health
if not graph.is_healthy():
    unhealthy = graph.get_unhealthy_dependencies()
    for dep in unhealthy:
        print(f"Unhealthy: {dep.name}, error_rate: {dep.error_rate}")

# Get visualization data for dashboard
viz = graph.get_visualization_data()
```

### 4. Root Cause Analyzer

Automated incident root cause analysis.

```python
from obskit import RootCauseAnalyzer, AnomalySeverity, AnomalyType, get_root_cause_analyzer

analyzer = RootCauseAnalyzer("my-service")

# Record anomalies
analyzer.record_anomaly(
    description="High latency on API endpoint",
    component="api-gateway",
    anomaly_type=AnomalyType.LATENCY,
    severity=AnomalySeverity.HIGH,
    value=500.0,
    threshold=200.0,
)

analyzer.record_anomaly(
    description="Database connections exhausted",
    component="postgres",
    severity=AnomalySeverity.CRITICAL,
)

# Analyze
result = analyzer.analyze()

print(f"Probable cause: {result.probable_cause}")
print(f"Confidence: {result.confidence}")
print(f"Affected components: {result.affected_components}")
print(f"Suggestions: {result.suggestions}")
```

---

## Resilience & Reliability

### 5. Chaos Engineering Hooks

Failure injection for testing.

```python
from obskit import (
    ChaosEngine, 
    InjectionType, 
    chaos_injection,
    enable_chaos,
    disable_chaos,
    get_chaos_engine,
)

# Create engine (disabled in production by default)
engine = ChaosEngine(enabled=True, safe_mode=True)

# Add experiments
engine.add_experiment(
    name="api-latency",
    injection_type=InjectionType.LATENCY,
    probability=0.1,  # 10% of requests
    latency_ms=500,
    target_components=["api"],
)

engine.add_experiment(
    name="db-errors",
    injection_type=InjectionType.ERROR,
    probability=0.05,
    error_message="Database connection failed",
    duration_minutes=30,
)

# Check if should inject
if engine.should_inject("api-latency", component="api"):
    engine.inject_latency("api-latency")

# Decorator usage
@chaos_injection("api-latency")
def api_call():
    return fetch_data()

# Global enable/disable
enable_chaos()
disable_chaos()
```

### 6. Failover Coordinator

Primary/backup failover management.

```python
from obskit import FailoverCoordinator, FailoverState, get_failover_coordinator

coordinator = FailoverCoordinator(
    "database",
    failure_threshold=3,
    recovery_threshold=5,
)

# Register endpoints
coordinator.register_primary(
    name="postgres-primary",
    address="db-primary.internal:5432",
    health_check=lambda: check_db_connection("primary"),
)
coordinator.register_backup(
    name="postgres-replica",
    address="db-replica.internal:5432",
    health_check=lambda: check_db_connection("replica"),
)

# Get current active endpoint
address = coordinator.get_active_address()
connection = connect_to_db(address)

# Automatic health-based failover
coordinator.check_health()  # Call periodically

# Manual failover
coordinator.force_failover("Maintenance window")
coordinator.force_recovery()

# Get status
status = coordinator.get_status()
print(f"Current state: {status['state']}")
```

### 7. Graceful Degradation Manager

Feature degradation under load.

```python
from obskit import DegradationManager, DegradationLevel, get_degradation_manager

manager = DegradationManager("my-service", auto_degrade=True)

# Register degradable features
manager.register_feature(
    name="recommendations",
    priority=50,  # Lower = more important
    degradation_threshold=50,  # Degrade at level 50+
)
manager.register_feature(
    name="search",
    priority=30,
    degradation_threshold=70,
)
manager.register_feature(
    name="core_api",
    priority=10,
    degradation_threshold=90,
    dependencies=[],
)

# Check if feature is enabled
if manager.is_enabled("recommendations"):
    show_recommendations()
else:
    show_static_content()

# Execute with fallback
result = manager.execute_with_fallback(
    "search",
    primary=lambda: full_text_search(query),
    fallback=lambda: simple_search(query),
)

# Manual degradation
manager.set_level(DegradationLevel.HIGH)  # 75
manager.degrade_feature("recommendations", reason="High load")
manager.restore_feature("recommendations")
```

### 8. Self-Healing Triggers

Automatic remediation.

```python
from obskit import SelfHealingEngine, HealingResult, get_self_healing_engine

engine = SelfHealingEngine(enabled=True, dry_run=False)

# Register healing triggers
engine.register_trigger(
    name="restart-on-oom",
    condition=lambda: get_memory_usage() > 90,
    action=lambda: restart_service(),
    description="Restart service when memory > 90%",
    cooldown_minutes=10,
    max_executions_per_hour=3,
)

engine.register_trigger(
    name="clear-cache-on-high-latency",
    condition=lambda: get_p99_latency() > 1000,
    action=lambda: clear_caches(),
    cooldown_minutes=5,
)

# Evaluate all triggers (call periodically)
events = engine.evaluate()

for event in events:
    print(f"Trigger: {event.trigger_name}, Result: {event.result}")
    if event.result == HealingResult.FAILED:
        alert_oncall(f"Self-healing failed: {event.error}")
```

---

## Performance

### 9. Adaptive Sampling

Dynamic trace/log sampling based on load.

```python
from obskit import AdaptiveSampler, get_adaptive_sampler

sampler = AdaptiveSampler(
    name="trace-sampler",
    base_rate=0.1,  # 10% base sampling
)

# Configure boosts for important scenarios
sampler.config.error_boost_factor = 10.0  # Sample 100% of errors
sampler.config.slow_threshold_ms = 500.0
sampler.config.slow_boost_factor = 5.0  # 50% of slow requests

# Check if should sample
if sampler.should_sample(
    has_error=is_error,
    latency_ms=latency,
    priority=is_important_request,
):
    record_trace()
    record_detailed_logs()

# Set operation-specific rates
sampler.set_operation_rate("health-check", 0.01)  # 1% for health checks
sampler.set_operation_rate("critical-api", 1.0)   # 100% for critical APIs

# Get stats
stats = sampler.get_stats()
print(f"Sample ratio: {stats.sample_ratio}")
```

### 10. Hot Path Detector

Identify critical code paths.

```python
from obskit import HotPathDetector, track_path, get_hot_path_detector

detector = HotPathDetector(hot_path_threshold=100)  # 100+ calls = hot

# Track code paths
with detector.track("api.user.get"):
    user = get_user(user_id)

with detector.track("db.query.select"):
    results = db.execute(query)

# Decorator usage
@track_path("process.order")
def process_order(order):
    return order.process()

# Get hot paths
hot_paths = detector.get_hot_paths()
for path in hot_paths:
    print(f"Hot path: {path.path}")
    print(f"  Calls: {path.call_count}")
    print(f"  Avg time: {path.avg_time_ms}ms")
    print(f"  Impact score: {path.impact_score}")

# Get call graph
graph = detector.get_call_graph()
```

### 11. Resource Predictor

Predict resource exhaustion.

```python
from obskit import ResourcePredictor, get_resource_predictor

predictor = ResourcePredictor(
    min_data_points=10,
    default_threshold=85.0,
)

# Record metrics (call regularly)
predictor.record("memory", get_memory_percent())
predictor.record("disk", get_disk_percent())
predictor.record("connections", get_connection_count())

# Set custom thresholds
predictor.set_threshold("connections", 900)  # Max 1000 connections

# Predict future usage
forecast = predictor.predict("memory", hours_ahead=24)

if forecast and forecast.will_exceed_threshold:
    print(f"Memory will exceed {forecast.threshold}% in {forecast.hours_until_threshold}h")
    print(f"Current: {forecast.current_value}%, Predicted: {forecast.predicted_value}%")
    alert_capacity_team()

# Get all at-risk resources
at_risk = predictor.get_at_risk_resources()
```

### 12. Auto-Scaling Metrics

Kubernetes HPA metrics provider.

```python
from obskit import AutoScalingMetrics, ScalingDirection, get_autoscaling_metrics

scaling = AutoScalingMetrics(
    "my-service",
    config=ScalingConfig(
        min_replicas=2,
        max_replicas=20,
        target_cpu_utilization=70.0,
        target_queue_depth_per_pod=100,
    ),
)

# Record metrics
scaling.set_replicas(current_pod_count)
scaling.record_queue_depth(rabbitmq.get_queue_depth())
scaling.record_requests_per_second(get_rps())

# Record pod metrics
for pod in get_pods():
    scaling.record_pod_metrics(
        pod_name=pod.name,
        cpu_utilization=pod.cpu_percent,
        memory_utilization=pod.memory_percent,
        request_count=pod.requests,
    )

# Get scaling recommendation
rec = scaling.get_recommendation()

print(f"Current: {rec.current_replicas}, Recommended: {rec.target_replicas}")
print(f"Direction: {rec.direction}, Reason: {rec.reason}")

# Get metrics for Kubernetes HPA custom metrics
hpa_metrics = scaling.get_metrics_for_hpa()
```

---

## Security & Compliance

### 13. Audit Trail

Immutable audit logging.

```python
from obskit import AuditTrail, AuditAction, AuditResult, get_audit_trail

audit = AuditTrail("my-service")

# Record audit events
audit.record(
    action=AuditAction.CREATE,
    actor="user:john@example.com",
    resource="order:12345",
    resource_type="order",
    details={"amount": 99.99, "items": 3},
    ip_address=request.remote_addr,
)

audit.record(
    action=AuditAction.DELETE,
    actor="admin:jane@example.com",
    resource="user:67890",
    resource_type="user",
    result=AuditResult.DENIED,
    reason="Insufficient permissions",
)

# Query audit logs
from obskit.audit import AuditQuery

query = AuditQuery(
    actor="user:john@example.com",
    action="create",
    start_time=datetime.utcnow() - timedelta(days=7),
)
entries = audit.query(query)

# Verify chain integrity
is_valid, error = audit.verify_chain()
if not is_valid:
    alert_security_team(f"Audit log tampering detected: {error}")

# Export for compliance
export = audit.export_for_compliance(
    start_time=month_start,
    end_time=month_end,
)
```

### 14. Secrets Detection

Detect and redact secrets in logs.

```python
from obskit import (
    SecretsDetector,
    SecretType,
    redact_secrets,
    scan_for_secrets,
    get_secrets_detector,
)

detector = SecretsDetector()

# Scan text for secrets
result = detector.scan(log_message)

if result.has_secrets:
    print(f"Found secrets: {result.detected_types}")
    # Don't log the original message!

# Redact secrets
safe_message = detector.redact(log_message)
logger.info(safe_message)  # Safe to log

# Combined scan and redact
safe_message, result = detector.scan_and_redact(log_message)

# Check if safe to log
if detector.is_safe(user_input):
    log_user_input(user_input)

# Add custom pattern
detector.add_pattern(
    name="Internal API Key",
    pattern=r"INTERNAL-[A-Z0-9]{32}",
    secret_type=SecretType.API_KEY,
)

# Global helper functions
safe_text = redact_secrets(text)
result = scan_for_secrets(text)
```

### 15. Compliance Reporter

GDPR/SOC2/HIPAA compliance checks.

```python
from obskit import (
    ComplianceReporter,
    ComplianceFramework,
    ComplianceCheck,
    get_compliance_reporter,
)

reporter = ComplianceReporter("my-service")

# Run framework-specific checks
gdpr_report = reporter.check_gdpr()
soc2_report = reporter.check_soc2()
hipaa_report = reporter.check_hipaa()

print(f"GDPR Score: {gdpr_report.score}%")
print(f"Passed: {gdpr_report.passed}/{gdpr_report.total_checks}")

# Check all frameworks
all_reports = reporter.check_all()

# Add custom compliance check
custom_check = ComplianceCheck(
    check_id="custom-001",
    name="Encryption at Rest",
    description="Verify all data is encrypted at rest",
    framework=ComplianceFramework.CUSTOM,
    check_func=lambda: verify_encryption(),
    severity="high",
    remediation="Enable disk encryption",
)
reporter.add_check(custom_check)

# Get remediation plan for failures
plan = reporter.get_remediation_plan()
for item in plan:
    print(f"Fix required: {item['name']}")
    print(f"  Remediation: {item['remediation']}")
```

---

## Operations

### 16. Runbook Integration

Link alerts to runbooks.

```python
from obskit import RunbookManager, get_runbook_manager

manager = RunbookManager()

# Register runbooks
manager.register(
    runbook_id="high-memory",
    title="High Memory Usage Alert",
    description="Steps to diagnose and resolve high memory alerts",
    alert_patterns=["HighMemory*", "OOMKill*"],
    tags=["memory", "critical"],
    steps=[
        {
            "title": "Check current memory usage",
            "description": "Identify which processes are using memory",
            "command": "kubectl top pods -n production",
            "expected_outcome": "Pod memory usage list",
        },
        {
            "title": "Check for memory leaks",
            "description": "Review recent deployments and logs",
            "command": "kubectl logs -l app=myapp --tail=1000 | grep -i memory",
        },
        {
            "title": "Scale if needed",
            "command": "kubectl scale deployment myapp --replicas=5",
        },
    ],
)

# Find runbook for an alert
runbook = manager.get_for_alert("HighMemoryUsage")
if runbook:
    print(f"Use runbook: {runbook.title}")
    print(f"Steps: {len(runbook.steps)}")

# Start execution tracking
execution = manager.start_execution(
    runbook_id="high-memory",
    alert_name="HighMemoryUsage",
    executor="oncall@example.com",
)

# Update progress
manager.update_execution(
    execution.execution_id,
    current_step=2,
    step_note="Found memory leak in new deployment",
)

# Complete or escalate
manager.complete_execution(execution.execution_id, resolved=True)
# or
manager.escalate_execution(execution.execution_id, "Need database team")
```

### 17. Incident Timeline Builder

Construct incident timelines.

```python
from obskit import (
    IncidentTimeline,
    IncidentManager,
    IncidentStatus,
    EventCategory,
    get_incident_manager,
)

# Create incident
timeline = IncidentTimeline(
    incident_id="INC-2024-001",
    title="Production API Outage",
    severity="high",
)

# Add events
timeline.add_event(
    description="PagerDuty alert received",
    category=EventCategory.ALERT,
    actor="alertmanager",
)

timeline.add_event(
    description="On-call engineer acknowledged",
    category=EventCategory.ACTION,
    actor="john@example.com",
)

timeline.add_event(
    description="Identified database connection pool exhaustion",
    category=EventCategory.DISCOVERY,
    actor="john@example.com",
)

# Update status
timeline.update_status(IncidentStatus.INVESTIGATING, "Checking database")
timeline.update_status(IncidentStatus.IDENTIFIED)

# Add metadata
timeline.add_responder("jane@example.com")
timeline.add_affected_service("api-gateway")
timeline.add_affected_service("user-service")
timeline.set_root_cause("Connection pool leak in v2.1.0")
timeline.set_resolution("Rolled back to v2.0.0, hotfix deployed")

timeline.update_status(IncidentStatus.RESOLVED)

# Generate reports
report = timeline.generate_report()
postmortem = timeline.generate_postmortem()
```

### 18. SLA Breach Predictor

Predict SLA violations before they happen.

```python
from obskit import SLAPredictor, get_sla_predictor

predictor = SLAPredictor()

# Define SLAs
predictor.set_sla(
    name="api_latency_p99",
    target_value=500.0,  # 500ms
    percentile=99,
    comparison="less_than",
)

predictor.set_sla(
    name="availability",
    target_value=99.9,
    comparison="greater_than",
)

# Record metrics (call regularly)
predictor.record("api_latency_p99", get_p99_latency())
predictor.record("availability", calculate_availability())

# Assess risk
risk = predictor.assess_risk("api_latency_p99")

if risk and risk.breach_likely:
    print(f"SLA breach predicted in {risk.hours_until_breach} hours!")
    print(f"Risk score: {risk.risk_score}%")
    print(f"Trend: {risk.trend}")
    print(f"Suggestions: {risk.suggestions}")
    
    # Take preemptive action
    scale_up_infrastructure()

# Get all at-risk SLAs
at_risk = predictor.get_at_risk_slas(threshold=50.0)
```

### 19. Capacity Planner

Plan future capacity needs.

```python
from obskit import CapacityPlanner, get_capacity_planner

planner = CapacityPlanner()

# Define resources
planner.add_resource(
    name="database_storage",
    current_value=500,
    max_value=1000,
    unit="GB",
    growth_rate_per_month=0.08,  # 8% monthly growth
    warning_threshold=70.0,
    critical_threshold=85.0,
    cost_per_unit=0.10,  # $0.10 per GB
)

planner.add_resource(
    name="api_instances",
    current_value=5,
    max_value=20,
    growth_rate_per_month=0.15,
    cost_per_unit=100.0,  # $100 per instance
)

# Update resource values
planner.update_resource("database_storage", current_value=520)

# Generate capacity plan
plan = planner.project(months_ahead=12)

print(f"Planning horizon: {plan.projection_months} months")
print(f"Total estimated cost: ${plan.total_estimated_cost}")
print(f"Action required: {plan.action_required}")

if plan.action_required:
    print(f"Action needed by: {plan.action_required_by}")
    
for projection in plan.projections:
    print(f"\n{projection.resource_name}:")
    print(f"  Current: {projection.current_usage}")
    print(f"  Projected: {projection.projected_usage}")
    print(f"  Days until critical: {projection.days_until_critical}")
    print(f"  Recommendation: {projection.recommendation}")
```

---

## Deployment & Testing

### 20. Feature Flag Observability

Track feature flag usage and impact.

```python
from obskit import FeatureFlagTracker, get_feature_flag_tracker

tracker = FeatureFlagTracker()

# Register flags
tracker.register_flag(
    name="new_checkout_flow",
    enabled=True,
    rollout_percent=25.0,
    description="New streamlined checkout",
)

# Record evaluations (integrate with your feature flag system)
tracker.record_evaluation(
    flag_name="new_checkout_flow",
    enabled=is_flag_enabled,
    user_id=user.id,
    context={"region": user.region, "plan": user.plan},
)

# Get metrics
metrics = tracker.get_flag_metrics("new_checkout_flow")

print(f"Total evaluations: {metrics.total_evaluations}")
print(f"Unique users: {metrics.unique_users}")
print(f"Enabled percent: {metrics.enabled_percent}%")

# Get all flag metrics
all_metrics = tracker.get_all_metrics()
for name, m in all_metrics.items():
    print(f"{name}: {m.enabled_percent}% enabled")
```

### 21. Deployment Tracking

Canary/Blue-Green/A/B deployment metrics.

```python
from obskit import DeploymentTracker, DeploymentType, get_deployment_tracker

tracker = DeploymentTracker(
    error_rate_threshold=0.05,  # 5% error rate threshold
    latency_threshold_ms=500,
    min_requests_for_decision=100,
)

# Start a canary deployment
tracker.start_canary(
    version="v2.0.0",
    traffic_percent=5.0,
    baseline_version="v1.9.0",
)

# Set baseline metrics for comparison
tracker.set_baseline_metrics(
    version="v1.9.0",
    error_rate=0.01,
    latency_p50=50.0,
    latency_p99=200.0,
)

# Record requests to canary
tracker.record_request(
    version="v2.0.0",
    latency_ms=response_time,
    success=response.ok,
)

# Check canary health
if tracker.is_canary_healthy("v2.0.0"):
    # Increase traffic
    tracker.increase_traffic("v2.0.0", 25.0)
else:
    # Rollback
    tracker.rollback("v2.0.0", reason="Error rate too high")

# Get deployment status
deployment = tracker.get_deployment("v2.0.0")
print(f"Status: {deployment.status}")
print(f"Traffic: {deployment.traffic_percent}%")
print(f"Error rate: {deployment.metrics.error_rate}")

# Complete deployment
tracker.complete_deployment("v2.0.0")
```

---

## Infrastructure

### 22. Connection Pool Metrics

Track database/Redis/RabbitMQ connection pools.

```python
from obskit import ConnectionPoolTracker

tracker = ConnectionPoolTracker("postgres", max_size=20)

# Update pool state
tracker.set_size(active=15, idle=5, waiting=0)

# Track checkout
with tracker.track_checkout():
    conn = pool.get_connection()
    execute_query(conn)
    pool.return_connection(conn)

# Record errors
tracker.record_error("connection_timeout")

# Get metrics
metrics = tracker.get_metrics()
print(f"Utilization: {metrics['utilization']}%")
```

### 23. Dead Letter Queue (DLQ) Metrics

Track DLQ messages.

```python
from obskit import DLQTracker

tracker = DLQTracker("orders-dlq")

# Record DLQ message
tracker.record(
    message_id="msg-123",
    reason="parse_error",
    original_queue="orders",
    error_message="Invalid JSON",
    message_age_seconds=300,
)

# Get stats
stats = tracker.get_stats()
print(f"Total DLQ messages: {stats['total']}")
print(f"Top reasons: {stats['by_reason']}")
```

### 24. External API SLA Tracking

Monitor external API dependencies.

```python
from obskit import ExternalAPISLATracker

tracker = ExternalAPISLATracker()

# Define expected SLAs
tracker.set_sla("stripe-api", availability=99.9, latency_p99=500)
tracker.set_sla("sendgrid-api", availability=99.5, latency_p99=1000)

# Record calls
tracker.record_call("stripe-api", latency_ms=150, success=True)
tracker.record_call("stripe-api", latency_ms=5000, success=False)

# Get compliance report
report = tracker.get_compliance_report("stripe-api")
print(f"Availability: {report.availability}% (target: {report.target_availability}%)")
```

### 25. Thread Pool Executor Metrics

Track ThreadPoolExecutor performance.

```python
from obskit import ExecutorTracker

tracker = ExecutorTracker("background-tasks", max_workers=10)

# Submit tracked task
future = tracker.submit(process_task, task_data)
result = future.result()

# Get metrics
metrics = tracker.get_metrics()
print(f"Queue size: {metrics['queue_size']}")
print(f"Active threads: {metrics['active_threads']}")
print(f"Tasks completed: {metrics['completed_tasks']}")
```

### 26. Consumer Lag Tracking

Monitor message consumer lag.

```python
from obskit import ConsumerLagTracker

tracker = ConsumerLagTracker()

# Update lag
tracker.update_lag(
    queue="orders",
    consumer_group="order-processor",
    lag=1500,
    oldest_message_age_seconds=30,
)

# Get lag report
report = tracker.get_report("orders")
print(f"Current lag: {report.lag}")
print(f"Processing rate: {report.messages_per_second}/s")
```

### 27. Circuit Breaker Dashboard

Circuit breaker state visualization.

```python
from obskit import CircuitBreakerDashboard

dashboard = CircuitBreakerDashboard()

# Register circuit breakers
dashboard.register("database")
dashboard.register("external-api")

# Update states
dashboard.update_state("database", "closed", failure_count=0)
dashboard.update_state("external-api", "open", failure_count=10)

# Get dashboard data
data = dashboard.get_dashboard_data()
# Returns JSON-friendly data for Grafana or custom dashboard
```

### 28. Error Fingerprinting

Group similar errors automatically.

```python
from obskit import ErrorFingerprinter, get_error_fingerprinter

fingerprinter = ErrorFingerprinter()

try:
    risky_operation()
except Exception as e:
    # Get fingerprint
    fingerprint = fingerprinter.fingerprint(e)
    
    # Check if this is a known error pattern
    group = fingerprinter.get_group(fingerprint)
    
    if group.occurrence_count > 100:
        # Don't alert for known frequent errors
        logger.warning(f"Known error: {group.sample_message}")
    else:
        # New error pattern - alert!
        alert_oncall(e)
```

### 29. Latency Breakdown

Break down operation latency by phase.

```python
from obskit import LatencyBreakdown

breakdown = LatencyBreakdown("api_request")

with breakdown.phase("auth"):
    authenticate_request()

with breakdown.phase("validation"):
    validate_input()

with breakdown.phase("database"):
    fetch_data()

with breakdown.phase("serialization"):
    serialize_response()

# Get summary
summary = breakdown.get_summary()
print(f"Total: {summary.total_ms}ms")
for phase, duration in summary.phases.items():
    percent = (duration / summary.total_ms) * 100
    print(f"  {phase}: {duration}ms ({percent:.1f}%)")
```

### 30. Distributed Locking

Coordinate operations across instances.

```python
from obskit import DistributedLock, create_distributed_lock

# Create Redis-backed lock
lock = create_distributed_lock(
    "order-processing",
    backend="redis",
    redis_url="redis://localhost:6379",
    ttl_seconds=30,
)

# Use lock
with lock.acquire("order-123"):
    # Only one instance processes this order
    process_order("order-123")

# Or with timeout
acquired = lock.try_acquire("order-456", timeout_seconds=5)
if acquired:
    try:
        process_order("order-456")
    finally:
        lock.release("order-456")
```

### 31. Memory/GC Metrics

Track Python memory and garbage collection.

```python
from obskit import MemoryTracker, start_memory_tracking, get_memory_tracker

# Start background tracking
start_memory_tracking(interval_seconds=60)

tracker = get_memory_tracker()

# Get current stats
stats = tracker.get_stats()
print(f"Memory used: {stats.memory_mb}MB")
print(f"Memory percent: {stats.memory_percent}%")
print(f"GC collections: {stats.gc_stats}")
print(f"Top objects: {stats.object_stats.top_types}")

# Force GC and get impact
before, after = tracker.force_gc()
print(f"Freed: {before - after}MB")
```

### 32. Alert Deduplication

Suppress redundant alerts.

```python
from obskit import AlertDeduplicator, get_alert_deduplicator

deduplicator = AlertDeduplicator(
    window_minutes=15,
    max_alerts_per_window=3,
)

# Check if should alert
alert_key = "high-memory-api-server"

if deduplicator.should_alert(alert_key):
    send_alert("High memory on api-server")
else:
    logger.info(f"Suppressed duplicate alert: {alert_key}")

# Get suppression stats
stats = deduplicator.get_stats()
print(f"Alerts sent: {stats.sent}")
print(f"Alerts suppressed: {stats.suppressed}")
```

### 33. Load Shedding

Gracefully reject requests under high load.

```python
from obskit import LoadShedder, Priority, get_load_shedder

shedder = LoadShedder(
    max_load=0.9,  # Start shedding at 90% CPU
    recovery_load=0.7,  # Stop shedding at 70%
)

# Define request priorities
@app.route("/api/critical")
def critical_endpoint():
    if shedder.should_accept(Priority.CRITICAL):
        return process_critical_request()
    return "Service overloaded", 503

@app.route("/api/optional")
def optional_endpoint():
    if shedder.should_accept(Priority.LOW):
        return process_optional_request()
    return "Service overloaded", 503

# Update load metrics
shedder.update_load(get_cpu_percent() / 100)
```

### 34. Tenant Quota Tracking

Monitor per-tenant resource usage.

```python
from obskit import QuotaTracker, QuotaPeriod, get_quota_tracker

tracker = QuotaTracker()

# Set quotas
tracker.set_quota(
    tenant_id="tenant-123",
    resource="api_requests",
    limit=10000,
    period=QuotaPeriod.DAILY,
)

tracker.set_quota(
    tenant_id="tenant-123",
    resource="storage_mb",
    limit=5000,
    period=QuotaPeriod.MONTHLY,
)

# Record usage
tracker.record_usage("tenant-123", "api_requests", 1)

# Check quota
usage = tracker.get_usage("tenant-123", "api_requests")
if usage.is_exceeded:
    return "Quota exceeded", 429

print(f"Usage: {usage.current}/{usage.limit} ({usage.percent}%)")

# Get report
report = tracker.get_tenant_report("tenant-123")
```

---

## Summary

ObsKit v1.3 provides **52 comprehensive observability features** covering:

| Category | Features |
|----------|----------|
| Debugging & Analysis | 4 |
| Resilience & Reliability | 4 |
| Performance | 4 |
| Security & Compliance | 3 |
| Operations | 4 |
| Deployment & Testing | 2 |
| Infrastructure | 13 |
| **Total** | **34 new + 18 existing = 52** |

All features are:
- ✅ Production-ready with metrics integration
- ✅ Fully typed with dataclasses
- ✅ Serializable to JSON/dict
- ✅ Singleton-capable for easy global access
- ✅ Unit tested
- ✅ Documented with examples

For more information, see the [API Reference](./API_REFERENCE.md).
