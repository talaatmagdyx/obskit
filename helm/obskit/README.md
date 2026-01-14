# obskit Helm Chart

This Helm chart simplifies deployment of services using the obskit observability toolkit to Kubernetes.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- Prometheus Operator (optional, for ServiceMonitor)

## Installation

### Basic Installation

```bash
helm install my-service ./helm/obskit \
  --set obskit.serviceName=my-service \
  --set image.repository=my-registry/my-service \
  --set image.tag=v1.0.0
```

### With Custom Configuration

```bash
helm install my-service ./helm/obskit \
  --set obskit.serviceName=order-service \
  --set obskit.environment=production \
  --set obskit.metricsSampleRate=0.1 \
  --set obskit.logSampleRate=0.01 \
  --set image.repository=my-registry/order-service \
  --set image.tag=v1.2.3
```

### With Metrics Authentication

```bash
helm install my-service ./helm/obskit \
  --set obskit.metricsAuthEnabled=true \
  --set secrets.metricsAuthToken=your-secret-token
```

## Configuration

### obskit Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `obskit.serviceName` | Service name | `your-service` |
| `obskit.environment` | Environment | `production` |
| `obskit.version` | Service version | `1.0.0` |
| `obskit.logLevel` | Log level | `INFO` |
| `obskit.logFormat` | Log format | `json` |
| `obskit.logSampleRate` | Log sampling rate | `0.1` |
| `obskit.metricsEnabled` | Enable metrics | `true` |
| `obskit.metricsPort` | Metrics port | `9090` |
| `obskit.metricsSampleRate` | Metrics sampling rate | `0.1` |
| `obskit.metricsAuthEnabled` | Metrics auth | `true` |
| `obskit.tracingEnabled` | Enable tracing | `true` |
| `obskit.otlpEndpoint` | OTLP endpoint | `http://jaeger-collector:4317` |
| `obskit.traceSampleRate` | Trace sampling rate | `0.1` |

### Service Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `3` |
| `image.repository` | Container image | Required |
| `image.tag` | Image tag | `latest` |
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `80` |
| `service.metricsPort` | Metrics port | `9090` |

### ServiceMonitor

| Parameter | Description | Default |
|-----------|-------------|---------|
| `serviceMonitor.enabled` | Enable ServiceMonitor | `true` |
| `serviceMonitor.interval` | Scrape interval | `30s` |
| `serviceMonitor.path` | Metrics path | `/metrics` |

## Examples

### Development Environment

```yaml
obskit:
  environment: development
  logLevel: DEBUG
  logFormat: console
  metricsSampleRate: 1.0
  logSampleRate: 1.0
  traceSampleRate: 1.0
```

### High-Frequency Service

```yaml
obskit:
  metricsSampleRate: 0.01  # 1% sampling
  logSampleRate: 0.001     # 0.1% sampling
  traceSampleRate: 0.01    # 1% sampling
```

### Production with Auth

```yaml
obskit:
  metricsAuthEnabled: true
  otlpInsecure: false  # Use TLS

secrets:
  metricsAuthToken: "your-secret-token"
```

## Uninstallation

```bash
helm uninstall my-service
```

## Upgrading

```bash
helm upgrade my-service ./helm/obskit \
  --set image.tag=v1.2.4
```

## See Also

- [Production Deployment Guide](../../docs/PRODUCTION_DEPLOYMENT.md)
- [obskit Documentation](../../README.md)

