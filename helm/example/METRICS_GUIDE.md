# Metrics Guide - Understanding and Using obskit Metrics

This guide shows you how to generate, view, and understand the metrics exposed by the obskit example service.

## 📊 Current Metrics Status

Your service is running and exposing metrics! The metrics endpoint shows:

1. **Python GC Metrics** - Standard Python garbage collection metrics
2. **Order Service Metrics** - RED metrics (Rate, Errors, Duration)

Currently, the order service metrics show type definitions but no values yet. This is normal - metrics are created when you make requests.

## 🚀 Generate Metrics

### Step 1: Make Some Requests

Open a terminal and run these commands to generate metrics:

```bash
# Create multiple orders to generate metrics
for i in {1..10}; do
  curl -X POST http://localhost:8080/orders \
    -H "Content-Type: application/json" \
    -d "{\"id\": \"order-$i\", \"amount\": $((i * 10))}"
  echo ""
  sleep 0.5
done

# Get some orders
for i in {1..5}; do
  curl http://localhost:8080/orders/order-$i
  echo ""
done
```

### Step 2: View Metrics Again

```bash
curl http://localhost:9090/metrics | grep order_service
```

**You should now see actual values!**

## 📈 Understanding the Metrics

### RED Metrics (Rate, Errors, Duration)

The service exposes three main metric types:

#### 1. Request Rate (`order_service_requests_total`)

**Counter** - Total number of requests

```prometheus
order_service_requests_total{operation="create_order",status="success"} 10.0
order_service_requests_total{operation="get_order",status="success"} 5.0
```

**Labels:**
- `operation` - The operation name (e.g., "create_order", "get_order")
- `status` - "success" or "failure"

#### 2. Errors (`order_service_errors_total`)

**Counter** - Total number of errors

```prometheus
order_service_errors_total{operation="create_order",error_type="HTTPException"} 2.0
```

**Labels:**
- `operation` - The operation name
- `error_type` - Type of error (e.g., "HTTPException", "ValueError")

#### 3. Duration (`order_service_request_duration_seconds`)

**Histogram** - Request duration distribution

```prometheus
order_service_request_duration_seconds_bucket{operation="create_order",le="0.005"} 2.0
order_service_request_duration_seconds_bucket{operation="create_order",le="0.01"} 5.0
order_service_request_duration_seconds_bucket{operation="create_order",le="0.025"} 8.0
order_service_request_duration_seconds_bucket{operation="create_order",le="0.05"} 10.0
order_service_request_duration_seconds_bucket{operation="create_order",le="0.1"} 10.0
order_service_request_duration_seconds_bucket{operation="create_order",le="0.25"} 10.0
order_service_request_duration_seconds_bucket{operation="create_order",le="0.5"} 10.0
order_service_request_duration_seconds_bucket{operation="create_order",le="1.0"} 10.0
order_service_request_duration_seconds_bucket{operation="create_order",le="2.5"} 10.0
order_service_request_duration_seconds_bucket{operation="create_order",le="5.0"} 10.0
order_service_request_duration_seconds_bucket{operation="create_order",le="+Inf"} 10.0
order_service_request_duration_seconds_sum{operation="create_order"} 0.234
order_service_request_duration_seconds_count{operation="create_order"} 10.0
```

**Labels:**
- `operation` - The operation name
- `le` - "less than or equal" bucket boundaries

**Useful calculations:**
- **Average duration**: `sum(rate(order_service_request_duration_seconds_sum[5m])) / sum(rate(order_service_request_duration_seconds_count[5m]))`
- **95th percentile**: `histogram_quantile(0.95, rate(order_service_request_duration_seconds_bucket[5m]))`
- **99th percentile**: `histogram_quantile(0.99, rate(order_service_request_duration_seconds_bucket[5m]))`

## 🔍 Viewing Metrics

### Method 1: Direct curl

```bash
# All metrics
curl http://localhost:9090/metrics

# Filter order service metrics
curl http://localhost:9090/metrics | grep order_service

# Filter specific metric
curl http://localhost:9090/metrics | grep order_service_requests_total

# Pretty print with jq (if installed)
curl -s http://localhost:9090/metrics | grep order_service | jq -R .
```

### Method 2: Browser

Open in your browser:
```
http://localhost:9090/metrics
```

### Method 3: Prometheus (Advanced)

If you have Prometheus installed, add this to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'order-service'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 15s
```

## 📊 Example Metrics Output

After making requests, you should see something like:

```prometheus
# HELP order_service_requests_total Total number of requests for order-service
# TYPE order_service_requests_total counter
order_service_requests_total{operation="create_order",status="success"} 10.0
order_service_requests_total{operation="get_order",status="success"} 5.0

