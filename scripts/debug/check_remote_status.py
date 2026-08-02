import paramiko
import sys
import os

HOST = os.environ.get('SSH_HOST', '109.199.100.137')
USER = os.environ.get('SSH_USER', 'root')
PASSWORD = os.environ.get('SSH_PASSWORD', '')
REMOTE_DIR = "/root/telegram_bot"

def check_status():
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    
    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD)
        print("Connected!")
        
        print("Checking docker containers...")
        stdin, stdout, stderr = ssh.exec_command("docker ps")  # nosec B601
        print(stdout.read().decode())
        
        print("Checking python processes...")
        stdin, stdout, stderr = ssh.exec_command("ps aux | grep userbot.py | grep -v grep")  # nosec B601
        print(stdout.read().decode())
        
        print("Checking bot.log tail...")
        stdin, stdout, stderr = ssh.exec_command(f"tail -n 20 {REMOTE_DIR}/bot.log")  # nosec B601
        print(stdout.read().decode())

    except Exception as e:
        print(f"Status check failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    check_status()
