#!/usr/bin/env python3
"""
Simple Dashboard Server for obskit Metrics
==========================================
A simple web server that displays obskit metrics in a dashboard.
No Docker, no Kubernetes needed - just Python!
"""

import http.server
import socketserver
import urllib.request
import json
import re
from datetime import datetime
from typing import Dict

METRICS_URL = "http://localhost:9090/metrics"
SERVICE_NAME = "order_service"
PORT = 8081


def parse_metrics(metrics_text: str) -> Dict:
    """Parse Prometheus metrics text format."""
    metrics = {}
    lines = metrics_text.split('\n')
    
    for line in lines:
        if line.startswith('#') or not line.strip():
            continue
        
        # Match: metric_name{labels} value
        match = re.match(r'^(\w+)(?:\{([^}]+)\})?\s+([\d.]+)', line)
        if match:
            name, labels, value = match.groups()
            key = f"{name}{{{labels}}}" if labels else name
            metrics[key] = float(value)
    
    return metrics


def calculate_stats(metrics: Dict) -> Dict:
    """Calculate statistics from metrics."""
    total_requests = 0
    total_errors = 0
    total_duration_sum = 0
    total_duration_count = 0
    operations = {}
    
    for key, value in metrics.items():
        if f"{SERVICE_NAME}_requests_total" in key:
            total_requests += value
            # Extract operation from labels
            op_match = re.search(r'operation="([^"]+)"', key)
            if op_match:
                op = op_match.group(1)
                operations[op] = operations.get(op, 0) + value
        
        if f"{SERVICE_NAME}_errors_total" in key:
            total_errors += value
        
        if "_sum" in key and "duration" in key:
            total_duration_sum += value
        
        if "_count" in key and "duration" in key:
            total_duration_count += value
    
    error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
    avg_duration = (total_duration_sum / total_duration_count * 1000) if total_duration_count > 0 else 0
    
    return {
        "total_requests": total_requests,
        "total_errors": total_errors,
        "error_rate": round(error_rate, 2),
        "avg_duration_ms": round(avg_duration, 2),
        "operations": operations,
        "timestamp": datetime.now().isoformat()
    }


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler for dashboard."""
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/api/metrics':
            self.send_json_metrics()
        elif self.path == '/' or self.path == '/index.html':
            self.send_dashboard()
        else:
            self.send_error(404)
    
    def send_json_metrics(self):
        """Send metrics as JSON."""
        try:
            with urllib.request.urlopen(METRICS_URL, timeout=5) as response:
                metrics_text = response.read().decode('utf-8')
                metrics = parse_metrics(metrics_text)
                stats = calculate_stats(metrics)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(stats).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def send_dashboard(self):
        """Send dashboard HTML."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>obskit Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #1e1e1e;
            color: #d4d4d4;
        }}
        .header {{
            background: #2d2d2d;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        h1 {{
            color: #4ec9b0;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: #2d2d2d;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #4ec9b0;
        }}
        .stat-label {{
            font-size: 12px;
            color: #858585;
            margin-bottom: 5px;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #4ec9b0;
        }}
        .operations {{
            background: #2d2d2d;
            padding: 20px;
            border-radius: 8px;
        }}
        .operation-item {{
            padding: 10px;
            margin: 5px 0;
            background: #3d3d3d;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>obskit - RED Metrics Dashboard</h1>
        <p>Auto-refreshing every 5 seconds | Metrics from: {METRICS_URL}</p>
    </div>
    <div id="content"></div>
    <script>
        async function loadMetrics() {{
            try {{
                const response = await fetch('/api/metrics');
                const data = await response.json();
                
                const statsHtml = `
                    <div class="stats">
                        <div class="stat-card">
                            <div class="stat-label">Total Requests</div>
                            <div class="stat-value">${{data.total_requests.toLocaleString()}}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Total Errors</div>
                            <div class="stat-value">${{data.total_errors.toLocaleString()}}</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Error Rate</div>
                            <div class="stat-value">${{data.error_rate}}%</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">Avg Duration</div>
                            <div class="stat-value">${{data.avg_duration_ms}}ms</div>
                        </div>
                    </div>
                `;
                
                const operationsHtml = `
                    <div class="operations">
                        <h2>Requests by Operation</h2>
                        ${{Object.entries(data.operations).map(([op, count]) => `
                            <div class="operation-item">
                                <strong>${{op}}:</strong> ${{count.toLocaleString()}} requests
                            </div>
                        `).join('')}}
                    </div>
                `;
                
                document.getElementById('content').innerHTML = statsHtml + operationsHtml;
            }} catch (error) {{
                document.getElementById('content').innerHTML = 
                    '<p style="color: red;">Error loading metrics: ' + error.message + '</p>';
            }}
        }}
        
        loadMetrics();
        setInterval(loadMetrics, 5000);
    </script>
</body>
</html>
"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())


def main():
    """Start the dashboard server."""
    print(f"🚀 Starting obskit Dashboard Server")
    print(f"📊 Metrics URL: {METRICS_URL}")
    print(f"🌐 Dashboard: http://localhost:{PORT}")
    print(f"📡 API: http://localhost:{PORT}/api/metrics")
    print(f"\nPress Ctrl+C to stop\n")
    
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n✅ Server stopped")


if __name__ == "__main__":
    main()