# HELP order_service_errors_total Total number of errors for order-service
# TYPE order_service_errors_total counter
# (No errors yet - this will appear when errors occur)

# HELP order_service_request_duration_seconds Request duration distribution
# TYPE order_service_request_duration_seconds histogram
order_service_request_duration_seconds_bucket{operation="create_order",le="0.005"} 0.0
order_service_request_duration_seconds_bucket{operation="create_order",le="0.01"} 2.0
order_service_request_duration_seconds_bucket{operation="create_order",le="0.025"} 5.0
order_service_request_duration_seconds_bucket{operation="create_order",le="0.05"} 8.0
order_service_request_duration_seconds_bucket{operation="create_order",le="0.1"} 10.0
order_service_request_duration_seconds_bucket{operation="create_order",le="+Inf"} 10.0
order_service_request_duration_seconds_sum{operation="create_order"} 0.234
order_service_request_duration_seconds_count{operation="create_order"} 10.0
```

## 🧪 Test Scenarios

### Generate Success Metrics

```bash
# Create 20 successful orders
for i in {1..20}; do
  curl -X POST http://localhost:8080/orders \
    -H "Content-Type: application/json" \
    -d "{\"id\": \"success-$i\", \"amount\": 100}"
done
```

### Generate Error Metrics

```bash
# Try to get non-existent order (will succeed, but you can test with invalid data)
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d "{}"  # Missing required fields might cause errors
```

### View Metrics After Requests

```bash
# View all order service metrics
curl -s http://localhost:9090/metrics | grep -A 20 order_service

# Count total requests
curl -s http://localhost:9090/metrics | grep order_service_requests_total | grep -v "#"

# View duration buckets
curl -s http://localhost:9090/metrics | grep order_service_request_duration_seconds_bucket
```

## 📈 Prometheus Queries (If Using Prometheus)

Once you have metrics, you can use these PromQL queries:

### Request Rate (requests per second)

```promql
rate(order_service_requests_total[5m])
```

### Error Rate

```promql
rate(order_service_errors_total[5m])
```

### Average Response Time

```promql
rate(order_service_request_duration_seconds_sum[5m]) / 
rate(order_service_request_duration_seconds_count[5m])
```

### 95th Percentile Response Time

```promql
histogram_quantile(0.95, 
  rate(order_service_request_duration_seconds_bucket[5m])
)
```

### Error Rate Percentage

```promql
rate(order_service_errors_total[5m]) / 
rate(order_service_requests_total[5m]) * 100
```

## 🎯 Quick Test Script

Save this as `generate-metrics.sh`:

```bash
#!/bin/bash
echo "📊 Generating metrics..."

# Create orders
for i in {1..10}; do
  echo "Creating order $i..."
  curl -s -X POST http://localhost:8080/orders \
    -H "Content-Type: application/json" \
    -d "{\"id\": \"test-$i\", \"amount\": $((i * 10))}" > /dev/null
done

# Get orders
for i in {1..5}; do
  echo "Getting order test-$i..."
  curl -s http://localhost:8080/orders/order-test-$i > /dev/null
done

echo ""
echo "✅ Metrics generated!"
echo ""
echo "View metrics:"
echo "  curl http://localhost:9090/metrics | grep order_service"
```

Make it executable and run:

```bash
chmod +x generate-metrics.sh
./generate-metrics.sh
```

## 🔍 Troubleshooting

### No Metrics Showing

**Problem:** Metrics show type definitions but no values

**Solution:** Make some requests to the service:
```bash
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"id": "test", "amount": 100}'
```

### Metrics Endpoint Not Accessible

**Problem:** `curl http://localhost:9090/metrics` fails

**Solution:**
1. Check if service is running: `curl http://localhost:8080/health`
2. Check if metrics server started (look for "metrics_server_started" in logs)
3. Verify port: `lsof -i :9090`

### Duplicate Metric Definitions

**Problem:** You see duplicate HELP/TYPE lines

**Solution:** This is normal if multiple REDMetrics instances exist. Each instance registers its own metrics. This usually happens if:
- Multiple services are running
- Metrics are being registered multiple times

To fix, ensure only one REDMetrics instance per service name.

## ✅ Success Checklist

- [ ] Metrics endpoint is accessible (`curl http://localhost:9090/metrics`)
- [ ] Made some requests to generate metrics
- [ ] Can see `order_service_requests_total` with values
- [ ] Can see `order_service_request_duration_seconds` buckets
- [ ] Metrics update after making new requests

## 📚 Next Steps

- **Grafana Dashboards** - Create dashboards using these metrics
- **Alerting** - Set up alerts based on error rates and latency
- **Production** - Deploy with Prometheus scraping these metrics

See [COMPLETE_LOCAL_GUIDE.md](./COMPLETE_LOCAL_GUIDE.md) for more details!

