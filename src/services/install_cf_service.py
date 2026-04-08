import paramiko
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

print("1. cloudflared ni /usr/local/bin manziliga o'tkazish...")
print(run("echo 'parol1122' | sudo -S cp /home/baxtiyorjongaziyev/telegram_bot/cloudflared /usr/local/bin/cloudflared"))

print("2. Eskirgan yoki qolib ketgan xizmatlarni tozalash (agar bo'lsa)...")
run("echo 'parol1122' | sudo -S cloudflared service uninstall")
run("echo 'parol1122' | sudo -S rm -rf /etc/cloudflared")

print("3. Cloudflare Tunnel ulanmoqda...")
token_command = "echo 'parol1122' | sudo -S cloudflared service install eyJhIjoiZTI5ZmRhMmU2NmUwODkyN2E2NDIzYzJkOGQ3MzIwY2UiLCJ0IjoiZmExY2NiNzMtODhmMC00ZWZmLWE4MTMtMzg0NjNmZGM4NGIxIiwicyI6IlpqaGpOelkzTVdZdFl6VmhOeTAwT1RWbExUaGxZMlF0TlRjeE5qSmxNRFJsTW1GayJ9"
out = run(token_command)
print(out)

print("4. Xizmat holati текishirilmoqda...")
print(run("systemctl status cloudflared | head -15"))

ssh.close()
