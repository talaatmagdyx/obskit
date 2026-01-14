# Health Checks Guide

Complete guide to Kubernetes-style health checks with built-in dependency checks.

---

## Overview

obskit provides three types of health checks:

| Check Type | Purpose | Kubernetes Probe |
|------------|---------|------------------|
| **Liveness** | Is the process alive? | `livenessProbe` |
| **Readiness** | Can we serve traffic? | `readinessProbe` |
| **Startup** | Has initialization completed? | `startupProbe` |

---

## Basic Setup

```python
from obskit.health import HealthChecker, create_health_response

checker = HealthChecker()

# Add checks
@checker.add_liveness_check("heartbeat")
async def check_heartbeat():
    return True

@checker.add_readiness_check("database")
async def check_database():
    try:
        await db.execute("SELECT 1")
        return True
    except Exception:
        return False

# Expose endpoints
@app.get("/live")
async def live():
    result = await checker.check_liveness()
    return create_health_response(result)

@app.get("/ready")
async def ready():
    result = await checker.check_readiness()
    return create_health_response(result)

@app.get("/health")
async def health():
    result = await checker.check_health()
    return create_health_response(result)
```

---

## Built-in Health Checks

### Redis Check

```python
from obskit.health import HealthChecker, create_redis_check
import redis

checker = HealthChecker()
redis_client = redis.Redis(host="localhost", port=6379)

# Basic Redis check
checker.add_readiness_check(
    "redis",
    create_redis_check(redis_client),
    critical=True,
)

# Redis with custom timeout
checker.add_readiness_check(
    "redis",
    create_redis_check(redis_client, timeout=2.0),
)

# Redis Cluster check
checker.add_readiness_check(
    "redis_cluster",
    create_redis_check(redis_client, check_cluster=True),
)
```

### Memory Check

```python
from obskit.health import create_memory_check

# Alert if memory > 90%
checker.add_readiness_check(
    "memory",
    create_memory_check(threshold_percent=90),
    critical=False,
)

# Custom threshold
checker.add_readiness_check(
    "memory_warning",
    create_memory_check(threshold_percent=80),
)
```

### Disk Check

```python
from obskit.health import create_disk_check

# Check root filesystem
checker.add_readiness_check(
    "disk_root",
    create_disk_check("/", threshold_percent=85),
)

# Check data volume
checker.add_readiness_check(
    "disk_data",
    create_disk_check("/data", threshold_percent=90),
    critical=True,
)
```

### HTTP Dependency Check

```python
from obskit.health import create_http_check

# Check external API
checker.add_readiness_check(
    "payment_api",
    create_http_check(
        "https://api.payment.com/health",
        expected_status=200,
        timeout=5.0,
    ),
    critical=True,
)

# Check with custom headers
checker.add_readiness_check(
    "internal_api",
    create_http_check(
        "http://internal-service:8080/health",
        headers={"X-Internal-Token": "secret"},
    ),
)
```

---

## Custom Health Checks

### Async Check Function

```python
@checker.add_readiness_check("database")
async def check_database():
    """Check database connectivity."""
    try:
        await db.execute("SELECT 1")
        return True
    except Exception as e:
        return False
```

### Check with Details

```python
@checker.add_readiness_check("database")
async def check_database():
    """Check with detailed response."""
    try:
        start = time.perf_counter()
        await db.execute("SELECT 1")
        latency = time.perf_counter() - start
        
        return {
            "healthy": True,
            "message": "Database connected",
            "details": {
                "latency_ms": latency * 1000,
                "pool_size": db.pool.size,
            },
        }
    except Exception as e:
        return {
            "healthy": False,
            "message": "Database connection failed",
            "error": str(e),
        }
```

### Sync Check Function

```python
def check_cache_sync():
    """Synchronous health check."""
    try:
        cache.ping()
        return True
    except Exception:
        return False

checker.add_readiness_check("cache", check_cache_sync)
```

### Critical vs Non-Critical

