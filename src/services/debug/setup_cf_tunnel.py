import paramiko
import sys
import time

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

cert_path = "/home/baxtiyorjongaziyev/.cloudflared/cert.pem"

print("1. Eski tunnellarni tozalash...")
run(f"/home/baxtiyorjongaziyev/telegram_bot/cloudflared tunnel cleanup meta-webhook")
run(f"/home/baxtiyorjongaziyev/telegram_bot/cloudflared tunnel delete meta-webhook")
time.sleep(2)

print("2. Yangi tunnel yaratilishi...")
cmd = f"/home/baxtiyorjongaziyev/telegram_bot/cloudflared tunnel --origincert {cert_path} create meta-webhook"
out = run(cmd)
print(out)

tunnel_id = ""
for line in out.split("\\n"):
    if "Created tunnel meta-webhook with id" in line:
        tunnel_id = line.split("id ")[1].strip()
        break

if not tunnel_id:
    outlist = run("/home/baxtiyorjongaziyev/telegram_bot/cloudflared tunnel list")
    for line in outlist.split("\\n"):
        if "meta-webhook" in line:
            tunnel_id = line.split()[0].strip()
            break

print("TUNNEL_ID:", tunnel_id)
if not tunnel_id:
    print("Tunnel ID topilmadi!")
    sys.exit(1)

print("3. DNS sozlanmoqda: meta.jonbranding.uz ->", tunnel_id)
out_dns = run(f"/home/baxtiyorjongaziyev/telegram_bot/cloudflared tunnel --origincert {cert_path} route dns meta-webhook meta.jonbranding.uz")
print(out_dns)

print("4. Config fayl yozilmoqda...")
config = f'''url: http://localhost:5050
tunnel: {tunnel_id}
credentials-file: /home/baxtiyorjongaziyev/.cloudflared/{tunnel_id}.json'''

run(f"echo '{config}' > /home/baxtiyorjongaziyev/.cloudflared/config.yml")

print("5. Tunnel ishga tushirilmoqda...")
run("pkill -f cloudflared")
time.sleep(2)
run("nohup /home/baxtiyorjongaziyev/telegram_bot/cloudflared tunnel run meta-webhook > /tmp/cf_run.log 2>&1 &")
time.sleep(4)

print("Tunnel ishlash loglari:")
print(run("cat /tmp/cf_run.log | head -15"))

print("✅ Barcha jarayon yakunlandi. URL: https://meta.jonbranding.uz")
ssh.close()
