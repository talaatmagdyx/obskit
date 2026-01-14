# Run Grafana Dashboard Locally (No Docker, No Kubernetes)

Simple guide to view obskit dashboards locally without Docker or Kubernetes.

## 🚀 Option 1: Simple Web Dashboard (Easiest)

A simple HTML dashboard that reads metrics directly from your local service.

### Step 1: Start Your Service

```bash
cd helm/example
./run-local.sh
```

### Step 2: Open the Dashboard

```bash
# Open the simple dashboard in your browser
open dashboard-simple.html

# OR manually open:
# file:///path/to/obskit/helm/example/dashboard-simple.html
```

The dashboard will automatically fetch metrics from `http://localhost:9090/metrics`.

## 🚀 Option 2: Local Grafana (More Features)

### Step 1: Install Grafana Locally

**macOS:**
```bash
brew install grafana
brew services start grafana
```

**Linux:**
```bash
# Download from https://grafana.com/grafana/download
# Or use package manager
sudo apt install grafana  # Debian/Ubuntu
sudo yum install grafana  # RHEL/CentOS
```

**Windows:**
- Download from https://grafana.com/grafana/download
- Install and start Grafana service

### Step 2: Access Grafana

```bash
# Grafana runs on port 3000
open http://localhost:3000

# Default credentials:
# Username: admin
# Password: admin (change on first login)
```

### Step 3: Configure Prometheus Data Source

1. Go to **Configuration** → **Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Set URL: `http://localhost:9090`
5. Click **Save & Test**

### Step 4: Import Dashboard

1. Go to **Dashboards** → **Import**
2. Click **Upload JSON file**
3. Select: `../obskit/dashboards/obskit-red-dashboard.json`
4. Select Prometheus data source
5. Click **Import**

### Step 5: View Dashboard

The dashboard will show metrics from your local service!

## 🚀 Option 3: Python Dashboard (No Installation)

A simple Python script that creates a web dashboard.

### Step 1: Run the Dashboard Server

```bash
cd helm/example
python3 dashboard-server.py
```

### Step 2: Open in Browser

```
http://localhost:8081
```

## 📊 What You'll See

All dashboards show:
- **Request Rate** - Requests per second
- **Error Rate** - Errors per second  
- **Request Duration** - p50, p95, p99 latencies
- **Total Requests/Errors** - Summary stats
- **Error Rate %** - Error percentage
- **Average Response Time** - Mean latency

## 🔧 Troubleshooting

### Metrics Not Showing

1. Make sure your service is running:
   ```bash
   curl http://localhost:9090/metrics
   ```

2. Generate some metrics:
   ```bash
   for i in {1..10}; do
     curl -X POST http://localhost:8080/orders \
       -H "Content-Type: application/json" \
       -d "{\"id\": \"$i\", \"amount\": 100}"
   done
   ```

### Grafana Can't Connect

1. Check if metrics endpoint is accessible:
   ```bash
   curl http://localhost:9090/metrics | head -20
   ```

2. Verify Grafana data source URL is correct: `http://localhost:9090`

3. Check firewall/port access

### Dashboard Shows "No Data"

1. Make some requests to generate metrics
2. Check time range in Grafana (should include current time)
3. Verify service name in queries matches your service

## ✅ Quick Start Summary

**Simplest (Option 1):**
```bash
./run-local.sh  # Terminal 1
open dashboard-simple.html  # Browser
```

**Full Featured (Option 2):**
```bash
brew install grafana  # Install
brew services start grafana  # Start
open http://localhost:3000  # Access
# Then import dashboard JSON
```

See the dashboard files in this directory for ready-to-use dashboards!

