# How to Run the Local Observability Stack

This guide walks you through running a complete local observability stack with
**Prometheus**, **Grafana Tempo**, **Grafana Loki**, and **Grafana** using Docker
Compose.  After following it you will have a working environment where your Python
service sends traces to Tempo, logs to Loki, and metrics to Prometheus — all browsable
through a single Grafana instance at `http://localhost:3000`.

---

## Stack overview

```
Your Python service
  ├── OTLP traces  ──────────────────► Grafana Tempo  (port 4317)
  ├── JSON logs ──► Promtail ─────────► Grafana Loki   (port 3100)
  └── /metrics ───────────────────────► Prometheus     (port 9090)
                                              │
                                        Grafana (port 3000)
                                     ┌────────┴─────────┐
                                   Tempo            Loki
                                 (traces)           (logs)
```

| Service | Port | Purpose |
|---------|------|---------|
| Grafana | 3000 | Dashboards and Explore UI |
| Prometheus | 9090 | Metrics storage and PromQL |
| Grafana Tempo | 3200 | Trace storage (OTLP receiver on 4317) |
| Grafana Loki | 3100 | Log aggregation |
| Promtail | — | Log scraper (Docker container logs → Loki) |

---

## Prerequisites

- Docker 24+ and Docker Compose v2
- Your Python service listening on port 8000
- `pip install obskit-logging obskit-tracing obskit-metrics obskit-health`

---

## Directory structure

Create the following directory tree alongside your application:

```
observability/
├── docker-compose.yml
├── prometheus.yml
├── tempo.yml
├── loki-config.yml
├── promtail-config.yml
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── datasources.yml
        └── dashboards/
            └── dashboards.yml
```

---

## docker-compose.yml

```yaml
# observability/docker-compose.yml
version: "3.8"

networks:
  observability:
    driver: bridge

volumes:
  prometheus_data: {}
  grafana_data: {}
  tempo_data: {}
  loki_data: {}

services:

  # ── Prometheus ──────────────────────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:v2.51.0
    container_name: obskit-prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      - "--storage.tsdb.retention.time=7d"
      - "--web.enable-remote-write-receiver"
      - "--enable-feature=exemplar-storage"   # Required for trace exemplars
    networks:
      - observability

  # ── Grafana Tempo ───────────────────────────────────────────────────────────
  tempo:
    image: grafana/tempo:2.4.1
    container_name: obskit-tempo
    restart: unless-stopped
    ports:
      - "3200:3200"    # Tempo HTTP API
      - "4317:4317"    # OTLP gRPC receiver (your app sends traces here)
      - "4318:4318"    # OTLP HTTP receiver
    volumes:
      - ./tempo.yml:/etc/tempo.yml:ro
      - tempo_data:/tmp/tempo
    command: ["-config.file=/etc/tempo.yml"]
    networks:
      - observability

  # ── Grafana Loki ────────────────────────────────────────────────────────────
  loki:
    image: grafana/loki:2.9.6
    container_name: obskit-loki
    restart: unless-stopped
    ports:
      - "3100:3100"
    volumes:
      - ./loki-config.yml:/etc/loki/loki-config.yml:ro
      - loki_data:/loki
    command: ["-config.file=/etc/loki/loki-config.yml"]
    networks:
      - observability

  # ── Promtail (log collector) ─────────────────────────────────────────────────
  promtail:
    image: grafana/promtail:2.9.6
    container_name: obskit-promtail
    restart: unless-stopped
    volumes:
      - ./promtail-config.yml:/etc/promtail/promtail-config.yml:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock
    command: ["-config.file=/etc/promtail/promtail-config.yml"]
    networks:
      - observability

  # ── Grafana ─────────────────────────────────────────────────────────────────
  grafana:
    image: grafana/grafana:10.4.2
    container_name: obskit-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
      - GF_AUTH_DISABLE_LOGIN_FORM=true
      - GF_FEATURE_TOGGLES_ENABLE=traceqlEditor
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    depends_on:
      - prometheus
      - tempo
      - loki
    networks:
      - observability
```

