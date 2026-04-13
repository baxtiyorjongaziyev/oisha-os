import paramiko
import sys

HOST = "109.199.100.137"
USER = "root"
PASSWORD = "#8tV9Hsm0aMqapdb"
REMOTE_DIR = "/root/telegram_bot"

def check_status():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD)
        print("Connected!")
        
        print("Checking docker containers...")
        stdin, stdout, stderr = ssh.exec_command("docker ps")
        print(stdout.read().decode())
        
        print("Checking python processes...")
        stdin, stdout, stderr = ssh.exec_command("ps aux | grep userbot.py | grep -v grep")
        print(stdout.read().decode())
        
        print("Checking bot.log tail...")
        stdin, stdout, stderr = ssh.exec_command(f"tail -n 20 {REMOTE_DIR}/bot.log")
        print(stdout.read().decode())

    except Exception as e:
        print(f"Status check failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    check_status()
