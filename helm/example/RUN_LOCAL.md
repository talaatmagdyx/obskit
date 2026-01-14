# Run Service Locally (No Docker, No Kubernetes)

The simplest way to test obskit - run the service directly with Python!

## 🚀 Quick Start

```bash
cd helm/example

# Run the service (creates venv, installs deps, starts server)
./run-local.sh
```

That's it! The service will be available at:
- **Service:** http://localhost:8080
- **Metrics:** http://localhost:9090/metrics
- **Health:** http://localhost:8080/health

## 📋 What It Does

The `run-local.sh` script:
1. ✅ Creates a Python virtual environment
2. ✅ Installs all dependencies (FastAPI, obskit, etc.)
3. ✅ Sets up obskit from local source
4. ✅ Starts the service on port 8080
5. ✅ Starts metrics server on port 9090

## 🧪 Test the Service

**In another terminal:**

```bash
# Health check
curl http://localhost:8080/health

# Metrics
curl http://localhost:9090/metrics

# Create an order
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"id": "123", "amount": 100.0}'

# Get order
curl http://localhost:8080/orders/order-123
```

## 🔧 Manual Setup (Alternative)

If you prefer to set it up manually:

```bash
cd helm/example

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn[standard] pydantic structlog pydantic-settings prometheus-client

# Set Python path to include obskit
export PYTHONPATH="../../obskit/src:$PYTHONPATH"

# Run the service
python3 test-service.py
```

## ⚙️ Configuration

The service uses environment variables (with defaults):

```bash
export OBSKIT_SERVICE_NAME="order-service"
export OBSKIT_ENVIRONMENT="local"
export OBSKIT_METRICS_ENABLED="true"
export OBSKIT_TRACING_ENABLED="false"  # Disabled for local (no collector)
export OBSKIT_METRICS_PORT="9090"
export PORT="8080"
```

## 🎯 Features Available

All obskit features work locally:
- ✅ **Structured Logging** - JSON logs to console
- ✅ **RED Metrics** - Rate, Errors, Duration
- ✅ **Health Checks** - `/health`, `/ready`, `/live`
- ✅ **Circuit Breaker** - For external calls
- ✅ **Retry Logic** - Automatic retries
- ✅ **Prometheus Metrics** - Available at `/metrics`

## 🐛 Troubleshooting

### Python Not Found
```bash
# Install Python 3.11+
brew install python@3.11  # macOS
# OR
sudo apt install python3.11  # Linux
```

### Port Already in Use
```bash
# Change port
export PORT=8081
export OBSKIT_METRICS_PORT=9091
./run-local.sh
```

### Import Errors
```bash
# Make sure PYTHONPATH is set
export PYTHONPATH="../../obskit/src:$PYTHONPATH"

# Verify obskit is accessible
python3 -c "import obskit; print(obskit.__file__)"
```

## 📊 View Metrics

Once running, you can:
1. **View in browser:** http://localhost:9090/metrics
2. **Use curl:** `curl http://localhost:9090/metrics | grep order_service`
3. **Use Prometheus:** Scrape from `localhost:9090/metrics`

## 🧹 Cleanup

Just press `Ctrl+C` to stop the service. The virtual environment will remain for next time.

To remove everything:
```bash
rm -rf venv
```

## 🚀 Next Steps

Once you've tested locally:
- See [KIND_EXAMPLE.md](./KIND_EXAMPLE.md) for Kubernetes deployment
- See [COMPLETE_EXAMPLE.md](./COMPLETE_EXAMPLE.md) for production setup
- See [README.md](./README.md) for all options

