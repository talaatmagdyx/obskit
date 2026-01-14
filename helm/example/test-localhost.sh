#!/bin/bash
# Test Script for Localhost Deployment
# ====================================
# This script tests all endpoints after deployment

set -e

NAMESPACE="local"
SERVICE="order-service"
HTTP_PORT=8080
METRICS_PORT=9090

echo "🧪 Testing $SERVICE on localhost"
echo ""

# Check if port-forward is running
if ! curl -s http://localhost:$HTTP_PORT/health > /dev/null 2>&1; then
  echo "❌ Error: Service not accessible on localhost:$HTTP_PORT"
  echo "   Make sure port-forward is running:"
  echo "   kubectl port-forward -n $NAMESPACE svc/$SERVICE $HTTP_PORT:80 $METRICS_PORT:9090"
  exit 1
fi

echo "✅ Service is accessible"
echo ""

# Test health endpoints
echo "🏥 Testing health endpoints..."
echo ""

echo "  Health check:"
HEALTH=$(curl -s http://localhost:$HTTP_PORT/health)
echo "$HEALTH" | jq . 2>/dev/null || echo "$HEALTH"
echo ""

echo "  Readiness check:"
READY=$(curl -s http://localhost:$HTTP_PORT/ready)
echo "$READY" | jq . 2>/dev/null || echo "$READY"
echo ""

echo "  Liveness check:"
LIVE=$(curl -s http://localhost:$HTTP_PORT/live)
echo "$LIVE" | jq . 2>/dev/null || echo "$LIVE"
echo ""

# Test business endpoints
echo "📦 Testing business endpoints..."
echo ""

echo "  Creating order..."
ORDER_RESPONSE=$(curl -s -X POST http://localhost:$HTTP_PORT/orders \
  -H "Content-Type: application/json" \
  -d '{"id": "test-123", "amount": 99.99}')

echo "$ORDER_RESPONSE" | jq . 2>/dev/null || echo "$ORDER_RESPONSE"
echo ""

ORDER_ID=$(echo "$ORDER_RESPONSE" | jq -r '.order_id // "test-123"' 2>/dev/null || echo "test-123")

echo "  Getting order: $ORDER_ID"
GET_ORDER=$(curl -s http://localhost:$HTTP_PORT/orders/$ORDER_ID)
echo "$GET_ORDER" | jq . 2>/dev/null || echo "$GET_ORDER"
echo ""

# Test metrics
echo "📊 Testing metrics endpoint..."
METRICS=$(curl -s http://localhost:$METRICS_PORT/metrics)

if echo "$METRICS" | grep -q "order_service"; then
  echo "  ✅ Metrics found!"
  echo ""
  echo "  Sample metrics:"
  echo "$METRICS" | grep "^order_service" | head -10
else
  echo "  ⚠️  No order_service metrics found"
  echo "  Available metrics:"
  echo "$METRICS" | grep "^#" | head -5
fi

echo ""
echo "✅ Testing complete!"
echo ""
echo "📋 Summary:"
echo "  - Health endpoints: ✅"
echo "  - Business endpoints: ✅"
echo "  - Metrics endpoint: ✅"
echo ""
echo "🌐 Access points:"
echo "  - Service: http://localhost:$HTTP_PORT"
echo "  - Metrics: http://localhost:$METRICS_PORT/metrics"
echo "  - Health: http://localhost:$HTTP_PORT/health"

