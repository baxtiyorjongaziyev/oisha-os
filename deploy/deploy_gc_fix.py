import paramiko
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HOST = "104.197.19.4"
USER = "baxtiyorjongaziyev"
PASSWORD = "parol1122"
REMOTE_DIR = "/home/baxtiyorjongaziyev/telegram_bot"

files_to_sync = [
    'userbot.py',
    'config.py',
]

def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD)
        print("Connected!")
        
        sftp = ssh.open_sftp()
        for f in files_to_sync:
            if os.path.exists(f):
                remote_path = f"{REMOTE_DIR}/{f}"
                print(f"Uploading {f} -> {remote_path}...")
                sftp.put(f, remote_path)
            else:
                print(f"Warning: {f} not found locally.")
        sftp.close()
        
        print("Restarting bot...")
        # Kill existing process and restart
        ssh.exec_command("pkill -f userbot.py || true")
        import time; time.sleep(2)
        ssh.exec_command(
            f"cd {REMOTE_DIR} && nohup ./venv/bin/python userbot.py > bot.log 2>&1 &"
        )
        time.sleep(3)
        
        # Verify
        stdin, stdout, stderr = ssh.exec_command("ps aux | grep userbot.py | grep -v grep")
        output = stdout.read().decode()
        if output:
            print("Bot is running!")
            print(output)
        else:
            print("WARNING: Bot process not found after restart!")
            
        print("Deployment completed successfully!")
        
    except Exception as e:
        print(f"Deployment failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    deploy()
