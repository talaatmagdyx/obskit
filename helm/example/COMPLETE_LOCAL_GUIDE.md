# Complete Local Development Guide

Step-by-step guide to run and test the obskit example service locally (no Docker, no Kubernetes).

## 📋 Prerequisites

- **Python 3.11+** installed
- **curl** for testing (or use a browser)
- **Git** (to clone the repository)

## 🚀 Step-by-Step Guide

### Step 1: Navigate to Example Directory

```bash
cd obskit/helm/example
```

### Step 2: Run the Service

```bash
./run-local.sh
```

**What this does:**
- ✅ Creates a Python virtual environment (`venv/`)
- ✅ Installs all dependencies (FastAPI, uvicorn, obskit, etc.)
- ✅ Sets up obskit from local source
- ✅ Starts the service on port 8080
- ✅ Starts metrics server on port 9090

**Expected output:**
```
🚀 Starting service locally (no Docker, no Kubernetes)

📦 Setting up Python environment...
   Creating virtual environment...
   Installing dependencies...
   PYTHONPATH: /path/to/monitoring/obskit/src:
✅ Environment ready

🌐 Starting service...
   Service: http://localhost:8080
   Metrics: http://localhost:9090/metrics
   Health: http://localhost:8080/health

Press Ctrl+C to stop
```

**Keep this terminal running!** The service is now running.

### Step 3: Test the Service (New Terminal)

Open a **new terminal** and run:

```bash
cd obskit/helm/example
./test-local.sh
```

**Or test manually:**

#### 3.1: Health Check

```bash
curl http://localhost:8080/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "checks": {}
}
```

#### 3.2: Readiness Check

```bash
curl http://localhost:8080/ready
```

**Expected response:**
```json
{
  "status": "ready",
  "checks": {
    "database": "healthy",
    "cache": "healthy"
  }
}
```

#### 3.3: Liveness Check

```bash
curl http://localhost:8080/live
```

**Expected response:**
```json
{
  "status": "alive",
  "checks": {}
}
```

#### 3.4: View Metrics

```bash
curl http://localhost:9090/metrics
```

**Expected output:**
```
# HELP order_service_requests_total Total number of requests
# TYPE order_service_requests_total counter
order_service_requests_total{endpoint="create_order",status="success"} 0.0
...
```

#### 3.5: Create an Order

```bash
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"id": "123", "amount": 100.0}'
```

**Expected response:**
```json
{
  "order_id": "order-123",
  "status": "created",
  "payment": {
    "id": "payment-order-123",
    "status": "completed",
    "amount": 100.0
  }
}
```

#### 3.6: Get Order

```bash
curl http://localhost:8080/orders/order-123
```

**Expected response:**
```json
{
  "order_id": "order-123",
  "status": "completed",
  "amount": 100.0
}
```

### Step 4: View Logs

In the terminal where the service is running, you'll see structured JSON logs:

```json
{"event": "service_starting", "timestamp": "2024-12-29T10:00:00Z", "level": "info"}
{"event": "metrics_server_started", "port": 9090, "timestamp": "2024-12-29T10:00:00Z", "level": "info"}
{"event": "service_started", "timestamp": "2024-12-29T10:00:00Z", "level": "info"}
{"event": "creating_order", "order_id": "123", "timestamp": "2024-12-29T10:01:00Z", "level": "info"}
```

### Step 5: Test Metrics Collection

Make several requests to generate metrics:

```bash
# Create multiple orders
for i in {1..5}; do
  curl -X POST http://localhost:8080/orders \
    -H "Content-Type: application/json" \
    -d "{\"id\": \"$i\", \"amount\": $((i * 10))}"
  echo ""
done

# View metrics (you should now see actual values!)
curl http://localhost:9090/metrics | grep order_service
```

**Note:** Initially, metrics show only type definitions. After making requests, you'll see actual values like:
```
order_service_requests_total{operation="create_order",status="success"} 5.0
order_service_request_duration_seconds_count{operation="create_order"} 5.0
```

