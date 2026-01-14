# API Stability and Versioning

## Version Policy

obskit follows [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

## Current Status

**Version: 1.0.0 (Stable Release)** ✅

As of v1.0.0, obskit is considered **fully production-ready** with stable APIs. We are committed to maintaining backwards compatibility within major versions.

### Stability Commitment

🛡️ **Our Promise:**
- No breaking changes within a major version (1.x.x)
- Minimum 2 minor versions deprecation notice before removal
- Clear migration guides for any API changes
- Security patches backported to latest stable release

---

## API Stability Matrix

All components are now **Stable**:

| Component | Stability | Since | Notes |
|-----------|-----------|-------|-------|
| Core Configuration | ✅ Stable | v0.1.0 | `configure()`, `get_settings()` |
| RED Metrics | ✅ Stable | v0.1.0 | `REDMetrics`, `get_red_metrics()` |
| Golden Signals | ✅ Stable | v0.1.0 | `GoldenSignals`, `get_golden_signals()` |
| USE Metrics | ✅ Stable | v0.1.0 | `USEMetrics`, `get_use_metrics()` |
| Health Checks | ✅ Stable | v0.1.0 | `HealthChecker`, built-in checks |
| Logging | ✅ Stable | v0.1.0 | `get_logger()`, `configure_logging()` |
| Middleware (FastAPI) | ✅ Stable | v0.1.0 | `ObskitMiddleware` |
| Middleware (Flask) | ✅ Stable | v0.1.0 | `ObskitFlaskMiddleware` |
| Middleware (Django) | ✅ Stable | v0.1.0 | `ObskitDjangoMiddleware` |
| Circuit Breaker | ✅ Stable | v0.1.0 | `CircuitBreaker` |
| **Distributed Circuit Breaker** | ✅ **Stable** | v1.0.0 | `DistributedCircuitBreaker` |
| **SLO Tracking** | ✅ **Stable** | v1.0.0 | `SLOTracker`, `track_slo()` |
| **Self-Metrics** | ✅ **Stable** | v1.0.0 | `get_self_metrics()` |
| Tracing | ✅ Stable | v0.1.0 | OpenTelemetry integration |
| Alertmanager | ✅ Stable | v1.0.0 | `AlertmanagerWebhook` |
| PII Redaction | ✅ Stable | v0.1.0 | `redact_pii()` |

### Legend

- ✅ **Stable**: API is production-ready. Breaking changes require major version bump.
- ⚠️ **Beta**: Functional but may evolve. Breaking changes possible in minor versions.
- 🔬 **Experimental**: Not for production. API may change significantly.

---

## Deprecation Policy

When we need to make changes, we follow this strict process:

### Phase 1: Deprecation Warning (Minimum 2 Minor Versions)

```python
import warnings

# Old API
def old_function():
    warnings.warn(
        "old_function() is deprecated and will be removed in v1.4.0. "
        "Use new_function() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return new_function()

# New API
def new_function():
    pass
```

### Phase 2: Documentation Update

- ✅ CHANGELOG entry explaining the change
- ✅ Migration guide with code examples
- ✅ Documentation updated with new API
- ✅ Deprecation notice in docstrings

### Phase 3: Removal (After 2 Minor Versions)

After at least 2 minor versions, the deprecated API may be removed.

**Example Timeline:**
- v1.2.0: `old_function()` deprecated, `new_function()` added
- v1.3.0: `old_function()` emits deprecation warning
- v1.4.0: `old_function()` removed (minimum 2 minor versions)

---

## Breaking Change Policy

Breaking changes will **only occur in major versions** (e.g., v2.0.0).

### Required Process for Breaking Changes

1. **RFC Discussion**: Major changes require a GitHub Discussion first
2. **Migration Guide**: Complete guide with before/after examples
3. **Codemods**: Automated migration tools where possible
4. **Release Notes**: Clear announcement in release notes
5. **Deprecation Period**: At least 2 minor versions in previous major

### Types of Changes

| Change Type | Major Version | Minor Version | Patch Version |
|-------------|---------------|---------------|---------------|
| New function | - | ✅ | - |
| New optional parameter | - | ✅ | - |
| New required parameter | ✅ | - | - |
| Function removal | ✅ | - | - |
| Return type change | ✅ | - | - |
| Default value change | ⚠️ (case-by-case) | ⚠️ (case-by-case) | - |
| Bug fix | - | - | ✅ |
| Security fix | - | - | ✅ |
| Minimum Python version | ✅ | - | - |
| Dependency update | ⚠️ (case-by-case) | ⚠️ (case-by-case) | - |

---

## Version Compatibility Matrix

### Python Versions

| obskit Version | Python 3.11 | Python 3.12 | Python 3.13 | Python 3.14 |
|---------------|-------------|-------------|-------------|-------------|
| 1.0.x | ✅ | ✅ | ✅ | ⚠️ (untested) |
| 1.1.x (planned) | ✅ | ✅ | ✅ | ✅ |
| 2.0.x (future) | ❌ | ✅ | ✅ | ✅ |

### Framework Compatibility

| Framework | Minimum | Maximum | Notes |
|-----------|---------|---------|-------|
| FastAPI | 0.100.0 | 0.115.x | Full support |
| Flask | 2.0.0 | 3.x | Full support |
| Django | 4.0.0 | 5.x | Full support |
| Starlette | 0.27.0 | 0.x | Via FastAPI |

### Dependency Versions

| Dependency | Minimum | Maximum | Update Policy |
|------------|---------|---------|---------------|
| structlog | 24.1.0 | <26.0.0 | Minor updates allowed |
| pydantic-settings | 2.0.0 | <3.0.0 | Minor updates allowed |
| prometheus-client | 0.19.0 | <1.0.0 | Minor updates allowed |
| opentelemetry-sdk | 1.20.0 | <2.0.0 | Minor updates allowed |
| redis | 5.0.0 | <6.0.0 | Minor updates allowed |

---

## Configuration Stability

### Environment Variables

All `OBSKIT_*` environment variables are considered stable:

| Variable | Since | Status |
|----------|-------|--------|
| `OBSKIT_SERVICE_NAME` | v0.1.0 | ✅ Stable |
| `OBSKIT_ENVIRONMENT` | v0.1.0 | ✅ Stable |
| `OBSKIT_VERSION` | v0.1.0 | ✅ Stable |
| `OBSKIT_LOG_LEVEL` | v0.1.0 | ✅ Stable |
| `OBSKIT_LOG_FORMAT` | v0.1.0 | ✅ Stable |
| `OBSKIT_METRICS_ENABLED` | v0.1.0 | ✅ Stable |
| `OBSKIT_METRICS_PORT` | v0.1.0 | ✅ Stable |
| `OBSKIT_METRICS_AUTH_ENABLED` | v0.1.0 | ✅ Stable |
| `OBSKIT_METRICS_AUTH_TOKEN` | v0.1.0 | ✅ Stable |
| `OBSKIT_METRICS_RATE_LIMIT_ENABLED` | v1.0.0 | ✅ Stable |
| `OBSKIT_TRACING_ENABLED` | v0.1.0 | ✅ Stable |
| `OBSKIT_OTLP_ENDPOINT` | v0.1.0 | ✅ Stable |
| `OBSKIT_ENABLE_SELF_METRICS` | v1.0.0 | ✅ Stable |
| `OBSKIT_ASYNC_METRIC_QUEUE_SIZE` | v1.0.0 | ✅ Stable |

---

## Metrics Stability

### Prometheus Metrics

All exposed metrics are considered part of the stable API:

| Metric | Type | Labels | Status |
|--------|------|--------|--------|
| `red_requests_total` | Counter | service, operation, status | ✅ Stable |
| `red_request_duration_seconds` | Histogram | service, operation | ✅ Stable |
| `golden_latency_seconds` | Histogram | service, operation | ✅ Stable |
| `golden_traffic_total` | Counter | service, operation | ✅ Stable |
| `golden_errors_total` | Counter | service, operation, error_type | ✅ Stable |
| `golden_saturation` | Gauge | service, resource | ✅ Stable |
| `use_utilization` | Gauge | service, resource | ✅ Stable |
| `use_saturation` | Gauge | service, resource | ✅ Stable |
| `use_errors_total` | Counter | service, resource, error_type | ✅ Stable |
| `obskit_async_queue_depth` | Gauge | - | ✅ Stable |
| `obskit_async_queue_capacity` | Gauge | - | ✅ Stable |
| `obskit_metrics_dropped_total` | Counter | operation, reason | ✅ Stable |
| `obskit_errors_total` | Counter | component, error_type | ✅ Stable |
| `obskit_info` | Info | version | ✅ Stable |

**Metric Stability Guarantees:**
- Metric names will not change within a major version
- Label names will not change within a major version
- New labels may be added in minor versions
- Histograms bucket boundaries are considered stable

---

## Future Roadmap

### v1.1.0 (Planned)

- Additional built-in health checks (PostgreSQL, MongoDB)
- gRPC middleware support
- Enhanced SLO features (multi-window burn rates)
- Performance optimizations

### v1.2.0 (Planned)

- Async logging adapters
- Custom metric types
- Enhanced tracing context propagation

### v2.0.0 (Future)

- Python 3.11 minimum version drop
- Potential API simplifications
- Enhanced type safety with Python 3.12+ features

---

## Getting Help

### API Migration Issues

1. **Check CHANGELOG** for migration instructions
2. **Search GitHub Issues** for similar problems
3. **Open an Issue** with the `migration` label
4. **Contact maintainers** for urgent production issues

### Reporting Stability Concerns

If you encounter unexpected breaking changes:

1. Open an issue with the `stability` label
2. Include your obskit version and the breaking change
3. We prioritize these issues as critical bugs

### Contributing to API Design

We welcome feedback on API design:

1. **Open a Discussion** for new feature proposals
2. **Submit an Issue** for API improvement suggestions
3. **Review PRs** and provide feedback on API changes

---

## Security Considerations

### Security Update Policy

| Update Type | Response Time | Versions |
|-------------|---------------|----------|
| Critical CVE | 24-48 hours | Latest stable |
| High severity | 1 week | Latest stable |
| Medium severity | 2 weeks | Latest stable |
| Low severity | Next release | Latest stable |

### Supported Versions

| Version | Security Updates | Bug Fixes |
|---------|------------------|-----------|
| 1.0.x | ✅ Yes | ✅ Yes |
| 0.1.x | ⚠️ Critical only | ❌ No |

---

**Last Updated:** 2026-01-13  
**Version:** 1.0.0  
**Status:** ✅ Production Stable
