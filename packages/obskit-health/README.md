# obskit-health

Kubernetes-style health check endpoints (liveness, readiness, health) for Python services.

## Install

```bash
pip install obskit-health
```

## Quick start

```python
from obskit.health import HealthChecker, create_health_response

checker = HealthChecker()

@checker.add_readiness_check("database")
async def check_db():
    return await db.ping()   # True = healthy

@checker.add_readiness_check("redis", critical=False)
async def check_redis():
    return await redis.ping()

# FastAPI endpoints
@app.get("/health")
async def health():
    result = await checker.check_health()
    return create_health_response(result)

@app.get("/ready")
async def ready():
    result = await checker.check_readiness()
    return {"status_code": 200 if result.healthy else 503, "body": result.to_dict()}
```

## Trace context in health responses

When `obskit-tracing` is installed, health check responses automatically include `trace_id` and `span_id`:

```json
{
  "status": "healthy",
  "service": "order-service",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id":  "00f067aa0ba902b7"
}
```

## Built-in check helpers

```python
from obskit.health import create_redis_check, create_memory_check, create_http_check

checker.add_readiness_check("cache")(create_redis_check("redis://localhost"))
checker.add_liveness_check("memory")(create_memory_check(threshold_percent=95))
checker.add_readiness_check("upstream")(create_http_check("https://api.example.com/health"))
```

## Kubernetes probe config

```yaml
livenessProbe:
  httpGet: { path: /live, port: 8080 }
  initialDelaySeconds: 5
  periodSeconds: 10
readinessProbe:
  httpGet: { path: /ready, port: 8080 }
  initialDelaySeconds: 5
  periodSeconds: 5
```
