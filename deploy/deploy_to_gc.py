import paramiko
import os
import sys

# Force UTF-8 encoding for output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HOST = "104.197.19.4"
USER = "baxtiyorjongaziyev"
# The user will provide the password, I'll use a placeholder or ask in the script if needed.
# Since I can't interactively ask for a password in a background script, 
# I'll create a script that takes it as an argument.
PASSWORD = sys.argv[1] if len(sys.argv) > 1 else ""

REMOTE_DIR = f"/home/{USER}/telegram_bot"

def deploy():
    if not PASSWORD:
        print("Error: Password not provided!")
        return

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD)
        print("Connected!")
        
        # Create directory
        ssh.exec_command(f"mkdir -p {REMOTE_DIR}")
        
        sftp = ssh.open_sftp()
        files_to_upload = [
            'config.py', 'settings.py', 'database.py', 'gsheets.py', 'userbot.py', 
            'training_data.txt', '.env', 'service_account.json', 'requirements.txt',
            'gcontacts.py', 'gcalendar.py', 'amocrm_sync.py', 'learning_engine.py',
            'tts_engine.py', 'invoicing.py', 'emoji_sync.py', 'proactive_worker.py',
            'meta_webhook.py', 'agent_core.py', 'agent_orchestrator.py', 'agent_tools.py'
        ]
        
        # Upload individual files
        for f in files_to_upload:
            if os.path.exists(f):
                print(f"Uploading {f}...")
                sftp.put(f, f"{REMOTE_DIR}/{f}")
            else:
                print(f"Warning: {f} not found locally.")

        # Upload agents directory recursively
        if os.path.exists('agents'):
            print("Uploading agents directory...")
            ssh.exec_command(f"mkdir -p {REMOTE_DIR}/agents")
            for f in os.listdir('agents'):
                if f.endswith('.py'):
                    sftp.put(f"agents/{f}", f"{REMOTE_DIR}/agents/{f}")
        
        # Upload controllers directory
        if os.path.exists('controllers'):
            print("Uploading controllers directory...")
            ssh.exec_command(f"mkdir -p {REMOTE_DIR}/controllers")
            for f in os.listdir('controllers'):
                if f.endswith('.py'):
                    sftp.put(f"controllers/{f}", f"{REMOTE_DIR}/controllers/{f}")

        # Upload services directory
        if os.path.exists('services'):
            print("Uploading services directory...")
            ssh.exec_command(f"mkdir -p {REMOTE_DIR}/services")
            for f in os.listdir('services'):
                if f.endswith('.py'):
                    sftp.put(f"services/{f}", f"{REMOTE_DIR}/services/{f}")
        
        sftp.close()
        
        print("Setting up environment and starting bot...")
        commands = [
            f"cd {REMOTE_DIR} && sudo apt update && sudo apt install -y python3-pip python3-venv",
            f"pkill -f userbot.py || true",
            f"cd {REMOTE_DIR} && python3 -m venv venv",
            f"cd {REMOTE_DIR} && ./venv/bin/pip install -r requirements.txt",
            f"cd {REMOTE_DIR} && nohup ./venv/bin/python userbot.py > bot.log 2>&1 &",
            f"pkill -f meta_webhook.py || true",
            f"cd {REMOTE_DIR} && ./venv/bin/pip install flask requests 2>/dev/null",
            f"cd {REMOTE_DIR} && nohup ./venv/bin/python meta_webhook.py > meta_webhook.log 2>&1 &",
            # Add cron job for proactive worker (runs every day at 10:00 AM)
            f"(crontab -l 2>/dev/null | grep -v 'proactive_worker.py'; echo '0 10 * * * cd {REMOTE_DIR} && ./venv/bin/python proactive_worker.py --job followup >> proactive.log 2>&1'; echo '0 22 * * * cd {REMOTE_DIR} && ./venv/bin/python proactive_worker.py --job report >> report.log 2>&1') | crontab -"
        ]
        
        for cmd in commands:
            print(f"Executing: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            # We don't wait for the last command as it's nohup
            if "nohup" not in cmd:
                stdout.channel.recv_exit_status()
        
        print("Deployment completed successfully!")
        
    except Exception as e:
        print(f"Deployment failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    deploy()
