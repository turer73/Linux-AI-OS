#!/bin/bash
# Linux-AI Configuration Directory Initializer
# Creates /var/AI-stump/ with default config files

set -e

CONFIG_DIR="/var/AI-stump"
SERVICES_DIR="${CONFIG_DIR}/services"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[Linux-AI] Initializing configuration..."

# Create directories
if [ ! -d "$CONFIG_DIR" ]; then
    sudo mkdir -p "$CONFIG_DIR"
    sudo mkdir -p "$SERVICES_DIR"
    sudo chmod 755 "$CONFIG_DIR"
    echo "[+] Created ${CONFIG_DIR}"
else
    echo "[=] ${CONFIG_DIR} already exists"
fi

# Copy default AI-runtime.yml
if [ ! -f "${CONFIG_DIR}/AI-runtime.yml" ]; then
    sudo cp "${SCRIPT_DIR}/defaults/AI-runtime.yml" "${CONFIG_DIR}/AI-runtime.yml"
    echo "[+] Created default AI-runtime.yml"
else
    echo "[=] AI-runtime.yml already exists, skipping"
fi

# Copy default GPU-runtime.yml
if [ ! -f "${CONFIG_DIR}/GPU-runtime.yml" ]; then
    sudo cp "${SCRIPT_DIR}/defaults/GPU-runtime.yml" "${CONFIG_DIR}/GPU-runtime.yml"
    echo "[+] Created default GPU-runtime.yml"
else
    echo "[=] GPU-runtime.yml already exists, skipping"
fi

# Copy example service profile
if [ ! -f "${SERVICES_DIR}/example.svc.yml" ]; then
    sudo cp "${SCRIPT_DIR}/defaults/example.svc.yml" "${SERVICES_DIR}/example.svc.yml"
    echo "[+] Created example service profile"
fi

# Copy webops site configuration
if [ ! -f "${CONFIG_DIR}/webops-sites.yml" ]; then
    sudo cp "${SCRIPT_DIR}/defaults/webops-sites.yml" "${CONFIG_DIR}/webops-sites.yml"
    echo "[+] Created default webops-sites.yml"
else
    echo "[=] webops-sites.yml already exists, skipping"
fi

# Copy AI agent configuration
if [ ! -f "${CONFIG_DIR}/ai-agent.yml" ]; then
    sudo cp "${SCRIPT_DIR}/defaults/ai-agent.yml" "${CONFIG_DIR}/ai-agent.yml"
    echo "[+] Created default ai-agent.yml"
else
    echo "[=] ai-agent.yml already exists, skipping"
fi

# Set ownership to current user
sudo chown -R "$(whoami):$(whoami)" "$CONFIG_DIR"

echo "[Linux-AI] Configuration initialized successfully."
echo "  Config dir : ${CONFIG_DIR}"
echo "  Services   : ${SERVICES_DIR}"
