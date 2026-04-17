import paramiko
import sys
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=15)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode() + stderr.read().decode()

print("1. Port 5050 va bot jarayonlarini to'xtatish...")
# Sudo'siz pkill ishlatamiz, chunki jarayonlar bizniki
run("pkill -9 -f meta_webhook.py")
run("pkill -9 -f userbot.py")
run("pkill -9 -f cloudflared")
time.sleep(3)

print("2. Systemd xizmatlarini qayta ishga tushirish...")
run("systemctl --user daemon-reload")
run("systemctl --user restart cloudflared")
time.sleep(2)
run("systemctl --user restart meta_webhook")
time.sleep(2)
run("systemctl --user restart userbot")
time.sleep(5)

print("3. Servicelar holati:")
print(run("systemctl --user status cloudflared --no-pager | grep Active"))
print(run("systemctl --user status meta_webhook --no-pager | grep Active"))
print(run("systemctl --user status userbot --no-pager | grep Active"))

print("4. Health check (localhost:5050):")
print(run("curl -s http://localhost:5050/health"))

ssh.close()
