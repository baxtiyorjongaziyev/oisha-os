import paramiko
import os
import sys

# Force UTF-8 encoding for output
sys.stdout.reconfigure(encoding='utf-8')

HOST = "109.199.100.137"
USER = "root"
PASSWORD = "#8tV9Hsm0aMqapdb"
REMOTE_DIR = os.environ.get('VPS_DEPLOY_PATH', '/root/telegram_bot')

def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD)
        print("Connected!")
        
        sftp = ssh.open_sftp()
        # Upload service_account.json
        local_file = "service_account.json"
        if os.path.exists(local_file):
            remote_path = f"{REMOTE_DIR}/{local_file}"
            print(f"Uploading {local_file} -> {remote_path}")
            sftp.put(local_file, remote_path)
            print("Upload complete!")
        else:
            print(f"Error: {local_file} not found!")
            return
        
        sftp.close()
        
        print("Restarting Docker Compose...")
        ssh.exec_command(f"cd {REMOTE_DIR} && docker compose restart")
        print("Deployment completed successfully!")
        
    except Exception as e:
        print(f"Deployment failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    deploy()
