import paramiko
import os
import sys

# Force UTF-8 encoding for output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Using the credentials from deploy_creds.py as it seems more specific
HOST = "109.199.100.137"
USER = "root"
PASSWORD = "#8tV9Hsm0aMqapdb"
REMOTE_DIR = os.environ.get('VPS_DEPLOY_PATH', '/root/telegram_bot')

files_to_sync = [
    'userbot.py', 
    'config.py', 
    'database.py', 
    'gsheets.py', 
    'training_data.txt', 
    '.env', 
    'service_account.json', 
    'requirements.txt',
    'gcontacts.py', 
    'gcalendar.py', 
    'amocrm_sync.py', 
    'airtable_sync.py', 
    'scouter.py', 
    'settings.py', 
    'learning_engine.py',
    'tts_engine.py', 
    'invoicing.py', 
    'emoji_sync.py'
]

def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD)
        print("Connected!")
        
        sftp = ssh.open_sftp()
        
        # Ensure REMOTE_DIR exists
        try:
            sftp.mkdir(REMOTE_DIR)
        except IOError:
            pass

        def upload_dir(local_path, remote_path):
            try:
                sftp.mkdir(remote_path)
            except IOError:
                pass
            for item in os.listdir(local_path):
                if item in ['.git', '__pycache__', 'venv', '.env']: continue
                l_p = os.path.join(local_path, item)
                r_p = f"{remote_path}/{item}"
                if os.path.isfile(l_p):
                    print(f"Uploading {l_p} -> {r_p}...")
                    sftp.put(l_p, r_p)
                elif os.path.isdir(l_p):
                    upload_dir(l_p, r_p)

        # Upload root files
        for f in files_to_sync:
            if os.path.exists(f):
                remote_path = f"{REMOTE_DIR}/{f}"
                if os.path.isfile(f):
                    print(f"Uploading {f} -> {remote_path}...")
                    sftp.put(f, remote_path)
            else:
                print(f"Warning: {f} not found locally.")
        
        # Upload mandatory directories
        mandatory_dirs = ['services', 'controllers', 'handlers', 'agents', 'invoices']
        for d in mandatory_dirs:
            if os.path.exists(d):
                upload_dir(d, f"{REMOTE_DIR}/{d}")

        sftp.close()
        
        print("Restarting Docker Compose to apply changes...")
        # We use docker compose restart to ensure the container picks up updated files
        # If it's running via python directly in the container, restart is sufficient
        stdin, stdout, stderr = ssh.exec_command(f"cd {REMOTE_DIR} && docker compose up -d --build")
        stdout.channel.recv_exit_status()
        
        print("Deployment completed successfully!")
        
    except Exception as e:
        print(f"Deployment failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    deploy()
