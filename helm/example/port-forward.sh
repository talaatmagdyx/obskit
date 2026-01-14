#!/bin/bash
# Port Forward Script
# ===================
# Convenience script to port-forward the service to localhost

NAMESPACE="${1:-local}"
SERVICE="${2:-order-service}"
HTTP_PORT="${3:-8080}"
METRICS_PORT="${4:-9090}"

echo "🔌 Port forwarding $SERVICE to localhost"
echo "   HTTP: http://localhost:$HTTP_PORT"
echo "   Metrics: http://localhost:$METRICS_PORT"
echo ""
echo "Press Ctrl+C to stop"
echo ""

kubectl port-forward -n $NAMESPACE svc/$SERVICE $HTTP_PORT:80 $METRICS_PORT:9090

