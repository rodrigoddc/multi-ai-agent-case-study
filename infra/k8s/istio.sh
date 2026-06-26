#!/usr/bin/env bash
set -euo pipefail

# Install Istio on the Kind cluster using the demo profile
# Prerequisites: istioctl must be installed.

echo "Installing Istio with demo profile..."
istioctl install --set profile=demo -y

echo "Labeling multi-agents namespace for sidecar injection..."
kubectl label namespace multi-agents istio-injection=enabled --overwrite

echo "Restarting existing pods to inject sidecars..."
kubectl rollout restart deployment -n multi-agents

echo "Waiting for rollouts to complete..."
kubectl rollout status deployment -n multi-agents --timeout=120s

echo "Verifying Istio configuration..."
istioctl analyze -n multi-agents

echo "Istio installation complete."
