# Grafana Dashboards for obskit Helm Chart

Complete guide to setting up and using Grafana dashboards with your obskit-enabled services.

## 📊 Available Dashboards

### 1. RED Method Dashboard
- **Request Rate** - Requests per second by operation
- **Error Rate** - Errors per second by operation and error type
- **Request Duration** - p50, p95, p99 percentiles
- **Total Requests/Errors** - Summary statistics
- **Error Rate Percentage** - Error rate as percentage
- **Average Response Time** - Mean response time
- **Requests by Operation** - Bar chart breakdown
- **Error Rate by Operation** - Error breakdown

### 2. Golden Signals Dashboard (Coming Soon)
- Latency
- Traffic
- Errors
- Saturation

## 🚀 Quick Setup

### Option 1: Using Grafana Operator (Recommended)

If you have Grafana Operator installed:

```bash
helm install my-service ../obskit \
  --set obskit.serviceName=order-service \
  --set grafana.dashboard.enabled=true \
  --set grafana.dashboard.operator=true \
  --set image.repository=my-registry/order-service \
  --set image.tag=v1.0.0
```

The dashboard will be automatically created and available in Grafana.

### Option 2: Manual Import

1. **Export the dashboard JSON:**

```bash
# Get the dashboard from the Helm chart
helm template my-service ../obskit \
  --set grafana.dashboard.enabled=true \
  --show-only templates/grafana-dashboard.yaml \
  > dashboard.json
```

2. **Import into Grafana:**

   - Open Grafana UI
   - Go to **Dashboards** → **Import**
   - Paste the JSON or upload the file
   - Select your Prometheus data source
   - Click **Import**

### Option 3: ConfigMap (For Grafana with ConfigMap Provisioning)

```bash
helm install my-service ../obskit \
  --set grafana.dashboard.enabled=true \
  --set grafana.dashboard.namespace=monitoring \
  --set image.repository=my-registry/order-service \
  --set image.tag=v1.0.0
```

The dashboard will be created as a ConfigMap in the specified namespace.

## 📋 Step-by-Step: Manual Dashboard Creation

### Step 1: Access Grafana

```bash
# Port forward Grafana (if not exposed)
kubectl port-forward -n monitoring svc/grafana 3000:3000

# Open in browser
open http://localhost:3000
```

### Step 2: Create Dashboard

1. Click **+** → **Create Dashboard**
2. Click **Add visualization**
3. Select **Prometheus** as data source

### Step 3: Add Panels

#### Panel 1: Request Rate

**Query:**
```promql
sum(rate(order_service_requests_total[5m])) by (operation, status)
```

**Legend:** `{{operation}} - {{status}}`

**Y-axis:** Requests/sec

#### Panel 2: Error Rate

**Query:**
```promql
sum(rate(order_service_errors_total[5m])) by (operation, error_type)
```

**Legend:** `{{operation}} - {{error_type}}`

**Y-axis:** Errors/sec

#### Panel 3: Request Duration (p95, p99)

**Query 1:**
```promql
histogram_quantile(0.95, sum(rate(order_service_request_duration_seconds_bucket[5m])) by (operation, le))
```

**Legend:** `{{operation}} - p95`

**Query 2:**
```promql
histogram_quantile(0.99, sum(rate(order_service_request_duration_seconds_bucket[5m])) by (operation, le))
```

**Legend:** `{{operation}} - p99`

**Y-axis:** Duration (seconds)

#### Panel 4: Total Requests (Stat)

**Query:**
```promql
sum(increase(order_service_requests_total[1h]))
```

**Visualization:** Stat

#### Panel 5: Error Rate Percentage (Stat)

**Query:**
```promql
(sum(rate(order_service_errors_total[5m])) / sum(rate(order_service_requests_total[5m]))) * 100
```

**Visualization:** Stat
**Unit:** Percent (0.0-100.0)
**Thresholds:**
- Green: 0-1%
- Yellow: 1-5%
- Red: >5%

#### Panel 6: Average Response Time (Stat)

**Query:**
```promql
sum(rate(order_service_request_duration_seconds_sum[5m])) / sum(rate(order_service_request_duration_seconds_count[5m]))
```

**Visualization:** Stat
**Unit:** Seconds
**Thresholds:**
- Green: <0.5s
- Yellow: 0.5-1.0s
- Red: >1.0s

## 📊 Complete Dashboard JSON

For a ready-to-use dashboard, see:
- `../obskit/dashboards/obskit-red-dashboard.json`

Import this JSON directly into Grafana.

## 🔧 Customization

### Change Service Name

If your service name is different, replace `order_service` in all queries:

```promql
# Replace this:
order_service_requests_total

# With your service name:
my_service_requests_total
```

### Add More Panels

#### Requests by Status

```promql
sum(rate(order_service_requests_total[5m])) by (status)
```

#### Top Error Types

