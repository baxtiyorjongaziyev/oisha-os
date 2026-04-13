import paramiko
import sys

HOST = "104.197.19.4"
USER = "baxtiyorjongaziyev"
PASSWORD = sys.argv[1] if len(sys.argv) > 1 else ""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD)

def run(cmd, wait=True):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    if wait:
        stdout.channel.recv_exit_status()
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out + err

# 1. nginx o'rnatish
print("nginx o'rnatilmoqda...")
print(run("sudo apt-get install -y nginx 2>&1 | tail -3"))

# 2. SSL self-signed sertifikat
print("SSL sertifikat yaratilmoqda...")
ssl_cmd = (
    "sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 "
    "-keyout /etc/ssl/private/wb.key "
    "-out /etc/ssl/certs/wb.crt "
    "-subj '/C=UZ/ST=Tashkent/O=JonBranding/CN=104.197.19.4' 2>&1"
)
print(run(ssl_cmd)[:200])

# 3. Nginx config
nginx_conf = (
    "server {\\n"
    "    listen 443 ssl;\\n"
    "    ssl_certificate /etc/ssl/certs/wb.crt;\\n"
    "    ssl_certificate_key /etc/ssl/private/wb.key;\\n"
    "    location /meta/ { proxy_pass http://127.0.0.1:5050; }\\n"
    "    location /health { proxy_pass http://127.0.0.1:5050; }\\n"
    "}"
)
print("Nginx config yozilmoqda...")
print(run(f"printf '{nginx_conf}' | sudo tee /etc/nginx/conf.d/meta-webhook.conf"))

# 4. nginx tekshirish va restart
print("nginx ishga tushirilmoqda...")
result = run("sudo nginx -t 2>&1 && sudo systemctl restart nginx && echo NGINX_OK")
print(result[:200])

# 5. Port 443 ochish
print("443 port ochilmoqda...")
print(run("sudo ufw allow 443/tcp 2>&1; sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT 2>&1; echo FW_443_OK"))

# 6. Test
print("Test qilinmoqda...")
import time; time.sleep(2)
print(run("curl -sk https://104.197.19.4/health || echo HTTPS_TEST_FAILED"))

ssh.close()
print("Tayyor!")
