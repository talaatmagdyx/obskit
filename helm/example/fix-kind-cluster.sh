#!/bin/bash
# Fix Kind Cluster Script
# =======================
# This script fixes a broken kind cluster by deleting and recreating it

set -e

CLUSTER_NAME="${1:-obskit-test}"

echo "🔧 Fixing Kind cluster: $CLUSTER_NAME"
echo ""

# Check if cluster exists
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  echo "ℹ️  Cluster $CLUSTER_NAME does not exist"
  echo "   Creating new cluster..."
  kind create cluster --name $CLUSTER_NAME
  echo "✅ Cluster created"
  exit 0
fi

echo "📋 Current cluster status:"
kind get clusters 2>/dev/null | grep "^${CLUSTER_NAME}$" || echo "   Not found in kind list"

# Try to access cluster
echo ""
echo "🔍 Checking cluster accessibility..."
kubectl config use-context kind-$CLUSTER_NAME > /dev/null 2>&1 || true

if kubectl cluster-info > /dev/null 2>&1; then
  echo "✅ Cluster is accessible - no fix needed"
  exit 0
fi

echo "❌ Cluster is not accessible"
echo ""
echo "🗑️  Deleting broken cluster..."
kind delete cluster --name $CLUSTER_NAME

echo ""
echo "🆕 Creating new cluster..."
kind create cluster --name $CLUSTER_NAME

echo ""
echo "⏳ Waiting for cluster to be ready..."
sleep 5

# Verify
kubectl config use-context kind-$CLUSTER_NAME
if kubectl cluster-info > /dev/null 2>&1; then
  echo "✅ Cluster is now accessible"
  kubectl get nodes
else
  echo "❌ Cluster still not accessible"
  echo "   Try manually:"
  echo "   docker ps | grep $CLUSTER_NAME"
  echo "   kind delete cluster --name $CLUSTER_NAME"
  echo "   kind create cluster --name $CLUSTER_NAME"
  exit 1
fi

