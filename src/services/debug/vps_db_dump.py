import paramiko
import os
import time

def db_dump():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print("Connecting to VPS...")
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        # 1. List tables
        print("--- TABLES ---")
        stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db ".tables"')
        print(stdout.read().decode())
        
        # 2. Count users
        print("--- USER COUNT ---")
        stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT count(*) FROM users;"')
        print(stdout.read().decode())
        
        # 3. List all user IDs and names
        print("--- USERS ---")
        stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT user_id, first_name, username FROM users;"')
        print(stdout.read().decode())
        
        # 4. Check for current logs for any incoming messages
        print("--- JOURNAL LAST ---")
        stdin, stdout, stderr = ssh.exec_command('journalctl --user -u userbot -n 100')
        print(stdout.read().decode())

        ssh.close()
        print("Dump finished.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    db_dump()
