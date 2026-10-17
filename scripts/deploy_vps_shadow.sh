#!/bin/bash
# ==========================================================
# PHASE 7 SHADOW VPS DEPLOYMENT SCRIPT
# ==========================================================

VPS_USER="ophelia"
VPS_IP="$1"
VPS_DIR="/opt/ophelia"

if [ -z "$VPS_IP" ]; then
    echo "Usage: ./deploy_vps_shadow.sh <VPS_IP>"
    exit 1
fi

echo "=========================================================="
echo "CALCULATING LOCAL ARTIFACT HASHES (SHA-256)"
echo "=========================================================="
sha256sum PHASE7_MODEL_FROZEN_*.pkl
sha256sum PHASE7_DECISION_THRESHOLDS.json

echo "=========================================================="
echo "DEPLOYING TO VPS: $VPS_USER@$VPS_IP:$VPS_DIR"
echo "=========================================================="
# We only deploy minimal required files
rsync -avz --progress \
    --exclude '.git' \
    --exclude '.env' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.ipynb' \
    --exclude 'test.zip' \
    --exclude 'data/' \
    --exclude 'research/' \
    --exclude 'logs/*.log' \
    --exclude 'PHASE5_*' \
    --exclude 'PHASE6_*' \
    ./ ${VPS_USER}@${VPS_IP}:${VPS_DIR}/

echo "=========================================================="
echo "DEPLOYMENT COMPLETE"
echo "Next Steps on VPS:"
echo "1. Run: sha256sum PHASE7_MODEL_FROZEN_*.pkl PHASE7_DECISION_THRESHOLDS.json"
echo "2. Ensure OPHELIA_MODE=SHADOW is exported in the environment."
echo "3. Copy systemd services: "
echo "   sudo cp deploy/ophelia-shadow.service /etc/systemd/system/"
echo "   sudo cp deploy/ophelia-telegram-monitor.service /etc/systemd/system/"
echo "4. Reload daemon and start: "
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl start ophelia-shadow"
echo "   sudo systemctl start ophelia-telegram-monitor"
echo "=========================================================="