---

## prometheus.yml

```yaml
# observability/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "order-service"
    honor_timestamps: true
    static_configs:
      # host.docker.internal resolves to your Mac/Linux host from inside a container
      - targets: ["host.docker.internal:8000"]
        labels:
          app: "order-service"
          env: "local"
    # Request OpenMetrics format so trace exemplars are included
    metrics_path: /metrics
    scheme: http
```

!!! tip "Linux hosts"
    On Linux, `host.docker.internal` is not available by default.  Add
    `extra_hosts: ["host.docker.internal:host-gateway"]` to the `prometheus` service
    definition, or use your host's Docker bridge IP (typically `172.17.0.1`).

---

## tempo.yml

```yaml
# observability/tempo.yml
stream_over_http_enabled: true

server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: "0.0.0.0:4317"
        http:
          endpoint: "0.0.0.0:4318"

storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/blocks

compactor:
  compaction:
    block_retention: 48h

metrics_generator:
  storage:
    path: /tmp/tempo/generator/wal
    remote_write:
      - url: http://prometheus:9090/api/v1/write
        send_exemplars: true

overrides:
  defaults:
    metrics_generator:
      processors: [service-graphs, span-metrics]
```

---

## loki-config.yml

```yaml
# observability/loki-config.yml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: "2024-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: loki_index_
        period: 24h

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 16
  ingestion_burst_size_mb: 32
```

---

## promtail-config.yml

```yaml
# observability/promtail-config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: "docker-containers"
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ["__meta_docker_container_name"]
        regex: "/(.*)"
        target_label: "container"
      - source_labels: ["__meta_docker_container_label_com_docker_compose_service"]
        target_label: "service"
    pipeline_stages:
      - json:
          expressions:
            level: level
            trace_id: trace_id
            span_id: span_id
            event: event
      - labels:
          level:
          trace_id:
          span_id:
```

---

## Grafana datasource provisioning

```yaml
# observability/grafana/provisioning/datasources/datasources.yml
apiVersion: 1

datasources:

  - name: Prometheus
    type: prometheus
    uid: prometheus
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      exemplarTraceIdDestinations:
        - name: trace_id
          datasourceUid: tempo

  - name: Tempo
    type: tempo
    uid: tempo
    url: http://tempo:3200
    jsonData:
      tracesToLogsV2:
        datasourceUid: loki
        spanStartTimeShift: "-1m"
        spanEndTimeShift: "1m"
        tags:
          - key: service.name
            value: app
        filterByTraceID: true
        filterBySpanID: false
      serviceMap:
        datasourceUid: prometheus
      nodeGraph:
        enabled: true

  - name: Loki
    type: loki
    uid: loki
    url: http://loki:3100
    jsonData:
      derivedFields:
        - name: TraceID
          matcherRegex: '"trace_id":"([a-f0-9]+)"'
          url: "$${__value.raw}"
          datasourceUid: tempo
          urlDisplayLabel: "View trace in Tempo"
```

---

## Starting the stack

```bash
cd observability
docker compose up -d
```

Verify all containers are healthy:

```bash
docker compose ps
```

Expected output:

```
NAME                 IMAGE                        STATUS
obskit-grafana       grafana/grafana:10.4.2       Up (healthy)
obskit-loki          grafana/loki:2.9.6           Up
obskit-prometheus    prom/prometheus:v2.51.0      Up
obskit-promtail      grafana/promtail:2.9.6       Up
obskit-tempo         grafana/tempo:2.4.1          Up
```

---

## Configuring your Python service

Set the OTLP endpoint environment variable before starting your service:

```bash
export OBSKIT_OTLP_ENDPOINT=http://localhost:4317

# Or pass it directly to uvicorn:
OBSKIT_OTLP_ENDPOINT=http://localhost:4317 uvicorn app.main:app --port 8000
```

