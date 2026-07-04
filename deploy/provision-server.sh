#!/bin/bash
# Oisha-OS — Generic server hardening + base setup
# Run ONCE on a fresh Ubuntu 22.04+/24.04 box (Oracle, GCP, any VPS).
# Usage: ssh <user>@<IP> 'bash -s -- <role>' < deploy/provision-server.sh
#   <role> = core | userbot | worker | monitoring
#
# What it does: system update, swap, docker + compose plugin, ufw, fail2ban,
# Asia/Tashkent timezone, a non-root "deploy" user with SSH-key-only sudo
# access, and role-specific firewall ports. It does NOT install oisha-os
# itself or touch any application secrets — pair it with the relevant
# GitHub Actions deploy workflow (oracle-deploy.yml / userbot-vps.yml) once
# the box is reachable.

set -euo pipefail

ROLE="${1:-}"
case "$ROLE" in
  core|userbot|worker|monitoring) ;;
  *)
    echo "Usage: $0 <core|userbot|worker|monitoring>"
    exit 1
    ;;
esac

echo "=== Oisha-OS: provisioning role='$ROLE' ==="

# 1. System update
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
sudo apt-get install -y -qq curl git ufw fail2ban

# 2. Swap (2GB) — skip if one already exists
if ! swapon --show | grep -q .; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
  echo "Swap: 2G created"
else
  echo "Swap: already present, skipping"
fi

# 3. Timezone
sudo timedatectl set-timezone Asia/Tashkent

# 4. Docker + compose plugin
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo systemctl enable --now docker

# 5. Deploy user (SSH-key-only, sudo, docker group)
if ! id -u deploy >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash -G sudo,docker deploy
  sudo mkdir -p /home/deploy/.ssh
  if [ -f "$HOME/.ssh/authorized_keys" ]; then
    sudo cp "$HOME/.ssh/authorized_keys" /home/deploy/.ssh/authorized_keys
  fi
  sudo chown -R deploy:deploy /home/deploy/.ssh
  sudo chmod 700 /home/deploy/.ssh
  sudo chmod 600 /home/deploy/.ssh/authorized_keys 2>/dev/null || true
  echo "deploy ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/deploy > /dev/null
  echo "User 'deploy' created (SSH key copied from current user, sudo, docker group)"
else
  echo "User 'deploy' already exists, skipping"
fi

# 6. SSH hardening — key-only auth
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sudo systemctl reload ssh 2>/dev/null || sudo systemctl reload sshd

# 7. Firewall — role-specific ports
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
case "$ROLE" in
  monitoring)
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    ;;
  core)
    sudo ufw allow 8080/tcp   # health check / internal API
    ;;
  userbot|worker)
    : # SSH only — no inbound app traffic needed
    ;;
esac
sudo ufw --force enable

# 8. fail2ban — default jail (sshd) is enough for a fresh box
sudo systemctl enable --now fail2ban

echo ""
echo "=== Provisioning complete: role=$ROLE ==="
echo "  Timezone:  Asia/Tashkent"
echo "  Docker:    $(docker --version 2>/dev/null || echo 'not found')"
echo "  Swap:      $(swapon --show --noheadings | wc -l) active"
echo "  Firewall:  $(sudo ufw status | head -1)"
echo "  Next step: log in as 'deploy' user, pull oisha-os, wire into"
echo "             the matching GitHub Actions workflow."
