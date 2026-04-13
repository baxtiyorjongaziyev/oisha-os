import paramiko
import os

def check_reg():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print("Connecting to VPS...")
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        # 1. Query users with roles
        print("--- REGISTERED TEAM MEMBERS ---")
        query = 'SELECT user_id, first_name, username, role, created_at FROM users WHERE role IS NOT NULL OR role != "";'
        stdin, stdout, stderr = ssh.exec_command(f'sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "{query}"')
        results = stdout.read().decode()
        if results:
            print(results)
        else:
            print("No users with specific roles found yet. Checking all users...")
            stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT user_id, first_name, username, role FROM users LIMIT 10;"')
            print(stdout.read().decode())
            
        # 2. Check last 10 messages for registration commands
        print("\n--- RECENT REGISTRATION LOGS ---")
        msg_query = "SELECT user_id, message_text, created_at FROM message_logs WHERE message_text LIKE '/register%' ORDER BY id DESC LIMIT 10;"
        stdin, stdout, stderr = ssh.exec_command(f'sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "{msg_query}"')
        print(stdout.read().decode())
        
        ssh.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_reg()
