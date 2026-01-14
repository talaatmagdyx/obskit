# Complete Helm Chart Example

This directory contains a **complete, production-ready example** of deploying a service with obskit using Helm.

## 📁 Files

- **values.yaml** - Complete production configuration
- **values-localhost.yaml** - Localhost/local development configuration ⭐
- **deploy.sh** - Automated deployment script (production)
- **deploy-localhost.sh** - Automated deployment script (localhost)
- **deploy-kind.sh** - Automated deployment script for Kind ⭐ **USE THIS FOR KIND**
- **port-forward.sh** - Convenience script for port-forwarding ⭐
- **test-localhost.sh** - Test script for localhost deployment ⭐
- **build.sh** - Build script for Docker image
- **test-service.py** - Example FastAPI service using obskit
- **Dockerfile.local** - Container image (installs obskit from local source)
- **Dockerfile.local-simple** - Simplified container image (no editable install)
- **Dockerfile.production** - Container image (for when obskit is published to PyPI)
- **requirements.txt** - Python dependencies
- **COMPLETE_LOCAL_GUIDE.md** - Complete step-by-step local guide ⭐⭐ **START HERE**
- **METRICS_GUIDE.md** - Understanding and using metrics ⭐
- **GRAFANA_LOCAL.md** - Local Grafana dashboard (no Docker/K8s) ⭐⭐
- **GRAFANA_DASHBOARDS.md** - Grafana dashboard setup for Kubernetes ⭐
- **RUN_LOCAL.md** - Quick local run guide
- **COMPLETE_EXAMPLE.md** - Detailed production deployment guide
- **LOCALHOST_EXAMPLE.md** - Complete localhost deployment guide
- **KIND_EXAMPLE.md** - Complete Kind (Kubernetes in Docker) guide ⭐ **READ THIS FOR KIND**
- **QUICK_START.md** - 5-minute quick start
- **BUILD_INSTRUCTIONS.md** - Build instructions
- **TROUBLESHOOTING.md** - Troubleshooting guide

## 🚀 Quick Start: Local (No Docker, No Kubernetes) ⭐⭐ **EASIEST**

### Run Directly with Python

```bash
cd helm/example

# Run locally (no Docker, no K8s needed!)
./run-local.sh
```

Then test (in another terminal):
```bash
cd helm/example
./test-local.sh
```

**See [COMPLETE_LOCAL_GUIDE.md](./COMPLETE_LOCAL_GUIDE.md) for complete step-by-step instructions!** ⭐

## 🚀 Quick Start: Kind (Kubernetes in Docker) ⭐

### One-Command Deployment

**⚠️ If `kind load docker-image` hangs, use the registry method instead!**

```bash
cd helm/example

# Fast method using local registry (RECOMMENDED - much faster!)
./deploy-kind-registry.sh obskit-test v1.0.0

# OR traditional method (may hang with large images)
./deploy-kind.sh obskit-test v1.0.0
```

**Why use registry method?**
- ✅ Much faster (seconds vs minutes)
- ✅ More reliable (no hanging)
- ✅ Standard Docker workflow

### Access the Service

**Terminal 1: Port-forward**
```bash
./port-forward.sh
# OR
kubectl port-forward -n local svc/order-service 8080:80 9090:9090
```

**Terminal 2: Test**
```bash
# Using test script
./test-localhost.sh

# Or manually:
curl http://localhost:8080/health
curl http://localhost:9090/metrics
```

## 🎯 Complete Kind Workflow

```bash
# 1. Deploy (creates cluster if needed, builds, loads, deploys)
./deploy-kind.sh obskit-test v1.0.0

# 2. Port-forward (in another terminal)
./port-forward.sh

# 3. Test (in another terminal)
./test-localhost.sh

# 4. View logs
kubectl logs -n local -l app.kubernetes.io/name=obskit-service -f

# 5. Cleanup when done
kind delete cluster --name obskit-test
```

## 🚀 Quick Start: Other Local Kubernetes

### Docker Desktop
```bash
./deploy-localhost.sh v1.0.0
./port-forward.sh
./test-localhost.sh
```

### Minikube
```bash
minikube start
./deploy-localhost.sh v1.0.0
./port-forward.sh
./test-localhost.sh
```

## 🚀 Production Deployment

```bash
# 1. Build image
./build.sh v1.0.0 my-registry/order-service

# 2. Push image
docker push my-registry/order-service:v1.0.0

# 3. Deploy
./deploy.sh v1.0.0
```

## 📚 Documentation

- **[KIND_EXAMPLE.md](./KIND_EXAMPLE.md)** ⭐ - Complete Kind guide (start here for kind!)
- **[LOCALHOST_EXAMPLE.md](./LOCALHOST_EXAMPLE.md)** - General localhost guide
- **[QUICK_START.md](./QUICK_START.md)** - Get started in 5 minutes
- **[COMPLETE_EXAMPLE.md](./COMPLETE_EXAMPLE.md)** - Full production deployment guide
- **[BUILD_INSTRUCTIONS.md](./BUILD_INSTRUCTIONS.md)** - How to build the Docker image
- **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** - Common issues and solutions

## 🎯 What This Example Includes

✅ Complete Helm values for production  
✅ Localhost-specific values for local development  
✅ Example FastAPI service with obskit  
✅ Dockerfile with security best practices  
✅ Automated deployment scripts  
✅ Test scripts  
✅ Build script for local development  
✅ Health check configuration  
✅ Metrics authentication (configurable)  
✅ Prometheus ServiceMonitor  
✅ Auto-scaling configuration  
✅ Security hardening  

## 🔧 Building the Image

Since obskit is not yet published to PyPI, use the build script:

```bash
# Build image (installs obskit from local source)
USE_SIMPLE=true ./build.sh v1.0.0 localhost/order-service
```

## 📊 Testing Locally

### Quick Test

```bash
# After deployment and port-forward:
./test-localhost.sh
```

### Manual Testing

```bash
# Health endpoints
curl http://localhost:8080/health
curl http://localhost:8080/ready
curl http://localhost:8080/live

# Metrics
curl http://localhost:9090/metrics

# Business logic
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"id": "123", "amount": 100.0}'
```

## 🆘 Need Help?

- **Kind deployment:** See [KIND_EXAMPLE.md](./KIND_EXAMPLE.md) ⭐
- **Localhost deployment:** See [LOCALHOST_EXAMPLE.md](./LOCALHOST_EXAMPLE.md)
- **Build issues:** See [BUILD_INSTRUCTIONS.md](./BUILD_INSTRUCTIONS.md)
- **Troubleshooting:** See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- **Production deployment:** See [COMPLETE_EXAMPLE.md](./COMPLETE_EXAMPLE.md)
