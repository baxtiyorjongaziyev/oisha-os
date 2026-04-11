import paramiko
import os
import time

def audit():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        # 1. Check users
        print("--- USERS IN DATABASE ---")
        stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT user_id, first_name, username, role FROM users;"')
        print(stdout.read().decode())
        
        # 2. Check current .env size and content snippet
        print("--- .ENV AUDIT ---")
        stdin, stdout, stderr = ssh.exec_command('ls -l /home/baxtiyorjongaziyev/telegram_bot/.env')
        print(stdout.read().decode())
        
        # 3. Clean up .env (Force write a clean one)
        env_content = """API_ID=30643078
API_HASH=***REDACTED***
BOT_TOKEN=8343217526:AAH0odkrzt9hF2xCIxbYped2OnYnP0Txe-4
GEMINI_API_KEY=***REDACTED***
GSHEET_ID=1KEFClhl4mVwCXI3YPfeE1B9X3SOkML2fp3NMocZzm8k
OWNER_ID=150074828
"""
        print("Fixing .env...")
        # Use a temporary file to upload
        with open("clean.env", "w") as f:
            f.write(env_content)
        
        sftp = ssh.open_sftp()
        sftp.put("clean.env", "/home/baxtiyorjongaziyev/telegram_bot/.env")
        sftp.close()
        os.remove("clean.env")
        
        print("Restarting bot...")
        ssh.exec_command('systemctl --user restart userbot')
        
        ssh.close()
        print("Audit and fix done.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    audit()
