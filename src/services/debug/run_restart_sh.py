import paramiko
import sys
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=20)
except Exception as e:
    print("Ulanish xatosi:", e)
    sys.exit(1)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode() + stderr.read().decode()

# 1. Shell skriptini yaratish
shell_script = """#!/bin/bash
# Port 5050 ni tozalash
pkill -9 -f meta_webhook.py
pkill -9 -f cloudflared
pkill -9 -f userbot.py

# Systemd ni yangilash
systemctl --user daemon-reload

# Xizmatlarni yoqish va ishga tushirish
systemctl --user enable cloudflared meta_webhook userbot
systemctl --user restart cloudflared
sleep 2
systemctl --user restart meta_webhook
sleep 2
systemctl --user restart userbot
sleep 3
"""

print("1. Restart skriptini serverga yuklash...")
run(f"echo '{shell_script}' > /home/baxtiyorjongaziyev/restart_all.sh")
run("chmod +x /home/baxtiyorjongaziyev/restart_all.sh")

print("2. Skriptni ishga tushirish...")
print(run("/home/baxtiyorjongaziyev/restart_all.sh"))

print("3. Holatni tekshirish...")
print(run("systemctl --user status cloudflared meta_webhook userbot --no-pager | grep -E '●|Active'"))

print("4. Health check:")
print(run("curl -s http://localhost:5050/health"))

ssh.close()
