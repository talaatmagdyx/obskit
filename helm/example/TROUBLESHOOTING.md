# Troubleshooting Guide

Common issues and solutions when deploying the Helm chart example.

## 🐛 Common Issues

### 1. `kind load docker-image` Appears Stuck

**Symptom:** The command shows "loading..." and seems to hang.

**Cause:** `kind load docker-image` can take 1-2 minutes for larger images. It's copying the entire Docker image into the kind container, which involves:
- Exporting the image from Docker
- Copying it into the kind container
- Importing it into containerd

**Solution:**
- **Wait it out:** The process is working, just be patient (1-2 minutes for ~500MB images)
- **Check progress:** In another terminal, run:
  ```bash
  docker exec obskit-test-control-plane crictl images | grep order-service
  ```
- **Skip if already loaded:** The script now checks if the image is already loaded and skips if present
- **Manual load:** If it truly hangs, cancel (Ctrl+C) and manually load:
  ```bash
  kind load docker-image localhost/order-service:v1.0.0 --name obskit-test
  ```

**Why it's slow:**
- Docker images can be large (hundreds of MB)
- Kind runs in a container, so images must be copied into it
- The copy happens over Docker's internal network

### 2. Image Not Found in Kind

**Symptom:** Pod shows `ImagePullBackOff` or `ErrImagePull`.

**Solution:**
```bash
# Verify image exists locally
docker images | grep order-service

# Verify image is loaded in kind
docker exec obskit-test-control-plane crictl images | grep order-service

# Reload if needed
kind load docker-image localhost/order-service:v1.0.0 --name obskit-test
```

### 3. Pod Not Starting

**Symptom:** Pod stays in `Pending` or `CrashLoopBackOff`.

**Check:**
```bash
# Describe pod for details
kubectl describe pod -n local -l app.kubernetes.io/name=obskit-service

# Check events
kubectl get events -n local --sort-by='.lastTimestamp'

# View logs
kubectl logs -n local -l app.kubernetes.io/name=obskit-service
```

**Common causes:**
- Image not loaded (see #2)
- Resource constraints (not enough CPU/memory)
- Health check failing

### 4. Port Forward Fails

**Symptom:** `kubectl port-forward` fails or connection refused.

**Solution:**
```bash
# Check if service exists
kubectl get svc -n local

# Check if pods are running
kubectl get pods -n local

# Try different ports
kubectl port-forward -n local svc/order-service 8081:80 9091:9090

# Check if ports are already in use
lsof -i :8080
lsof -i :9090
```

### 5. Build Fails: obskit Not Found

**Symptom:** Docker build fails with "ModuleNotFoundError: No module named 'obskit'".

**Solution:**
```bash
# Make sure you're using the simple Dockerfile
USE_SIMPLE=true ./build.sh v1.0.0 localhost/order-service

# Verify obskit source exists
ls -la ../../src/obskit

# Check build context is correct (should be repo root)
docker build -f Dockerfile.local-simple -t test .
```

### 6. Helm Install Fails

**Symptom:** `helm install` fails with validation errors.

**Check:**
```bash
# Validate values
helm template ../obskit --values values-localhost.yaml --debug

# Check for syntax errors
helm lint ../obskit --values values-localhost.yaml
```

### 7. Service Not Responding

**Symptom:** `curl http://localhost:8080/health` fails.

**Check:**
```bash
# Verify port-forward is running
ps aux | grep port-forward

# Check pod logs
kubectl logs -n local -l app.kubernetes.io/name=obskit-service -f

# Test inside the pod
kubectl exec -n local -it deployment/order-service -- curl http://localhost:8080/health
```

### 8. Metrics Endpoint Not Accessible

**Symptom:** `curl http://localhost:9090/metrics` fails.

**Check:**
```bash
# Verify metrics port is forwarded
kubectl port-forward -n local svc/order-service 8080:80 9090:9090

# Check if metrics auth is enabled
kubectl get deployment -n local order-service -o yaml | grep -i metrics

# Test inside pod
kubectl exec -n local deployment/order-service -- curl http://localhost:9090/metrics
```

### 9. Kind Cluster Issues

**Symptom:** Kind cluster won't start or is unresponsive.

**Solution:**
```bash
# Delete and recreate
kind delete cluster --name obskit-test
kind create cluster --name obskit-test

# Check Docker resources
docker ps
docker stats

# Restart Docker Desktop (if on macOS/Windows)
```

### 10. Out of Disk Space

**Symptom:** Build or deployment fails with disk space errors.

**Solution:**
```bash
# Check Docker disk usage
docker system df

# Clean up unused images
docker image prune -a

# Clean up kind clusters
kind delete cluster --name obskit-test
```

## 🔍 Debugging Commands

### Check Everything is Running

```bash
# Cluster status
kubectl cluster-info
kubectl get nodes

# Namespace resources
kubectl get all -n local

# Pod details
kubectl describe pod -n local -l app.kubernetes.io/name=obskit-service

# Service endpoints
kubectl get endpoints -n local
```

### View Logs

```bash
# All pods
kubectl logs -n local -l app.kubernetes.io/name=obskit-service --tail=100

# Specific pod
POD=$(kubectl get pods -n local -l app.kubernetes.io/name=obskit-service -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n local $POD -f

# Previous container (if crashed)
kubectl logs -n local $POD --previous
```

### Inspect Resources

```bash
# Deployment
kubectl get deployment -n local order-service -o yaml

# Service
kubectl get service -n local order-service -o yaml

# ConfigMap
kubectl get configmap -n local -o yaml

# Secrets
kubectl get secret -n local -o yaml
```

## 🚀 Quick Fixes

### Reset Everything

```bash
# Delete Helm release
helm uninstall order-service -n local

# Delete namespace
kubectl delete namespace local

# Delete kind cluster
kind delete cluster --name obskit-test

# Rebuild and redeploy
cd helm/example
./deploy-kind.sh obskit-test v1.0.0
```

### Rebuild Image Only

```bash
cd helm/example
USE_SIMPLE=true ./build.sh v1.0.1 localhost/order-service
kind load docker-image localhost/order-service:v1.0.1 --name obskit-test
helm upgrade order-service ../obskit \
  --namespace local \
  --values values-localhost.yaml \
  --set image.tag=v1.0.1 \
  --reuse-values
kubectl rollout restart deployment/order-service -n local
```

## 📚 Additional Resources

- [Kind Documentation](https://kind.sigs.k8s.io/)
- [Kubernetes Troubleshooting](https://kubernetes.io/docs/tasks/debug/)
- [Helm Troubleshooting](https://helm.sh/docs/intro/using_helm/#troubleshooting)