**See [METRICS_GUIDE.md](./METRICS_GUIDE.md) for detailed metrics information!**

### Step 6: Stop the Service

In the terminal where the service is running:
- Press `Ctrl+C` to stop the service

## 🔧 Configuration

### Environment Variables

You can customize the service behavior with environment variables:

```bash
# Service name
export OBSKIT_SERVICE_NAME="my-service"

# Environment
export OBSKIT_ENVIRONMENT="development"

# Log level (DEBUG, INFO, WARNING, ERROR)
export OBSKIT_LOG_LEVEL="DEBUG"

# Enable/disable features
export OBSKIT_METRICS_ENABLED="true"
export OBSKIT_TRACING_ENABLED="false"  # Disable if no collector

# Ports
export PORT=8080
export OBSKIT_METRICS_PORT=9090
```

### Example: Run with Custom Configuration

```bash
export OBSKIT_LOG_LEVEL="DEBUG"
export OBSKIT_SERVICE_NAME="my-custom-service"
./run-local.sh
```

## 📊 Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ready` | GET | Readiness check |
| `/live` | GET | Liveness check |
| `/orders` | POST | Create a new order |
| `/orders/{order_id}` | GET | Get order by ID |
| `/metrics` | GET | Prometheus metrics (port 9090) |

## 🎯 What's Working

All obskit features are available locally:

- ✅ **Structured Logging** - JSON logs to console
- ✅ **RED Metrics** - Rate, Errors, Duration tracking
- ✅ **Health Checks** - `/health`, `/ready`, `/live` endpoints
- ✅ **Circuit Breaker** - For external API calls
- ✅ **Retry Logic** - Automatic retries with exponential backoff
- ✅ **Prometheus Metrics** - Available at `:9090/metrics`
- ✅ **Correlation IDs** - Automatic request tracking
- ✅ **FastAPI Middleware** - Automatic observability

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Check what's using the port
lsof -i :8080
lsof -i :9090

# Use different ports
export PORT=8081
export OBSKIT_METRICS_PORT=9091
./run-local.sh
```

### Import Errors

```bash
# Verify PYTHONPATH is set correctly
echo $PYTHONPATH

# Should show: /path/to/monitoring/obskit/src

# Verify obskit is accessible
python3 -c "import obskit; print(obskit.__file__)"
```

### Virtual Environment Issues

```bash
# Remove and recreate
rm -rf venv
./run-local.sh
```

### Service Not Responding

```bash
# Check if service is running
curl http://localhost:8080/health

# Check logs in the service terminal
# Look for error messages

# Verify Python version
python3 --version  # Should be 3.11+
```

## 📚 Next Steps

Once you've tested locally:

1. **Kubernetes Deployment** - See [KIND_EXAMPLE.md](./KIND_EXAMPLE.md)
2. **Production Setup** - See [COMPLETE_EXAMPLE.md](./COMPLETE_EXAMPLE.md)
3. **Helm Chart** - See [README.md](./README.md)

## 🧹 Cleanup

When you're done:

```bash
# Stop the service (Ctrl+C)

# Optional: Remove virtual environment
rm -rf venv
```

## 📝 Quick Reference

### Start Service
```bash
./run-local.sh
```

### Test Service
```bash
./test-local.sh
```

### Manual Test
```bash
curl http://localhost:8080/health
curl http://localhost:9090/metrics
```

### Stop Service
```bash
# Press Ctrl+C in the service terminal
```

## ✅ Success Checklist

- [ ] Service starts without errors
- [ ] Health endpoint returns 200
- [ ] Metrics endpoint returns metrics
- [ ] Can create orders
- [ ] Can retrieve orders
- [ ] Logs are in JSON format
- [ ] Metrics are being collected

## 🎉 You're Done!

You've successfully:
- ✅ Set up a local development environment
- ✅ Run the obskit example service
- ✅ Tested all endpoints
- ✅ Viewed metrics and logs

The service is now ready for local development and testing!

