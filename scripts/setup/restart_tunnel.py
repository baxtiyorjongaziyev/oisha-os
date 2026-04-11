import paramiko
import time
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=15)
except Exception as e:
    print("Ulanish xatosi:", e)
    sys.exit(1)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode() + stderr.read().decode()

print("1. Hozirgi cloudflared holati:")
print(run("pgrep -af cloudflared"))

print("2. Eski jarayonlarni yopish va qayta ishga tushirish...")
run("pkill -f cloudflared")
time.sleep(2)

token = "eyJhIjoiZTI5ZmRhMmU2NmUwODkyN2E2NDIzYzJkOGQ3MzIwY2UiLCJ0IjoiZmExY2NiNzMtODhmMC00ZWZmLWE4MTMtMzg0NjNmZGM4NGIxIiwicyI6IlpqaGpOelkzTVdZdFl6VmhOeTAwT1RWbExUaGxZMlF0TlRjeE5qSmxNRFJsTW1GayJ9"
run(f"nohup /home/baxtiyorjongaziyev/telegram_bot/cloudflared tunnel run --token {token} > /tmp/cf_run.log 2>&1 &")
time.sleep(6)

print("3. Tunnel loglari:")
print(run("cat /tmp/cf_run.log | head -15"))

print("4. meta_webhook.py holati:")
print(run("pgrep -af meta_webhook"))

print("5. Health check:")
print(run("curl -s http://localhost:5050/health"))

ssh.close()
