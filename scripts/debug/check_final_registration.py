import paramiko
import os

def check():
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        ssh.connect(os.environ.get('VPS_HOST', '104.197.19.4'), username=os.environ.get('VPS_USER', 'baxtiyorjongaziyev'), password=os.environ.get('VPS_PASSWORD', ''), timeout=30)
        
        db_path = '/home/baxtiyorjongaziyev/telegram_bot/bot_database.db'
        
        print("--- USERS ---")
        stdin, stdout, stderr = ssh.exec_command(f'sqlite3 {db_path} "SELECT user_id, first_name, role FROM users;"')  # nosec B601
        print(stdout.read().decode())
        
        print("--- RECENT MESSAGES ---")
        stdin, stdout, stderr = ssh.exec_command(f'sqlite3 {db_path} "SELECT user_id, message_text FROM message_logs ORDER BY id DESC LIMIT 10;"')  # nosec B601
        print(stdout.read().decode())
        
        ssh.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
