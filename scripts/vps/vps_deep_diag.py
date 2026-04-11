import paramiko
import os
import time

def deep_diag():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print("Connecting to VPS...")
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        # 1. File Listing
        print("--- FILE LISTING ---")
        stdin, stdout, stderr = ssh.exec_command('ls -la /home/baxtiyorjongaziyev/telegram_bot/')
        print(stdout.read().decode())
        
        # 2. .env Content
        print("--- .ENV CONTENT ---")
        stdin, stdout, stderr = ssh.exec_command('cat /home/baxtiyorjongaziyev/telegram_bot/.env')
        print(stdout.read().decode())
        
        # 3. User Table Audit
        print("--- USERS AUDIT ---")
        stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT user_id, first_name, role FROM users;"')
        print(stdout.read().decode())
        
        # 4. Message Log Audit (Last 5)
        print("--- MESSAGE LOGS AUDIT ---")
        stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT user_id, message_content, timestamp FROM message_logs ORDER BY id DESC LIMIT 5;"')
        print(stdout.read().decode())
        
        # 5. Journal Audit
        print("--- JOURNAL AUDIT ---")
        stdin, stdout, stderr = ssh.exec_command('journalctl --user -u userbot -n 30')
        print(stdout.read().decode())
        
        # 6. Current processes
        print("--- PROCESS AUDIT ---")
        stdin, stdout, stderr = ssh.exec_command('ps aux | grep userbot.py | grep -v grep')
        print(stdout.read().decode())
        
        ssh.close()
        print("Diagnostics finished.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    deep_diag()
