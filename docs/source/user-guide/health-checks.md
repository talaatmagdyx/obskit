# Health Checks Guide

Health checks allow orchestrators like Kubernetes to manage your service lifecycle.
obskit provides liveness and readiness probes following Kubernetes conventions.

## Why Health Checks?

### Liveness Probes

**Question:** "Is the application running?"

If liveness fails, Kubernetes restarts the container.

Use for:
- Detecting deadlocks
- Catching unrecoverable states
- Ensuring the process is alive

### Readiness Probes

**Question:** "Can the application serve traffic?"

If readiness fails, Kubernetes removes the pod from load balancing.

Use for:
- Database connectivity
- Cache availability
- External service dependencies

```{mermaid}
flowchart LR
    subgraph Kubernetes
        LB[Load Balancer]
        P1[Pod 1 - Ready]
        P2[Pod 2 - Not Ready]
        P3[Pod 3 - Ready]
    end
    
    LB --> P1
    LB -.->|"Excluded"| P2
    LB --> P3
```

## Basic Setup

```python
from obskit import get_health_checker

health = get_health_checker()

# Liveness: simple check that app is running
health.add_liveness_check("basic", lambda: True)

# Readiness: check dependencies
health.add_readiness_check("database", check_database)
health.add_readiness_check("redis", check_redis)
```

## Health Check Functions

Health check functions should return a boolean:

```python
def check_database() -> bool:
    try:
        db.execute("SELECT 1")
        return True
    except Exception:
        return False

async def check_external_api() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://api.example.com/health")
            return response.status_code == 200
    except Exception:
        return False
```

## FastAPI Integration

```python
from fastapi import FastAPI, HTTPException
from obskit import get_health_checker

app = FastAPI()
health = get_health_checker()

@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "healthy"}

@app.get("/ready")
async def readiness_check():
    """Readiness probe."""
    result = await health.check_readiness()
    
    if result.status.value != "healthy":
        raise HTTPException(status_code=503, detail=result.checks)
    
    return {
        "status": "ready",
        "checks": result.checks,
    }
```

## Kubernetes Configuration

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
spec:
  template:
    spec:
      containers:
        - name: app
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 3
```

## Check Types

### Synchronous Checks

```python
def check_file_exists() -> bool:
    return Path("/data/config.json").exists()

health.add_readiness_check("config", check_file_exists)
```

### Async Checks

```python
async def check_database() -> bool:
    async with db.acquire() as conn:
        await conn.execute("SELECT 1")
        return True

health.add_readiness_check("database", check_database)
```

### Checks with Timeout

```python
import asyncio

async def check_slow_service() -> bool:
    try:
        result = await asyncio.wait_for(
            call_slow_service(),
            timeout=5.0,
        )
        return result
    except asyncio.TimeoutError:
        return False

health.add_readiness_check("slow_service", check_slow_service)
```

## Detailed Status

```python
result = await health.check_readiness()

print(result.status)  # HealthStatus.HEALTHY or HealthStatus.UNHEALTHY
print(result.checks)  # {"database": True, "redis": True, "external_api": False}
```

### Response Format

```json
{
  "status": "healthy",
  "checks": {
    "database": true,
    "redis": true,
    "external_api": true
  }
}
```

Or when unhealthy:

```json
{
  "status": "unhealthy",
  "checks": {
    "database": true,
    "redis": false,
    "external_api": true
  }
}
```

## Best Practices

### 1. Keep Liveness Simple

```python
# Good: simple, fast check
health.add_liveness_check("alive", lambda: True)

# Bad: complex check that might hang
health.add_liveness_check("database", check_database)  # Use readiness instead
```

### 2. Set Appropriate Timeouts

```python
# Good: timeout prevents hanging
async def check_with_timeout():
    return await asyncio.wait_for(check_dependency(), timeout=3.0)

# Bad: no timeout, might hang indefinitely
async def check_no_timeout():
    return await check_dependency()  # Could hang forever
```

### 3. Fail Fast on Critical Dependencies

```python
# Database is critical - fail readiness if unavailable
health.add_readiness_check("database", check_database)

# Optional cache - don't fail readiness
# (app can work without it, just slower)
# health.add_readiness_check("cache", check_cache)  # Don't add
```

### 4. Use Startup Probes for Slow Starts

```yaml
# For applications that take time to initialize
startupProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 0
  periodSeconds: 5
  failureThreshold: 30  # Allow 2.5 minutes for startup
```

## Common Patterns

### Database Pool Check

```python
async def check_database_pool() -> bool:
    """Check that we can get a connection from the pool."""
    try:
        async with pool.acquire(timeout=1.0) as conn:
            await conn.execute("SELECT 1")
            return True
    except Exception:
        return False
```

### Redis Check

```python
def check_redis() -> bool:
    try:
        return redis_client.ping()
    except Exception:
        return False
```

### External API Check

```python
async def check_payment_provider() -> bool:
    try:
        response = await httpx.get(
            "https://api.stripe.com/health",
            timeout=5.0,
        )
        return response.status_code < 500
    except Exception:
        return False
```

### Disk Space Check

```python
import shutil

def check_disk_space() -> bool:
    usage = shutil.disk_usage("/")
    free_percent = usage.free / usage.total
    return free_percent > 0.1  # At least 10% free
```

## Troubleshooting

### Probe Failing After Deploy

1. Increase `initialDelaySeconds`
2. Check application startup logs
3. Verify dependencies are available

### Intermittent Failures

1. Increase `failureThreshold`
2. Add connection pooling
3. Check network stability

### Pod Keeps Restarting

1. Check liveness probe isn't too aggressive
2. Verify app isn't deadlocking
3. Check resource limits

## Next Steps

- **[Resilience Guide](resilience.md)** - Handle dependency failures
- **[Kubernetes Example](../examples/kubernetes.md)** - Full K8s deployment
- **[Troubleshooting](../troubleshooting/index.md)** - Common issues

