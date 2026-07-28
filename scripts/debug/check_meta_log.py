import paramiko
import sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # nosec B507
ssh.connect(os.environ.get('VPS_HOST', '104.197.19.4'), username=os.environ.get('VPS_USER', 'baxtiyorjongaziyev'), password=os.environ.get('VPS_PASSWORD', ''), timeout=15)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)  # nosec B601
    return stdout.read().decode() + stderr.read().decode()

print("meta_webhook.service log:")
print(run("journalctl --user -u meta_webhook --no-pager -n 30"))

print("meta_webhook.py manual test:")
print(run("cd /home/baxtiyorjongaziyev/telegram_bot && ./venv/bin/python -c 'import meta_webhook; print(\"OK\")'"))

ssh.close()
