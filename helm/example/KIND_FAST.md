# Fast Kind Deployment (Alternative Method)

If `kind load docker-image` is hanging or taking too long (>5 minutes), use this faster method.

## 🚀 Quick Fix: Use Local Registry (Recommended)

This method is **much faster** and more reliable:

```bash
cd helm/example

# Use the registry-based deployment (fast!)
./deploy-kind-registry.sh obskit-test v1.0.0
```

This script:
1. Creates a kind cluster configured for local registry
2. Starts a local Docker registry
3. Builds and pushes the image to the registry
4. Deploys using the registry (fast pull)

## 🔧 What Changed

The new script (`deploy-kind-registry.sh`) uses a **local Docker registry** instead of `kind load docker-image`:

- ✅ **Much faster** - Push/pull is faster than copying into container
- ✅ **More reliable** - No hanging issues
- ✅ **Standard approach** - Uses normal Docker registry workflow

## 📋 Manual Steps (If Script Doesn't Work)

### 1. Start Local Registry

```bash
docker run -d --name kind-registry \
  --restart=unless-stopped \
  -p 5000:5000 \
  registry:2
```

### 2. Create Kind Cluster with Registry Support

```bash
cat <<EOF | kind create cluster --name obskit-test --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5000"]
    endpoint = ["http://localhost:5000"]
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 5000
    hostPort: 5000
    protocol: TCP
EOF
```

### 3. Connect Registry to Kind Network

```bash
docker network connect kind kind-registry
```

### 4. Build and Push Image

```bash
cd helm/example

# Build with registry name
USE_SIMPLE=true ./build.sh v1.0.0 localhost:5000/order-service

# Push to registry
docker push localhost:5000/order-service:v1.0.0
```

### 5. Deploy

```bash
./deploy-localhost.sh v1.0.0 localhost:5000/order-service
```

## 🔄 Alternative: Direct Import Method

If registry doesn't work, try direct import:

```bash
# Save image to tar
docker save localhost/order-service:v1.0.0 -o /tmp/image.tar

# Import directly into kind
docker exec -i obskit-test-control-plane ctr --namespace=k8s.io images import - < /tmp/image.tar

# Cleanup
rm /tmp/image.tar
```

## 🧹 Cleanup

```bash
# Stop registry
docker stop kind-registry
docker rm kind-registry

# Delete cluster
kind delete cluster --name obskit-test
```

## 🐛 Why `kind load docker-image` Hangs

Common causes:
1. **Large image size** - Copying 500MB+ can be slow
2. **Docker daemon issues** - Resource constraints
3. **Network issues** - Between Docker and kind container
4. **File system issues** - Slow disk I/O

The registry method avoids all these by using Docker's native push/pull mechanism.

