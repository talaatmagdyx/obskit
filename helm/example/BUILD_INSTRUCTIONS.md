# Building the Example Service

Since `obskit` is not yet published to PyPI, you need to build the Docker image using the local source.

## 🏗️ Building Options

### Option 1: Using the Build Script (Recommended)

```bash
cd helm/example

# Build image (tries editable install first)
./build.sh v1.0.0 my-registry.example.com/order-service

# If editable install fails, use simplified version
USE_SIMPLE=true ./build.sh v1.0.0 my-registry.example.com/order-service

# Build and push
./build.sh v1.0.0 my-registry.example.com/order-service push
```

### Option 2: Manual Docker Build

```bash
# From the repository root
cd /path/to/monitoring

# Build using Dockerfile.local (editable install)
docker build \
  -f obskit/helm/example/Dockerfile.local \
  -t my-registry.example.com/order-service:v1.0.0 \
  .

# OR use simplified version (no editable install, just copies source)
docker build \
  -f obskit/helm/example/Dockerfile.local-simple \
  -t my-registry.example.com/order-service:v1.0.0 \
  .
```

### Option 3: Install obskit Locally First

```bash
# From repository root
cd obskit
pip install -e ".[all]"

# Then build regular Dockerfile (but modify requirements.txt to not include obskit)
cd helm/example
docker build -f Dockerfile -t my-registry.example.com/order-service:v1.0.0 .
```

## 📝 Dockerfile Options

- **Dockerfile.local** - Installs obskit from local source (use this for now)
- **Dockerfile.production** - Installs obskit from PyPI (use after publishing)

## 🔄 After Publishing to PyPI

Once `obskit` is published to PyPI:

1. Update `requirements.txt`:
   ```txt
   obskit[all]>=0.1.0
   ```

2. Use `Dockerfile.production`:
   ```bash
   docker build -f Dockerfile.production -t my-registry/order-service:v1.0.0 .
   ```

## 🐛 Troubleshooting

### If editable install fails (README.md error)

Use the simplified Dockerfile:

```bash
USE_SIMPLE=true ./build.sh v1.0.0 my-registry/order-service
```

Or manually:

```bash
docker build \
  -f obskit/helm/example/Dockerfile.local-simple \
  -t my-registry/order-service:v1.0.0 \
  .
```

The simplified version:
- Installs all dependencies manually
- Copies obskit source to Python path
- No editable install needed
- Works around hatchling build issues

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for more help.

## 🚀 Quick Build & Deploy

```bash
# Build
./build.sh v1.0.0

# Deploy
./deploy.sh v1.0.0
```

