#!/bin/bash
# Test Local Service
# ==================
# Simple test script for the locally running service

set -e

BASE_URL="${1:-http://localhost:8080}"
METRICS_URL="${2:-http://localhost:9090}"

echo "🧪 Testing service at $BASE_URL"
echo ""

# Test health endpoints
echo "1️⃣  Testing health endpoints..."

HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/health" 2>&1)
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -1)
BODY=$(echo "$HEALTH_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ Health check:"
  echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
  echo "❌ Health check failed (HTTP $HTTP_CODE)"
  echo "   Response: $BODY"
  echo "   Is the service running? Try: ./run-local.sh"
fi
echo ""

READY_RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/ready" 2>&1)
HTTP_CODE=$(echo "$READY_RESPONSE" | tail -1)
BODY=$(echo "$READY_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ Readiness check:"
  echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
  echo "❌ Readiness check failed (HTTP $HTTP_CODE)"
  echo "   Response: $BODY"
fi
echo ""

LIVE_RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/live" 2>&1)
HTTP_CODE=$(echo "$LIVE_RESPONSE" | tail -1)
BODY=$(echo "$LIVE_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ Liveness check:"
  echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
  echo "❌ Liveness check failed (HTTP $HTTP_CODE)"
  echo "   Response: $BODY"
fi
echo ""

# Test metrics
echo "2️⃣  Testing metrics endpoint..."
METRICS_RESPONSE=$(curl -s -w "\n%{http_code}" "$METRICS_URL/metrics" 2>&1)
HTTP_CODE=$(echo "$METRICS_RESPONSE" | tail -1)
BODY=$(echo "$METRICS_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ Metrics endpoint (showing first 20 lines):"
  echo "$BODY" | head -20
else
  echo "❌ Metrics endpoint failed (HTTP $HTTP_CODE)"
  echo "   Response: $BODY"
  echo "   Is the metrics server running?"
fi
echo ""

# Test business logic
echo "3️⃣  Testing business logic..."
ORDER_RESPONSE=$(curl -s -X POST "$BASE_URL/orders" \
  -H "Content-Type: application/json" \
  -d '{"id": "test-123", "amount": 99.99}')

if [ $? -eq 0 ]; then
  echo "✅ Order created:"
  echo "$ORDER_RESPONSE" | python3 -m json.tool
else
  echo "❌ Order creation failed"
fi
echo ""

# Get order
ORDER_ID=$(echo "$ORDER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('order_id', 'order-test-123'))" 2>/dev/null || echo "order-test-123")
echo "4️⃣  Getting order: $ORDER_ID"
curl -s "$BASE_URL/orders/$ORDER_ID" | python3 -m json.tool || echo "❌ Get order failed"
echo ""

echo "✅ All tests complete!"

