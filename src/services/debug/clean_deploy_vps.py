import paramiko
import os
import sys

# VPS Credentials
HOST = "109.199.100.137"
USER = "root"
PASSWORD = "#8tV9Hsm0aMqapdb"
REMOTE_DIR = "/root/telegram_bot"

def clean_deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
        print("Connected!")
        
        # 1. PURGE REMOTE DIRECTORY (EXCEPT .session files)
        print("Cleaning remote directory...")
        ssh.exec_command(f"find {REMOTE_DIR} -maxdepth 1 ! -name '*.session' ! -name 'bot_database.db' ! -name 'telegram_bot' -exec rm -rf {{}} +")
        ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
        
        sftp = ssh.open_sftp()
        
        # 2. UPLOAD EVERYTHING
        files_to_upload = [
            'config.py', 'settings.py', 'database.py', 'gsheets.py', 'userbot.py', 
            'training_data.txt', '.env', 'service_account.json', 'requirements.txt',
            'agent_core.py', 'agent_orchestrator.py', 'agent_tools.py',
            'learning_engine.py', 'tts_engine.py', 'invoicing.py', 'amocrm_sync.py',
            'docker-compose.yml', 'Dockerfile'
        ]
        
        for f in files_to_upload:
            if os.path.exists(f):
                print(f"Uploading {f}...")
                sftp.put(f, f"{REMOTE_DIR}/{f}")
        
        for dir_name in ['agents', 'controllers', 'services']:
            if os.path.exists(dir_name):
                print(f"Uploading {dir_name}/...")
                ssh.exec_command(f"mkdir -p {REMOTE_DIR}/{dir_name}")
                for f in os.listdir(dir_name):
                    if f.endswith('.py'):
                        sftp.put(f"{dir_name}/{f}", f"{REMOTE_DIR}/{dir_name}/{f}")
        
        sftp.close()
        
        print("Restarting bot...")
        # Force restart via docker compose if it exists, else direct
        ssh.exec_command(f"cd {REMOTE_DIR} && (docker compose down || true) && (docker compose up -d || nohup python3 userbot.py > bot.log 2>&1 &)")
        
        print("Clean Deployment completed successfully!")
        
    except Exception as e:
        print(f"Deployment failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    clean_deploy()
