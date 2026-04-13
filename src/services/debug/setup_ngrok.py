import paramiko
import sys
import time

HOST = "104.197.19.4"
USER = "baxtiyorjongaziyev"
PASSWORD = sys.argv[1] if len(sys.argv) > 1 else ""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD)
transport = ssh.get_transport()

def sudo_run(cmd):
    """sudo buyruqni stdin orqali parol bilan ishlatish."""
    channel = transport.open_session()
    channel.set_combine_stderr(True)
    channel.exec_command(f"echo '{PASSWORD}' | sudo -S {cmd}")
    time.sleep(2)
    out = ""
    while channel.recv_ready():
        out += channel.recv(4096).decode()
    return out

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    stdout.channel.recv_exit_status()
    return stdout.read().decode() + stderr.read().decode()

print("=== NGROK O'rnatish ===")

# 1. ngrok yuklab olish (Linux ARM64 yoki AMD64)
print("Architecture tekshirilmoqda...")
arch = run("uname -m").strip()
print(f"Arch: {arch}")

if "aarch64" in arch or "arm" in arch:
    ngrok_url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz"
else:
    ngrok_url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz"

print(f"ngrok yuklab olinmoqda: {ngrok_url}")
out = run(f"wget -q {ngrok_url} -O /tmp/ngrok.tgz && tar -xzf /tmp/ngrok.tgz -C /tmp && echo NGROK_DOWNLOADED")
print(out[:100])

# 2. ngrok ni ko'chirish
out = run("cp /tmp/ngrok /home/baxtiyorjongaziyev/telegram_bot/ngrok && chmod +x /home/baxtiyorjongaziyev/telegram_bot/ngrok && echo NGROK_READY")
print(out[:100])

# 3. ngrok ni background da ishga tushirish (port 5050)
run("pkill -f 'ngrok http' || true")
time.sleep(1)
run("nohup /home/baxtiyorjongaziyev/telegram_bot/ngrok http 5050 --log /tmp/ngrok.log > /dev/null 2>&1 &")
print("ngrok ishga tushirildi, URL kutilmoqda...")
time.sleep(5)

# 4. URL olish
out = run("curl -s http://localhost:4040/api/tunnels 2>/dev/null || echo NO_API")
print("Tunnels:", out[:500])

# 5. Agar local API ishlamasa, log dan URL olish
if "https" not in out:
    log_out = run("cat /tmp/ngrok.log 2>/dev/null | grep -o 'url=https://[^ ]*' | head -1")
    print("From log:", log_out[:200])

ssh.close()
