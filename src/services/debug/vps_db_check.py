import paramiko
import os

def check_db():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122')
        
        print('=== 📊 DATABASE STATISTICS ===')
        
        # Message Logs Stats
        cmd_stats = 'sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT COUNT(id), COUNT(DISTINCT user_id) FROM message_logs;"'
        stdin, stdout, stderr = ssh.exec_command(cmd_stats)
        out = stdout.read().decode().strip()
        print(f'Total messages, Unique users (message_logs): {out}')
        
        # Users Table Stats
        cmd_users = 'sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT COUNT(*) FROM users;"'
        stdin, stdout, stderr = ssh.exec_command(cmd_users)
        out = stdout.read().decode().strip()
        print(f'Total users in users table: {out}')
        
        # Recent Messages Sample
        print('\n=== 💬 RECENT MESSAGE SAMPLES ===')
        cmd_sample = 'sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT user_id, message_text, is_ai_reply FROM message_logs ORDER BY created_at DESC LIMIT 5;"'
        stdin, stdout, stderr = ssh.exec_command(cmd_sample)
        print(stdout.read().decode())
        
        ssh.close()
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    check_db()
