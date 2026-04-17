import paramiko
import os

def transfer_and_run():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122')
        
        diag_code = """
import sqlite3
import os

db_path = '/home/baxtiyorjongaziyev/telegram_bot/bot_database.db'
if not os.path.exists(db_path):
    print(f'ERROR: DB not found at {db_path}')
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print('--- DB STATS ---')
try:
    users_count = cur.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    print(f'Users in users table: {users_count}')
    
    logs_count = cur.execute('SELECT COUNT(*) FROM message_logs').fetchone()[0]
    print(f'Total messages in message_logs: {logs_count}')
    
    unique_users = cur.execute('SELECT COUNT(DISTINCT user_id) FROM message_logs').fetchone()[0]
    print(f'Unique users in message_logs: {unique_users}')
    
    print('\\n--- Recent messages sample ---')
    samples = cur.execute("SELECT user_id, message_text FROM message_logs WHERE message_text IS NOT NULL AND message_text != '' ORDER BY created_at DESC LIMIT 5").fetchall()
    for uid, msg in samples:
        print(f'[{uid}]: {msg[:100]}')

except Exception as e:
    print(f'DB Error: {e}')

conn.close()
"""
        # Save to a temporary local file first
        with open('vps_db_diag_temp.py', 'w', encoding='utf-8') as f:
            f.write(diag_code)
            
        # Upload
        sftp = ssh.open_sftp()
        sftp.put('vps_db_diag_temp.py', '/home/baxtiyorjongaziyev/telegram_bot/vps_db_diag.py')
        sftp.close()
        
        # Run
        print('=== RUNNING DIAG SCRIPT ON VPS ===')
        stdin, stdout, stderr = ssh.exec_command('python3 /home/baxtiyorjongaziyev/telegram_bot/vps_db_diag.py')
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        ssh.close()
    except Exception as e:
        print(f'Local Error: {e}')

if __name__ == '__main__':
    transfer_and_run()
