# Grafana Dashboards for obskit

This directory contains Grafana dashboard JSON files for visualizing obskit metrics.

## 📊 Available Dashboards

### RED Method Dashboard
- **File:** `obskit-red-dashboard.json`
- **Description:** Complete RED (Rate, Errors, Duration) metrics dashboard
- **Panels:**
  - Request Rate (RPS)
  - Error Rate
  - Request Duration (p50, p95, p99)
  - Total Requests/Errors
  - Error Rate Percentage
  - Average Response Time
  - Requests by Operation
  - Error Rate by Operation

## 🚀 Usage

### Import into Grafana

1. Open Grafana UI
2. Go to **Dashboards** → **Import**
3. Upload the JSON file or paste the content
4. Select your Prometheus data source
5. Click **Import**

### Customize Service Name

Before importing, replace `{{service_name}}` with your actual service name:

```bash
# Example: Replace order_service with your_service
sed 's/order_service/your_service/g' obskit-red-dashboard.json > custom-dashboard.json
```

Or use Grafana variables (recommended):
- Add a variable `service_name` in dashboard settings
- Use `${service_name}` in queries

## 📝 Dashboard Structure

Each dashboard JSON contains:
- **Panels:** Visualization panels with Prometheus queries
- **Variables:** Template variables for filtering
- **Refresh:** Auto-refresh interval
- **Time Range:** Default time range

## 🔧 Customization

### Add More Panels

Edit the JSON and add new panel objects to the `panels` array.

### Change Queries

Update the `expr` field in each panel's `targets` array.

### Modify Layout

Adjust `gridPos` values:
- `x`: Horizontal position
- `y`: Vertical position
- `w`: Width (1-24)
- `h`: Height

## 📚 See Also

- [GRAFANA_DASHBOARDS.md](../../example/GRAFANA_DASHBOARDS.md) - Complete setup guide
- [METRICS_GUIDE.md](../../example/METRICS_GUIDE.md) - Understanding metrics

