import paramiko
import os
import sys
import time

# VPS Details (Production)
HOST = "109.199.100.137"
USER = "root"
PASSWORD = "#8tV9Hsm0aMqapdb"
REMOTE_DIR = "/root/telegram_bot"

def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD)
        print("Connected!")
        
        # Stop any previous bot processes (hard)
        print("Stopping existing bot processes...")
        ssh.exec_command("pkill -9 -f main.py || true")
        ssh.exec_command("pkill -9 -f userbot.py || true")
        ssh.exec_command("pkill -9 -f proactive_worker.py || true")
        time.sleep(2)
        
        sftp = ssh.open_sftp()
        
        # 2. Create remote directories
        print("Creating directory structure...")
        for d in ["agents", "controllers", "services", "handlers", "webapp"]:
            ssh.exec_command(f"mkdir -p {REMOTE_DIR}/{d}")
        
        # 3. Collect all .py files and needed directories
        from glob import glob
        
        # Files in root
        py_files = [f for f in os.listdir(".") if (f.endswith(".py") or f.endswith(".session")) and os.path.isfile(f)]
        root_configs = [".env", "requirements.txt", "training_data.txt", "service_account.json"]
        
        other_files = []
        # Directories to include recursively (src contains the core logic now)
        for d in ["src", "agents", "controllers", "services", "handlers", "webapp"]:
            if os.path.exists(d):
                for root, dirs, files in os.walk(d):
                    for f in files:
                        if f.endswith((".py", ".json", ".txt", ".html", ".css", ".js", ".session", ".db")):
                            rel_path = os.path.join(root, f)
                            other_files.append(rel_path.replace(os.sep, "/"))
        
        paths_to_sync = py_files + root_configs + other_files
        
        for path in paths_to_sync:
            local_path = path.replace("/", os.sep)
            remote_path = f"{REMOTE_DIR}/{path}"
            
            # Ensure all parent subdirectories exist on remote
            if "/" in path:
                remote_subdir = f"{REMOTE_DIR}/{path.rsplit('/', 1)[0]}"
                ssh.exec_command(f"mkdir -p {remote_subdir}")

            if os.path.exists(local_path):
                print(f"Uploading {path} -> {remote_path}...")
                sftp.put(local_path, remote_path)
        
        # [AUDIT] Verify the file was actually updated on remote
        print("Verifying remote file integrity...")
        stdin, stdout, stderr = ssh.exec_command(f"grep '150074828' {REMOTE_DIR}/src/services/access_manager.py")
        if not stdout.read():
            print("❌ ERROR: Remote file integrity check FAILED! The hardcoded ID is missing on VPS.")
            sys.exit(1)
        else:
            print("✅ SUCCESS: Remote file integrity verified.")
        
        sftp.close()
        
        # 4. Set up venv and Install dependencies
        print("Setting up venv and installing requirements on VPS...")
        commands = [
            f"cd {REMOTE_DIR} && python3 -m venv venv",
            f"cd {REMOTE_DIR} && ./venv/bin/pip install --upgrade pip",
            f"cd {REMOTE_DIR} && ./venv/bin/pip install -r requirements.txt"
        ]
        for cmd in commands:
            print(f"Executing: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.channel.recv_exit_status()
        
        # 5. Start the bot using venv
        print("Starting bot in background using venv...")
        # Clear log first
        ssh.exec_command(f"true > {REMOTE_DIR}/bot.log")
        # Start using nohup and venv python
        ssh.exec_command(f"cd {REMOTE_DIR} && nohup ./venv/bin/python3 src/main.py >> bot.log 2>&1 &")
        
        print("Waiting for startup (5s)...")
        time.sleep(5)
        
        # 6. Check logs
        print("\n--- RECENT LOGS FROM VPS ---")
        stdin, stdout, stderr = ssh.exec_command(f"tail -n 100 {REMOTE_DIR}/bot.log")
        log_content = stdout.read().decode('utf-8')
        print(log_content)
        
        print("\n--- REMOTE .ENV CHECK ---")
        stdin, stdout, stderr = ssh.exec_command(f"cat {REMOTE_DIR}/.env")
        print(stdout.read().decode('utf-8'))
        
        if "ERROR" in log_content or "Exception" in log_content:
            print("\n⚠️ WARNING: Potential errors detected in logs!")
        else:
            print("\n✅ Bot started successfully on VPS!")
            
        print("\nDeployment finished.")
        
    except Exception as e:
        print(f"Deployment failed: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    deploy()
