import paramiko
import sys
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=15)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode() + stderr.read().decode()

print("1. 5050-portni band qilgan jarayonni qidirish...")
port_info = run("sudo fuser 5050/tcp").strip()
if not port_info:
    port_info = run("lsof -t -i:5050").strip()

if port_info:
    print(f"Topilgan PID(lar): {port_info}")
    print("2. Jarayonni to'xtatish...")
    run(f"kill -9 {port_info}")
    time.sleep(2)
else:
    print("Portni band qilgan jarayon topilmadi, pkill ishlatiladi.")
    run("pkill -9 -f meta_webhook.py")
    time.sleep(2)

print("3. meta_webhook.service ni qayta ishga tushirish...")
run("systemctl --user restart meta_webhook")
time.sleep(3)

print("4. Status tekshirish...")
print(run("systemctl --user status meta_webhook --no-pager | head -15"))

print("5. Health check (localhost:5050):")
print(run("curl -s http://localhost:5050/health"))

ssh.close()
