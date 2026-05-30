#!/usr/bin/env bash
# ==============================================================================
# Oisha-OS Oracle Cloud Linux Deployment Script
# ==============================================================================
# This script automates production deployment on Linux VPS (Ubuntu/Debian/etc.).
# It dynamically configures virtual environment, updates absolute paths in 
# systemd service definitions, copies them, and starts them automatically.
#
# Run this on your Oracle Cloud server:
#     sudo bash scripts/deploy_oracle.sh
# ==============================================================================

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Error: Please run this script with sudo (as root): sudo bash $0"
  exit 1
fi

# Get the absolute path of the project directory (parent of scripts/)
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
echo "🚀 Starting Oisha-OS 24/7 Deployment on Oracle Cloud..."
echo "📂 Project absolute path resolved to: $PROJECT_DIR"

# 1. Update OS package lists and install basic tools
echo "📦 Updating OS packages and installing dependencies..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git build-essential screen curl

# 2. Setup virtual environment (.venv)
echo "🐍 Initializing Python Virtual Environment (.venv)..."
cd "$PROJECT_DIR"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "✅ Virtual environment created."
else
  echo "ℹ️ Existing virtual environment (.venv) found. Reusing it."
fi

# 3. Install requirements
echo "📥 Installing required python packages..."
.venv/bin/pip install --upgrade pip
if [ -f "requirements.txt" ]; then
  .venv/bin/pip install -r requirements.txt
  echo "✅ Dependencies installed."
else
  echo "⚠️ Warning: requirements.txt not found!"
fi

# 4. Configure systemd service files dynamically with project paths
echo "⚙️ Dynamically configuring Linux systemd services..."
OISHA_SERVICE_SRC="ops/oisha.service"
WATCHDOG_SERVICE_SRC="ops/watchdog.service"

OISHA_SERVICE_DEST="/etc/systemd/system/oisha.service"
WATCHDOG_SERVICE_DEST="/etc/systemd/system/watchdog.service"

if [ ! -f "$OISHA_SERVICE_SRC" ] || [ ! -f "$WATCHDOG_SERVICE_SRC" ]; then
  echo "❌ Error: Systemd service templates not found in ops/!"
  exit 1
fi

# Escape project path for sed replacement
ESCAPED_DIR=$(echo "$PROJECT_DIR" | sed 's/\//\\\//g')

# Copy and replace paths in oisha.service
echo "⚙️ Registering oisha.service..."
cat "$OISHA_SERVICE_SRC" | \
  sed "s/\/root\/oisha-os/$ESCAPED_DIR/g" > "$OISHA_SERVICE_DEST"

# Copy and replace paths in watchdog.service
echo "⚙️ Registering watchdog.service..."
cat "$WATCHDOG_SERVICE_SRC" | \
  sed "s/\/root\/oisha-os/$ESCAPED_DIR/g" > "$WATCHDOG_SERVICE_DEST"

# 5. Reload systemd and start the background services
echo "⚡ Reloading systemd manager configuration..."
systemctl daemon-reload

echo "⚡ Enabling Oisha-OS services to start on server boot..."
systemctl enable oisha
systemctl enable watchdog

echo "⚡ Starting/Restarting background daemons..."
systemctl restart oisha
systemctl restart watchdog

echo ""
echo "=========================================================================="
echo " 🎉 OISHA-OS IS NOW FULLY AUTONOMOUS AND RUNNING 24/7 ON ORACLE CLOUD! 🎉"
echo "=========================================================================="
echo "  To check live Main Service status:   sudo systemctl status oisha"
echo "  To check live Self-Healing status:  sudo systemctl status watchdog"
echo "  To read latest Main Service logs:    sudo journalctl -u oisha -n 50 -f"
echo "  To read latest Watchdog logs:       sudo journalctl -u watchdog -n 50 -f"
echo "=========================================================================="
echo ""
