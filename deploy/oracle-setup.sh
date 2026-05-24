#!/bin/bash
# Oracle Cloud Free Tier — Oisha-OS Setup Script
# Run this ONCE on a fresh Oracle ARM instance (Ubuntu 22.04+)
# Usage: ssh ubuntu@<IP> 'bash -s' < deploy/oracle-setup.sh

set -euo pipefail

echo "=== Oisha-OS: Oracle Cloud Free Setup ==="

# 1. System packages
sudo apt-get update -qq
sudo apt-get install -y -qq python3.12 python3.12-venv python3-pip git

# 2. Firewall — open port 8080 for health checks
sudo iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || true

# 3. Clone repo
OISHA_DIR="/home/ubuntu/oisha-os"
if [ ! -d "$OISHA_DIR" ]; then
    git clone https://github.com/baxtiyorjongaziyev/oisha-os.git "$OISHA_DIR"
fi
cd "$OISHA_DIR"

# 4. Python venv
python3.12 -m venv venv
./venv/bin/pip install -q -r requirements.txt

# 5. Create systemd service
sudo tee /etc/systemd/system/oisha-os.service > /dev/null <<'SERVICE'
[Unit]
Description=Oisha-OS Enterprise AI Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/oisha-os
ExecStart=/home/ubuntu/oisha-os/venv/bin/python src/main.py
Restart=always
RestartSec=10
EnvironmentFile=/home/ubuntu/oisha-os/.env
StandardOutput=journal
StandardError=journal
SyslogIdentifier=oisha-os

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/home/ubuntu/oisha-os/data

[Install]
WantedBy=multi-user.target
SERVICE

# 6. Log rotation
sudo tee /etc/logrotate.d/oisha-os > /dev/null <<'LOGROTATE'
/home/ubuntu/oisha-os/data/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
LOGROTATE

# 7. Watchdog cron (every 5 min)
chmod +x "$OISHA_DIR/deploy/oracle-watchdog.sh"
CRON_LINE="*/5 * * * * $OISHA_DIR/deploy/oracle-watchdog.sh >> /var/log/oisha-watchdog.log 2>&1"
(crontab -l 2>/dev/null | grep -v "oracle-watchdog" ; echo "$CRON_LINE") | crontab -

# 8. Auto-start on reboot
sudo tee /etc/cron.d/oisha-reboot > /dev/null <<'REBOOT'
@reboot ubuntu sleep 30 && sudo systemctl start oisha-os
REBOOT

# 9. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable oisha-os
echo ""
echo "=== Setup complete! ==="
echo "Next steps:"
echo "  1. Create .env file: nano /home/ubuntu/oisha-os/.env"
echo "  2. Start: sudo systemctl start oisha-os"
echo "  3. Check: sudo journalctl -u oisha-os -f"
echo "  4. Watchdog: tail -f /var/log/oisha-watchdog.log"
