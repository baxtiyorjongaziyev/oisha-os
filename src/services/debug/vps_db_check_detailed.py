import paramiko
import os

def check_db_detailed():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122')
        
        print('=== 📊 DETAILED DATABASE CHECK ===')
        
        # 1. Total users
        stdin, stdout, stderr = ssh.exec_command("sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db 'SELECT COUNT(*) FROM users;'")
        print(f'Total users in [users] table: {stdout.read().decode().strip()}')
        
        # 2. Total messages
        stdin, stdout, stderr = ssh.exec_command("sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db 'SELECT COUNT(*) FROM message_logs;'")
        print(f'Total messages in [message_logs]: {stdout.read().decode().strip()}')
        
        # 3. Unique users with messages
        stdin, stdout, stderr = ssh.exec_command("sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db 'SELECT COUNT(DISTINCT user_id) FROM message_logs;'")
        print(f'Unique users with history: {stdout.read().decode().strip()}')
        
        # 4. Message sample (to see if they are empty or meaningful)
        print('\n--- Recent meaningful messages ---')
        stdin, stdout, stderr = ssh.exec_command("sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db \"SELECT user_id, message_text FROM message_logs WHERE message_text IS NOT NULL AND message_text != '' ORDER BY created_at DESC LIMIT 10;\"")
        print(stdout.read().decode())
        
        ssh.close()
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    check_db_detailed()