```promql
topk(10, sum(rate(order_service_errors_total[5m])) by (error_type))
```

#### Request Duration Heatmap

```promql
sum(rate(order_service_request_duration_seconds_bucket[5m])) by (operation, le)
```

**Visualization:** Heatmap

## 🎯 Useful Prometheus Queries

### Request Rate (RPS)
```promql
sum(rate(order_service_requests_total[5m])) by (operation)
```

### Error Rate
```promql
sum(rate(order_service_errors_total[5m])) by (operation)
```

### 95th Percentile Latency
```promql
histogram_quantile(0.95, sum(rate(order_service_request_duration_seconds_bucket[5m])) by (operation, le))
```

### 99th Percentile Latency
```promql
histogram_quantile(0.99, sum(rate(order_service_request_duration_seconds_bucket[5m])) by (operation, le))
```

### Average Latency
```promql
sum(rate(order_service_request_duration_seconds_sum[5m])) / sum(rate(order_service_request_duration_seconds_count[5m]))
```

### Error Rate Percentage
```promql
(sum(rate(order_service_errors_total[5m])) / sum(rate(order_service_requests_total[5m]))) * 100
```

### Success Rate
```promql
(sum(rate(order_service_requests_total{status="success"}[5m])) / sum(rate(order_service_requests_total[5m]))) * 100
```

## 📈 Dashboard Variables

Add variables for dynamic filtering:

### Service Name Variable

1. Go to **Dashboard Settings** → **Variables**
2. Click **Add variable**
3. Configure:
   - **Name:** `service_name`
   - **Type:** Query
   - **Data source:** Prometheus
   - **Query:** `label_values(order_service_requests_total, __name__)`
   - **Multi-value:** Enabled
   - **Include All:** Enabled

### Operation Variable

1. Add another variable:
   - **Name:** `operation`
   - **Type:** Query
   - **Query:** `label_values(order_service_requests_total, operation)`
   - **Multi-value:** Enabled

Then use in queries:
```promql
sum(rate(${service_name}_requests_total{operation=~"$operation"}[5m]))
```

## 🚨 Alerting Rules

Create alerts based on dashboard metrics:

### High Error Rate

```yaml
- alert: HighErrorRate
  expr: |
    (sum(rate(order_service_errors_total[5m])) / 
     sum(rate(order_service_requests_total[5m]))) * 100 > 5
  for: 5m
  annotations:
    summary: "High error rate detected"
    description: "Error rate is {{ $value }}%"
```

### High Latency

```yaml
- alert: HighLatency
  expr: |
    histogram_quantile(0.95, 
      sum(rate(order_service_request_duration_seconds_bucket[5m])) by (le)
    ) > 1.0
  for: 5m
  annotations:
    summary: "High latency detected"
    description: "p95 latency is {{ $value }}s"
```

## 🔍 Troubleshooting

### Dashboard Shows "No Data"

**Problem:** Dashboard panels show "No data"

**Solutions:**
1. Verify Prometheus is scraping metrics:
   ```bash
   kubectl get servicemonitor -n <namespace>
   ```

2. Check if metrics exist in Prometheus:
   ```bash
   # Port forward Prometheus
   kubectl port-forward -n monitoring svc/prometheus 9090:9090
   
   # Query metrics
   curl 'http://localhost:9090/api/v1/query?query=order_service_requests_total'
   ```

3. Verify service name in queries matches your service:
   - Check `obskit.serviceName` in Helm values
   - Update queries to match

### Wrong Service Name

**Problem:** Queries use wrong service name

**Solution:** Replace `order_service` with your actual service name:
- In dashboard JSON: Find and replace `order_service` → `your_service`
- In manual queries: Update all queries

### Metrics Not Appearing

**Problem:** Metrics don't show up in Grafana

**Solutions:**
1. Check Prometheus data source is configured correctly
2. Verify time range (metrics might be old)
3. Check if ServiceMonitor is working:
   ```bash
   kubectl describe servicemonitor <service-name>
   ```

## 📚 Additional Resources

- **Prometheus Queries:** See [METRICS_GUIDE.md](./METRICS_GUIDE.md)
- **Alerting Rules:** See `../../alerts/prometheus_rules.yml`
- **Grafana Documentation:** https://grafana.com/docs/

## ✅ Quick Checklist

- [ ] Grafana is installed and accessible
- [ ] Prometheus data source is configured
- [ ] ServiceMonitor is created and working
- [ ] Metrics are being scraped (check Prometheus targets)
- [ ] Dashboard is imported or created
- [ ] Service name in queries matches actual service
- [ ] Dashboard shows data

## 🎉 You're Done!

Your Grafana dashboard is now set up and showing obskit metrics!

**Next Steps:**
- Create custom panels for your specific needs
- Set up alerting based on dashboard metrics
- Create additional dashboards for different views

