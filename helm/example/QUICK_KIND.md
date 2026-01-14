# Quick Kind Example - 3 Commands

The fastest way to deploy and test with Kind.

## 🚀 Deploy

```bash
cd helm/example
./deploy-kind.sh obskit-test v1.0.0
```

This script:
- ✅ Creates Kind cluster (if it doesn't exist)
- ✅ Builds Docker image
- ✅ Loads image into Kind
- ✅ Deploys with Helm
- ✅ Shows you next steps

## 🔌 Port Forward

In another terminal:

```bash
cd helm/example
./port-forward.sh
```

## 🧪 Test

In another terminal:

```bash
cd helm/example
./test-localhost.sh
```

## ✅ Done!

Your service is now running at:
- **Service:** http://localhost:8080
- **Metrics:** http://localhost:9090/metrics

## 🧹 Cleanup

```bash
kind delete cluster --name obskit-test
```

## 📚 More Details

See [KIND_EXAMPLE.md](./KIND_EXAMPLE.md) for complete guide.

