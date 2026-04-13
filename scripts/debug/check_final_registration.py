import paramiko
import os

def check():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        db_path = '/home/baxtiyorjongaziyev/telegram_bot/bot_database.db'
        
        print("--- USERS ---")
        stdin, stdout, stderr = ssh.exec_command(f'sqlite3 {db_path} "SELECT user_id, first_name, role FROM users;"')
        print(stdout.read().decode())
        
        print("--- RECENT MESSAGES ---")
        stdin, stdout, stderr = ssh.exec_command(f'sqlite3 {db_path} "SELECT user_id, message_text FROM message_logs ORDER BY id DESC LIMIT 10;"')
        print(stdout.read().decode())
        
        ssh.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