```python
# Critical: Service cannot function without this
checker.add_readiness_check(
    "database",
    check_database,
    critical=True,  # Readiness fails if this fails
)

# Non-critical: Service degraded but functional
checker.add_readiness_check(
    "cache",
    check_cache,
    critical=False,  # Warning only, readiness still passes
)
```

---

## Health Check Response

### Response Structure

```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connected",
      "details": {
        "latency_ms": 2.5
      }
    },
    "redis": {
      "status": "healthy",
      "message": "Redis ping successful"
    }
  },
  "timestamp": "2026-01-13T12:00:00Z"
}
```

### HTTP Status Codes

| Status | Code | When |
|--------|------|------|
| healthy | 200 | All critical checks pass |
| unhealthy | 503 | Any critical check fails |
| degraded | 200 | Non-critical check fails |

---

## FastAPI Integration

```python
from fastapi import FastAPI, Response
from obskit.health import HealthChecker, create_health_response

app = FastAPI()
checker = HealthChecker()

@app.get("/health")
async def health():
    result = await checker.check_health()
    response = create_health_response(result)
    return Response(
        content=response["body"],
        status_code=response["status_code"],
        media_type="application/json",
    )

@app.get("/ready")
async def ready():
    result = await checker.check_readiness()
    response = create_health_response(result)
    return Response(
        content=response["body"],
        status_code=response["status_code"],
        media_type="application/json",
    )

@app.get("/live")
async def live():
    result = await checker.check_liveness()
    response = create_health_response(result)
    return Response(
        content=response["body"],
        status_code=response["status_code"],
        media_type="application/json",
    )
```

---

## Kubernetes Configuration

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: app
        # Liveness probe - restart if unhealthy
        livenessProbe:
          httpGet:
            path: /live
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
          
        # Readiness probe - remove from load balancer if unhealthy
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
          
        # Startup probe - wait for initialization
        startupProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 0
          periodSeconds: 5
          timeoutSeconds: 5
          failureThreshold: 30  # 30 * 5 = 150s max startup
```

---

## Best Practices

### 1. Keep Liveness Checks Simple

```python
# ✅ GOOD - Simple heartbeat
@checker.add_liveness_check("heartbeat")
async def check_heartbeat():
    return True

# ❌ BAD - Don't check external dependencies in liveness
@checker.add_liveness_check("database")  # This should be readiness!
async def check_database():
    return await db.ping()
```

### 2. Appropriate Timeouts

```python
from obskit import configure

configure(
    health_check_timeout=5.0,  # Match Kubernetes probe timeout
)

# Per-check timeout
checker.add_readiness_check(
    "slow_dependency",
    create_http_check("http://slow-api/health", timeout=10.0),
)
```

### 3. Critical vs Non-Critical

```python
# Database is critical - can't serve requests without it
checker.add_readiness_check("database", check_db, critical=True)

# Cache is nice-to-have - requests slower but work
checker.add_readiness_check("cache", check_cache, critical=False)

# External API is critical for this operation
checker.add_readiness_check("payment_api", check_payment, critical=True)
```

### 4. Include Useful Details

```python
@checker.add_readiness_check("database")
async def check_database():
    return {
        "healthy": True,
        "message": "Connected",
        "details": {
            "active_connections": pool.size,
            "max_connections": pool.max_size,
            "latency_ms": 2.5,
        },
    }
```

---

## Troubleshooting

### Check Timeout

```
{"status": "unhealthy", "error": "Check timed out after 5.0s"}
```

**Solution:** Increase timeout or optimize check

```python
configure(health_check_timeout=10.0)
# or
create_redis_check(client, timeout=10.0)
```

### Dependency Unavailable

```
{"status": "unhealthy", "error": "Connection refused"}
```

**Solution:** Verify dependency is running and accessible

```bash
# Test connectivity
curl http://redis:6379
```

### Pod Restart Loop

If liveness probe fails, pod restarts continuously.

**Solution:** 
1. Check logs: `kubectl logs <pod>`
2. Increase `failureThreshold`
3. Don't check external dependencies in liveness

```yaml
livenessProbe:
  failureThreshold: 5  # More tolerance
```
