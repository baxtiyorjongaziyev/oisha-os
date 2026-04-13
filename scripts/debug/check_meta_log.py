import paramiko
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=15)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode() + stderr.read().decode()

print("meta_webhook.service log:")
print(run("journalctl --user -u meta_webhook --no-pager -n 30"))

print("meta_webhook.py manual test:")
print(run("cd /home/baxtiyorjongaziyev/telegram_bot && ./venv/bin/python -c 'import meta_webhook; print(\"OK\")'"))

ssh.close()
