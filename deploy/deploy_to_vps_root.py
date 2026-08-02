import paramiko
import os
import sys

# VPS Credentials
HOST = os.environ.get('SSH_HOST', '109.199.100.137')
USER = os.environ.get('SSH_USER', 'root')
PASSWORD = os.environ.get('SSH_PASSWORD', '')
REMOTE_DIR = "/root/telegram_bot"

def deploy():
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    
    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
        print("Connected!")
        
        # Ensure remote directory exists
        ssh.exec_command(f"mkdir -p {REMOTE_DIR}")  # nosec B601
        
        sftp = ssh.open_sftp()
        
        # Files to upload (Main files)
        files_to_upload = [
            'config.py', 'settings.py', 'database.py', 'gsheets.py', 'userbot.py', 
            'training_data.txt', '.env', 'service_account.json', 'requirements.txt',
            'agent_core.py', 'agent_orchestrator.py', 'agent_tools.py',
            'learning_engine.py', 'tts_engine.py', 'invoicing.py', 'amocrm_sync.py'
        ]
        
        for f in files_to_upload:
            if os.path.exists(f):
                print(f"Uploading {f}...")
                sftp.put(f, f"{REMOTE_DIR}/{f}")
            else:
                print(f"Warning: {f} not found locally.")

        # Upload directories recursively
        for dir_name in ['agents', 'controllers', 'services']:
            if os.path.exists(dir_name):
                print(f"Uploading {dir_name} directory...")
                ssh.exec_command(f"mkdir -p {REMOTE_DIR}/{dir_name}")  # nosec B601
                for f in os.listdir(dir_name):
                    if f.endswith('.py'):
                        sftp.put(f"{dir_name}/{f}", f"{REMOTE_DIR}/{dir_name}/{f}")
        
        sftp.close()
        
        print("Restarting bot on VPS...")
        # Check if using docker-compose or direct python
        stdin, stdout, stderr = ssh.exec_command(f"ls {REMOTE_DIR}/docker-compose.yml")  # nosec B601
        if stdout.read():
            print("Using Docker Compose...")
            ssh.exec_command(f"cd {REMOTE_DIR} && docker compose down && docker compose up -d")  # nosec B601
        else:
            print("Using direct Python...")
            ssh.exec_command(f"pkill -f userbot.py || true")  # nosec B601
            ssh.exec_command(f"cd {REMOTE_DIR} && nohup python3 userbot.py > bot.log 2>&1 &")  # nosec B601
        
        print("Deployment completed successfully!")
        
    except Exception as e:
        print(f"Deployment failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    deploy()
