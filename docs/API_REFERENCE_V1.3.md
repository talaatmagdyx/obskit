# ObsKit v1.3 API Reference

Complete API reference for all 52 features in ObsKit v1.3.

## Table of Contents

- [Debugging & Analysis](#debugging--analysis)
- [Resilience & Reliability](#resilience--reliability)
- [Performance](#performance)
- [Security & Compliance](#security--compliance)
- [Operations](#operations)
- [Deployment & Testing](#deployment--testing)
- [Infrastructure](#infrastructure)

---

## Debugging & Analysis

### FlameGraphProfiler

```python
from obskit import FlameGraphProfiler, profile_function, get_flamegraph_profiler
```

#### Class: `FlameGraphProfiler`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `profile(operation)` | Context manager for profiling | `operation: str` | Context manager |
| `get_profile(operation)` | Get profile results | `operation: str` | `ProfileResult` or `None` |
| `get_all_profiles()` | Get all profiles | - | `Dict[str, ProfileResult]` |
| `generate_flamegraph_data(operation)` | Generate flame graph data | `operation: str` | `FlameGraphNode` |
| `export_collapsed(operation)` | Export collapsed stack format | `operation: str` | `str` |
| `clear(operation)` | Clear specific profile | `operation: str` | `None` |

#### Dataclass: `ProfileResult`

| Field | Type | Description |
|-------|------|-------------|
| `operation` | `str` | Operation name |
| `duration_seconds` | `float` | Total duration |
| `total_calls` | `int` | Number of function calls |
| `top_functions` | `List[Tuple[str, float, int]]` | Top functions by time |
| `call_tree` | `Dict` | Call tree structure |

---

### QueryAnalyzer

```python
from obskit import QueryAnalyzer, QueryAnalysis, QueryType, get_query_analyzer
```

#### Class: `QueryAnalyzer`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `analyze(query, explain_output, actual_time_ms)` | Analyze SQL query | `query: str`, `explain_output: Optional[str]`, `actual_time_ms: Optional[float]` | `QueryAnalysis` |
| `get_slow_queries(limit)` | Get slow queries | `limit: int = 10` | `List[QueryAnalysis]` |

#### Dataclass: `QueryAnalysis`

| Field | Type | Description |
|-------|------|-------------|
| `query_hash` | `str` | Normalized query hash |
| `query_type` | `QueryType` | SELECT, INSERT, UPDATE, DELETE |
| `tables_accessed` | `List[str]` | Tables in query |
| `indexes_used` | `List[str]` | Indexes used |
| `missing_indexes` | `List[str]` | Suggested missing indexes |
| `estimated_cost` | `float` | Query cost estimate |
| `has_seq_scan` | `bool` | Has sequential scan |
| `needs_optimization` | `bool` | Needs optimization |
| `suggestions` | `List[str]` | Optimization suggestions |

---

### DependencyGraph

```python
from obskit import DependencyGraph, DependencyNode, DependencyType, get_dependency_graph
```

#### Class: `DependencyGraph`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `add_dependency(name, dep_type, is_critical)` | Add dependency | `name: str`, `dep_type: DependencyType`, `is_critical: bool = False` | `None` |
| `record_call(name, latency_ms, success)` | Record dependency call | `name: str`, `latency_ms: float`, `success: bool = True` | `None` |
| `get_dependency(name)` | Get dependency | `name: str` | `DependencyNode` or `None` |
| `get_unhealthy_dependencies()` | Get unhealthy deps | - | `List[DependencyNode]` |
| `get_critical_path()` | Get critical path | - | `List[str]` |
| `is_healthy()` | Check overall health | - | `bool` |
| `get_visualization_data()` | Get viz data | - | `GraphVisualization` |

#### Enum: `DependencyType`

- `DATABASE`, `CACHE`, `SERVICE`, `QUEUE`, `STORAGE`, `OTHER`

---

### RootCauseAnalyzer

```python
from obskit import RootCauseAnalyzer, Anomaly, AnomalySeverity, get_root_cause_analyzer
```

#### Class: `RootCauseAnalyzer`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `record_anomaly(description, component, ...)` | Record anomaly | See docstring | `str` (anomaly_id) |
| `resolve_anomaly(anomaly_id)` | Resolve anomaly | `anomaly_id: str` | `None` |
| `analyze()` | Analyze root cause | - | `RootCauseResult` |
| `get_active_anomalies()` | Get active anomalies | - | `List[Anomaly]` |
| `record_event(event_type, description, ...)` | Record correlated event | See docstring | `None` |

#### Dataclass: `RootCauseResult`

| Field | Type | Description |
|-------|------|-------------|
| `probable_cause` | `Optional[str]` | Most likely cause |
| `confidence` | `float` | Confidence score (0-1) |
| `affected_components` | `List[str]` | Affected components |
| `anomalies` | `List[Anomaly]` | Related anomalies |
| `suggestions` | `List[str]` | Remediation suggestions |
| `timeline` | `List[Dict]` | Event timeline |
| `impact_assessment` | `str` | Impact description |

---

## Resilience & Reliability

### ChaosEngine

```python
from obskit import ChaosEngine, InjectionType, chaos_injection, enable_chaos, disable_chaos
```

#### Class: `ChaosEngine`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `add_experiment(name, injection_type, probability, ...)` | Add experiment | See docstring | `None` |
| `should_inject(name, component)` | Check if should inject | `name: str`, `component: Optional[str]` | `bool` |
| `inject_latency(name)` | Inject latency | `name: str` | `None` |
| `inject_error(name)` | Inject error | `name: str` | Raises exception |
| `maybe_inject(name)` | Context manager | `name: str` | Context manager |
| `enable_experiment(name)` | Enable experiment | `name: str` | `None` |
| `disable_experiment(name)` | Disable experiment | `name: str` | `None` |

#### Enum: `InjectionType`

- `LATENCY`, `ERROR`, `EXCEPTION`, `TIMEOUT`, `CORRUPTION`

---

### FailoverCoordinator

```python
from obskit import FailoverCoordinator, FailoverState, get_failover_coordinator
```

#### Class: `FailoverCoordinator`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `register_primary(name, address, health_check)` | Register primary | `name: str`, `address: str`, `health_check: Callable` | `None` |
| `register_backup(name, address, health_check)` | Register backup | `name: str`, `address: str`, `health_check: Callable` | `None` |
| `get_active()` | Get active endpoint | - | `Endpoint` |
| `get_active_address()` | Get active address | - | `str` |
| `check_health()` | Check health | - | `None` |
| `force_failover(reason)` | Force failover | `reason: Optional[str]` | `None` |
| `force_recovery()` | Force recovery | - | `None` |
| `get_state()` | Get current state | - | `FailoverState` |
| `get_status()` | Get full status | - | `Dict` |
| `get_events()` | Get events | - | `List[FailoverEvent]` |

---

### DegradationManager

```python
from obskit import DegradationManager, DegradationLevel, get_degradation_manager
```

#### Class: `DegradationManager`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `register_feature(name, priority, degradation_threshold, ...)` | Register feature | See docstring | `None` |
| `is_enabled(name)` | Check if enabled | `name: str` | `bool` |
| `set_level(level)` | Set degradation level | `level: DegradationLevel` | `None` |
| `degrade_feature(name, reason)` | Manually degrade | `name: str`, `reason: Optional[str]` | `None` |
| `restore_feature(name)` | Restore feature | `name: str` | `None` |
| `execute_with_fallback(name, primary, fallback)` | Execute with fallback | `name: str`, `primary: Callable`, `fallback: Callable` | `Any` |
| `get_state()` | Get state | - | `DegradationState` |
| `reset()` | Reset all | - | `None` |

#### Enum: `DegradationLevel`

- `NONE` (0), `LOW` (25), `MEDIUM` (50), `HIGH` (75), `CRITICAL` (100)

---

### SelfHealingEngine

```python
from obskit import SelfHealingEngine, HealingResult, get_self_healing_engine
```

#### Class: `SelfHealingEngine`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `register_trigger(name, condition, action, ...)` | Register trigger | See docstring | `None` |
| `evaluate()` | Evaluate all triggers | - | `List[HealingEvent]` |
| `get_trigger(name)` | Get trigger | `name: str` | `HealingTrigger` |
| `enable_trigger(name)` | Enable trigger | `name: str` | `None` |
| `disable_trigger(name)` | Disable trigger | `name: str` | `None` |
| `get_events(limit)` | Get recent events | `limit: int = 100` | `List[HealingEvent]` |

#### Enum: `HealingResult`

- `SUCCESS`, `FAILED`, `SKIPPED`

---

## Performance

### AdaptiveSampler

```python
from obskit import AdaptiveSampler, get_adaptive_sampler
```

#### Class: `AdaptiveSampler`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `should_sample(priority, has_error, latency_ms, operation)` | Check if should sample | See docstring | `bool` |
| `set_rate(rate)` | Set sampling rate | `rate: float` | `None` |
| `get_rate()` | Get current rate | - | `float` |
| `set_operation_rate(operation, rate)` | Set operation rate | `operation: str`, `rate: float` | `None` |
| `get_stats()` | Get statistics | - | `SamplingStats` |
| `reset_stats()` | Reset statistics | - | `None` |

---

### HotPathDetector

```python
from obskit import HotPathDetector, track_path, get_hot_path_detector
```

#### Class: `HotPathDetector`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `track(path)` | Context manager | `path: str` | Context manager |
| `record(path, duration_ms, has_error, caller)` | Manual record | See docstring | `None` |
| `get_path_stats(path)` | Get path stats | `path: str` | `PathStats` |
| `get_hot_paths(limit)` | Get hot paths | `limit: int = 10` | `List[HotPath]` |
| `get_call_graph()` | Get call graph | - | `Dict[str, List[str]]` |
| `get_summary()` | Get summary | - | `Dict` |
| `clear()` | Clear all | - | `None` |

---

### ResourcePredictor

```python
from obskit import ResourcePredictor, Forecast, get_resource_predictor
```

#### Class: `ResourcePredictor`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `record(resource, value, timestamp)` | Record metric | `resource: str`, `value: float`, `timestamp: Optional[datetime]` | `None` |
| `set_threshold(resource, threshold)` | Set threshold | `resource: str`, `threshold: float` | `None` |
| `predict(resource, hours_ahead)` | Predict usage | `resource: str`, `hours_ahead: int = 24` | `Forecast` or `None` |
| `get_all_forecasts(hours_ahead)` | Get all forecasts | `hours_ahead: int = 24` | `Dict[str, Forecast]` |
| `get_at_risk_resources()` | Get at-risk resources | - | `List[Forecast]` |
| `get_history(resource)` | Get history | `resource: str` | `List[Tuple[datetime, float]]` |
| `clear(resource)` | Clear resource | `resource: Optional[str] = None` | `None` |

---

### AutoScalingMetrics

```python
from obskit import AutoScalingMetrics, ScalingRecommendation, get_autoscaling_metrics
```

#### Class: `AutoScalingMetrics`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `set_replicas(count)` | Set replica count | `count: int` | `None` |
| `record_queue_depth(depth)` | Record queue depth | `depth: int` | `None` |
| `record_requests_per_second(rps)` | Record RPS | `rps: float` | `None` |
| `record_pod_metrics(pod_name, cpu, memory, requests)` | Record pod metrics | See docstring | `None` |
| `get_recommendation()` | Get scaling recommendation | - | `ScalingRecommendation` |
| `get_metrics_for_hpa()` | Get HPA metrics | - | `Dict` |
| `record_scaling_event(direction, new_count)` | Record scaling | `direction: ScalingDirection`, `new_count: int` | `None` |

---

## Security & Compliance

### AuditTrail

```python
from obskit import AuditTrail, AuditAction, AuditResult, get_audit_trail
```

#### Class: `AuditTrail`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `record(action, actor, resource, ...)` | Record audit entry | See docstring | `AuditEntry` |
| `query(query)` | Query entries | `query: AuditQuery` | `List[AuditEntry]` |
| `get_actor_activity(actor, limit)` | Get actor activity | `actor: str`, `limit: int = 100` | `List[AuditEntry]` |
| `get_resource_history(resource, limit)` | Get resource history | `resource: str`, `limit: int = 100` | `List[AuditEntry]` |
| `get_failed_actions(limit)` | Get failed actions | `limit: int = 100` | `List[AuditEntry]` |
| `verify_chain()` | Verify integrity | - | `Tuple[bool, Optional[str]]` |
| `export_for_compliance(start_time, end_time)` | Export for compliance | `start_time: datetime`, `end_time: datetime` | `List[Dict]` |

#### Enum: `AuditAction`

- `CREATE`, `READ`, `UPDATE`, `DELETE`, `LOGIN`, `LOGOUT`, `GRANT`, `REVOKE`, `EXPORT`, `IMPORT`

---

### SecretsDetector

```python
from obskit import SecretsDetector, SecretType, redact_secrets, scan_for_secrets
```

#### Class: `SecretsDetector`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `scan(text)` | Scan for secrets | `text: str` | `DetectionResult` |
| `redact(text)` | Redact secrets | `text: str` | `str` |
| `scan_and_redact(text)` | Scan and redact | `text: str` | `Tuple[str, DetectionResult]` |
| `is_safe(text)` | Check if safe | `text: str` | `bool` |
| `add_pattern(name, pattern, secret_type)` | Add pattern | `name: str`, `pattern: str`, `secret_type: SecretType` | `None` |

#### Enum: `SecretType`

- `API_KEY`, `PASSWORD`, `JWT`, `AWS_KEY`, `CREDIT_CARD`, `SSH_KEY`, `PRIVATE_KEY`, `CUSTOM`

---

### ComplianceReporter

```python
from obskit import ComplianceReporter, ComplianceFramework, get_compliance_reporter
```

#### Class: `ComplianceReporter`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `check_gdpr()` | Check GDPR compliance | - | `ComplianceReport` |
| `check_soc2()` | Check SOC2 compliance | - | `ComplianceReport` |
| `check_hipaa()` | Check HIPAA compliance | - | `ComplianceReport` |
| `check_all()` | Check all frameworks | - | `Dict[str, ComplianceReport]` |
| `add_check(check)` | Add custom check | `check: ComplianceCheck` | `None` |
| `run_check(check)` | Run specific check | `check: ComplianceCheck` | `CheckResult` |
| `set_check_function(check_id, func)` | Override check func | `check_id: str`, `func: Callable` | `None` |
| `get_remediation_plan()` | Get remediation plan | - | `List[Dict]` |

---

## Operations

### RunbookManager

```python
from obskit import RunbookManager, Runbook, get_runbook_manager
```

#### Class: `RunbookManager`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `register(runbook_id, title, steps, ...)` | Register runbook | See docstring | `None` |
| `get_runbook(runbook_id)` | Get runbook | `runbook_id: str` | `Runbook` or `None` |
| `get_for_alert(alert_name)` | Find for alert | `alert_name: str` | `Runbook` or `None` |
| `search(query, tags)` | Search runbooks | `query: Optional[str]`, `tags: Optional[List[str]]` | `List[Runbook]` |
| `start_execution(runbook_id, alert_name, executor)` | Start execution | See docstring | `RunbookExecution` |
| `update_execution(execution_id, current_step, step_note)` | Update execution | See docstring | `None` |
| `complete_execution(execution_id, resolved, notes)` | Complete | See docstring | `None` |
| `fail_execution(execution_id, reason)` | Fail execution | `execution_id: str`, `reason: str` | `None` |
| `escalate_execution(execution_id, reason)` | Escalate | `execution_id: str`, `reason: str` | `None` |
| `get_execution(execution_id)` | Get execution | `execution_id: str` | `RunbookExecution` |
| `get_recent_executions(limit)` | Get recent | `limit: int = 10` | `List[RunbookExecution]` |

---

### IncidentTimeline

```python
from obskit import IncidentTimeline, IncidentManager, IncidentStatus, get_incident_manager
```

#### Class: `IncidentTimeline`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `add_event(description, category, actor, ...)` | Add event | See docstring | `TimelineEvent` |
| `update_status(status, note)` | Update status | `status: IncidentStatus`, `note: Optional[str]` | `None` |
| `add_responder(responder)` | Add responder | `responder: str` | `None` |
| `add_affected_service(service)` | Add service | `service: str` | `None` |
| `set_root_cause(cause)` | Set root cause | `cause: str` | `None` |
| `set_resolution(resolution)` | Set resolution | `resolution: str` | `None` |
| `get_timeline()` | Get all events | - | `List[TimelineEvent]` |
| `get_timeline_by_category(category)` | Filter by category | `category: EventCategory` | `List[TimelineEvent]` |
| `generate_report()` | Generate report | - | `Dict` |
| `generate_postmortem()` | Generate postmortem | - | `Dict` |

#### Enum: `IncidentStatus`

- `DETECTED`, `INVESTIGATING`, `IDENTIFIED`, `MITIGATING`, `RESOLVED`, `POSTMORTEM`

---

### SLAPredictor

```python
from obskit import SLAPredictor, RiskAssessment, get_sla_predictor
```

#### Class: `SLAPredictor`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `set_sla(name, target_value, percentile, comparison)` | Define SLA | See docstring | `None` |
| `record(sla_name, value, timestamp)` | Record metric | `sla_name: str`, `value: float`, `timestamp: Optional[datetime]` | `None` |
| `assess_risk(sla_name)` | Assess risk | `sla_name: str` | `RiskAssessment` or `None` |
| `get_all_risks()` | Get all risks | - | `Dict[str, RiskAssessment]` |
| `get_at_risk_slas(threshold)` | Get at-risk SLAs | `threshold: float = 50.0` | `List[RiskAssessment]` |

#### Dataclass: `RiskAssessment`

| Field | Type | Description |
|-------|------|-------------|
| `sla_name` | `str` | SLA name |
| `risk_score` | `float` | Risk score (0-100) |
| `breach_likely` | `bool` | Breach likely |
| `hours_until_breach` | `Optional[float]` | Hours until breach |
| `current_value` | `float` | Current value |
| `target_value` | `float` | Target value |
| `trend` | `str` | stable/degrading/improving |
| `confidence` | `float` | Confidence (0-1) |
| `suggestions` | `List[str]` | Suggestions |

---

### CapacityPlanner

```python
from obskit import CapacityPlanner, CapacityPlan, get_capacity_planner
```

#### Class: `CapacityPlanner`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `add_resource(name, current_value, max_value, ...)` | Add resource | See docstring | `None` |
| `update_resource(name, current_value)` | Update resource | `name: str`, `current_value: float` | `None` |
| `get_resource(name)` | Get resource | `name: str` | `Resource` or `None` |
| `project(months_ahead)` | Generate plan | `months_ahead: int = 12` | `CapacityPlan` |
| `project_resource(name, months_ahead)` | Project resource | `name: str`, `months_ahead: int` | `CapacityProjection` |
| `get_critical_resources()` | Get critical | - | `List[Resource]` |
| `calculate_growth_rate(name)` | Calculate growth | `name: str` | `Optional[float]` |

---

## Deployment & Testing

### FeatureFlagTracker

```python
from obskit import FeatureFlagTracker, FlagMetrics, get_feature_flag_tracker
```

#### Class: `FeatureFlagTracker`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `register_flag(name, enabled, rollout_percent, description)` | Register flag | See docstring | `None` |
| `record_evaluation(flag_name, enabled, user_id, context)` | Record evaluation | See docstring | `None` |
| `get_flag_metrics(flag_name)` | Get metrics | `flag_name: str` | `FlagMetrics` or `None` |
| `get_all_metrics()` | Get all metrics | - | `Dict[str, FlagMetrics]` |
| `update_flag_state(name, enabled, rollout_percent)` | Update state | See docstring | `None` |

#### Dataclass: `FlagMetrics`

| Field | Type | Description |
|-------|------|-------------|
| `flag_name` | `str` | Flag name |
| `total_evaluations` | `int` | Total evaluations |
| `enabled_count` | `int` | Enabled count |
| `disabled_count` | `int` | Disabled count |
| `unique_users` | `int` | Unique users |
| `enabled_percent` | `float` | Enabled percentage |

---

### DeploymentTracker

```python
from obskit import DeploymentTracker, Deployment, DeploymentType, get_deployment_tracker
```

#### Class: `DeploymentTracker`

| Method | Description | Parameters | Returns |
|--------|-------------|------------|---------|
| `start_canary(version, traffic_percent, baseline_version)` | Start canary | See docstring | `None` |
| `start_blue_green(new_version, old_version)` | Start blue-green | `new_version: str`, `old_version: str` | `None` |
| `record_request(version, latency_ms, success)` | Record request | `version: str`, `latency_ms: float`, `success: bool` | `None` |
| `is_canary_healthy(version)` | Check health | `version: str` | `bool` |
| `increase_traffic(version, percent)` | Increase traffic | `version: str`, `percent: float` | `None` |
| `rollback(version, reason)` | Rollback | `version: str`, `reason: Optional[str]` | `None` |
| `complete_deployment(version)` | Complete | `version: str` | `None` |
| `get_deployment(version)` | Get deployment | `version: str` | `Deployment` or `None` |
| `get_active_deployments()` | Get active | - | `List[Deployment]` |
| `set_baseline_metrics(version, error_rate, latency_p50, latency_p99)` | Set baseline | See docstring | `None` |

#### Enum: `DeploymentType`

- `CANARY`, `BLUE_GREEN`, `ROLLING`, `AB_TEST`

#### Enum: `DeploymentStatus`

- `PENDING`, `CANARY`, `FULL`, `COMPLETED`, `ROLLED_BACK`, `FAILED`

---

## Infrastructure

### ConnectionPoolTracker

```python
from obskit import ConnectionPoolTracker
```

| Method | Description |
|--------|-------------|
| `set_size(active, idle, waiting)` | Set pool sizes |
| `track_checkout()` | Context manager for checkout |
| `record_error(error_type)` | Record pool error |
| `get_metrics()` | Get pool metrics |

### DLQTracker

```python
from obskit import DLQTracker
```

| Method | Description |
|--------|-------------|
| `record(message_id, reason, original_queue, ...)` | Record DLQ message |
| `get_stats()` | Get DLQ statistics |

### ExternalAPISLATracker

```python
from obskit import ExternalAPISLATracker
```

| Method | Description |
|--------|-------------|
| `set_sla(api, availability, latency_p99)` | Set expected SLA |
| `record_call(api, latency_ms, success)` | Record API call |
| `get_compliance_report(api)` | Get compliance report |

### ExecutorTracker

```python
from obskit import ExecutorTracker
```

| Method | Description |
|--------|-------------|
| `submit(fn, *args, **kwargs)` | Submit tracked task |
| `get_metrics()` | Get executor metrics |

### ConsumerLagTracker

```python
from obskit import ConsumerLagTracker
```

| Method | Description |
|--------|-------------|
| `update_lag(queue, consumer_group, lag, oldest_message_age)` | Update lag |
| `get_report(queue)` | Get lag report |

### CircuitBreakerDashboard

```python
from obskit import CircuitBreakerDashboard
```

| Method | Description |
|--------|-------------|
| `register(name)` | Register circuit breaker |
| `update_state(name, state, failure_count)` | Update state |
| `get_dashboard_data()` | Get dashboard data |

### ErrorFingerprinter

```python
from obskit import ErrorFingerprinter, get_error_fingerprinter
```

| Method | Description |
|--------|-------------|
| `fingerprint(exception)` | Get error fingerprint |
| `get_group(fingerprint)` | Get error group |

### LatencyBreakdown

```python
from obskit import LatencyBreakdown
```

| Method | Description |
|--------|-------------|
| `phase(name)` | Context manager for phase |
| `get_summary()` | Get breakdown summary |

### DistributedLock

```python
from obskit import DistributedLock, create_distributed_lock
```

| Method | Description |
|--------|-------------|
| `acquire(key)` | Context manager for lock |
| `try_acquire(key, timeout_seconds)` | Try to acquire |
| `release(key)` | Release lock |

### MemoryTracker

```python
from obskit import MemoryTracker, start_memory_tracking, get_memory_tracker
```

| Method | Description |
|--------|-------------|
| `get_stats()` | Get memory stats |
| `force_gc()` | Force garbage collection |

### AlertDeduplicator

```python
from obskit import AlertDeduplicator, get_alert_deduplicator
```

| Method | Description |
|--------|-------------|
| `should_alert(alert_key)` | Check if should alert |
| `get_stats()` | Get suppression stats |

### LoadShedder

```python
from obskit import LoadShedder, Priority, get_load_shedder
```

| Method | Description |
|--------|-------------|
| `should_accept(priority)` | Check if should accept |
| `update_load(load)` | Update load metric |

### QuotaTracker

```python
from obskit import QuotaTracker, QuotaPeriod, get_quota_tracker
```

| Method | Description |
|--------|-------------|
| `set_quota(tenant_id, resource, limit, period)` | Set quota |
| `record_usage(tenant_id, resource, amount)` | Record usage |
| `get_usage(tenant_id, resource)` | Get usage |
| `get_tenant_report(tenant_id)` | Get tenant report |

---

## Global Singletons

All major classes have corresponding `get_*` functions for global singleton access:

```python
# One instance per service/name
get_flamegraph_profiler()
get_query_analyzer(database_name)
get_dependency_graph(service_name)
get_root_cause_analyzer(service_name)
get_chaos_engine()
get_failover_coordinator(name)
get_degradation_manager(service_name)
get_self_healing_engine()
get_adaptive_sampler(name)
get_hot_path_detector()
get_resource_predictor()
get_autoscaling_metrics(service_name)
get_audit_trail(service_name)
get_secrets_detector()
get_compliance_reporter(service_name)
get_runbook_manager()
get_incident_manager()
get_sla_predictor()
get_capacity_planner()
get_feature_flag_tracker()
get_deployment_tracker()
get_error_fingerprinter()
get_memory_tracker()
get_alert_deduplicator()
get_load_shedder()
get_quota_tracker()
```

---

For detailed usage examples, see [FEATURES_V1.3.md](./FEATURES_V1.3.md).
