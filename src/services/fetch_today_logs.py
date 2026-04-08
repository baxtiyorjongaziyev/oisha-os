import paramiko
import os

def fetch_today_logs():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        # Script content to run on VPS
        vps_script = """
import sqlite3
import datetime

db_path = '/home/baxtiyorjongaziyev/telegram_bot/bot_database.db'
today = '2026-03-16'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = f'''
        SELECT u.first_name, u.username, m.message_text, m.is_ai_reply, m.created_at
        FROM message_logs m
        JOIN users u ON m.user_id = u.user_id
        WHERE m.created_at LIKE '{today}%'
        ORDER BY m.created_at ASC
    '''
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    if not rows:
        print('BUGUNGI SUHBATLAR TOPILMADI.')
    else:
        current_user = None
        for r in rows:
            name = f'{r[0]} (@{r[1]})' if r[1] else r[0]
            if name != current_user:
                print(f'\\n--- USER: {name} ---')
                current_user = name
            
            prefix = '🤖 AI' if r[3] else '👤 USER'
            print(f'[{r[4]}] {prefix}: {r[2]}')
            
    conn.close()
except Exception as e:
    print(f'ERROR: {e}')
"""
        # Upload script to VPS
        sftp = ssh.open_sftp()
        with sftp.file('/home/baxtiyorjongaziyev/telegram_bot/today_analyzer.py', 'w') as f:
            f.write(vps_script)
        sftp.close()
        
        # Run script
        stdin, stdout, stderr = ssh.exec_command('python3 /home/baxtiyorjongaziyev/telegram_bot/today_analyzer.py')
        output = stdout.read().decode()
        print(output)
        
        ssh.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_today_logs()