In your application code:

```python
import os
from obskit.tracing import setup_tracing
from obskit.logging import get_logger

setup_tracing(
    service_name="order-service",
    exporter_endpoint=os.getenv("OBSKIT_OTLP_ENDPOINT", "http://localhost:4317"),
)

log = get_logger("order_service")
log.info("startup", otlp_endpoint=os.getenv("OBSKIT_OTLP_ENDPOINT"))
```

---

## Verifying the stack

### Prometheus

Open `http://localhost:9090/targets` and confirm `order-service` shows **UP**.

If the target is down, check:

- Is your service running on port 8000?
- Is `host.docker.internal` resolving correctly (see Linux note above)?

### Tempo

Send a test trace with obskit and then query Tempo:

```bash
curl http://localhost:3200/api/search?limit=5
```

You should see recent trace summaries in the JSON response.

### Loki

```bash
curl "http://localhost:3100/loki/api/v1/query?query={container%3D\"order-service\"}&limit=5"
```

### Grafana

Open `http://localhost:3000` (no login required — anonymous admin access is enabled).

Navigate to **Explore** and:

1. Select the **Loki** datasource.
2. Run: `{container="order-service"} | json`
3. Click any `trace_id` value → Grafana jumps to the Tempo trace.

---

## Pro tips

### Log-to-trace correlation in Explore

1. Open Grafana Explore.
2. Select **Loki** and run a query such as:
   ```logql
   {container="order-service"} | json | level="error"
   ```
3. Expand any log line that has a `trace_id` field.
4. Click the **View trace in Tempo** link next to the `trace_id` value.

### Trace-to-metrics with Tempo metrics generator

The `tempo.yml` above enables the Tempo **metrics generator** which automatically
derives `service_graph_*` and `traces_spanmetrics_*` Prometheus metrics from your
trace data.  In Grafana, add a panel with:

```promql
histogram_quantile(0.99,
  sum by (le, client, server) (
    rate(traces_service_graph_request_server_seconds_bucket[5m])
  )
)
```

### Stopping and cleaning up

```bash
# Stop containers, keep volumes
docker compose stop

# Stop and remove containers and volumes (deletes all stored data)
docker compose down -v
```

---

## Environment variable reference

| Variable | Default | Description |
|----------|---------|-------------|
| `OBSKIT_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP gRPC exporter endpoint |
| `OBSKIT_SERVICE_NAME` | (required) | Service name tag on all telemetry |
| `OBSKIT_LOG_LEVEL` | `INFO` | Minimum log level |
| `OBSKIT_TRACING_ENABLED` | `true` | Set to `false` to disable tracing entirely |

---

## Troubleshooting

### Traces not appearing in Tempo

1. Confirm the OTLP exporter endpoint is reachable:
   ```bash
   curl -I http://localhost:4317  # Should return HTTP 200 or 400 (not connection refused)
   ```
2. Check Tempo logs for errors:
   ```bash
   docker compose logs tempo --tail=50
   ```
3. Verify `setup_tracing()` is called *before* the first request.

### Logs not appearing in Loki

1. Check Promtail is scraping your container:
   ```bash
   docker compose logs promtail --tail=50
   ```
2. Ensure your application container has a `com.docker.compose.service` label.
3. Verify logs are emitted as JSON (structlog with `get_logger()`).

### Prometheus exemplars not visible

Ensure Prometheus was started with `--enable-feature=exemplar-storage` (already
included in the `docker-compose.yml` above) and that your `/metrics` endpoint returns
`Content-Type: application/openmetrics-text`.

### Grafana shows "No data"

Check that datasource URLs use the Docker Compose service names (`prometheus`,
`tempo`, `loki`) and not `localhost` — containers communicate over the `observability`
bridge network by service name, not by localhost.
