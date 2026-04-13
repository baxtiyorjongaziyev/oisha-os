
import paramiko
import sqlite3
import datetime
import os

def analyze_last_24h():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        sftp = ssh.open_sftp()
        
        # Download the database to analyze locally
        remote_db = '/home/baxtiyorjongaziyev/telegram_bot/bot_database.db'
        local_db = 'vps_bot_database_24h_v2.db'
        print(f'Downloading {remote_db}...')
        sftp.get(remote_db, local_db)
        sftp.close()
        
        conn = sqlite3.connect(local_db)
        cursor = conn.cursor()
        
        # Calculate 24h ago
        now = datetime.datetime.now()
        one_day_ago = (now - datetime.timedelta(days=1)).isoformat()
        
        print(f'\n--- MESSAGES FROM LAST 24H (since {one_day_ago}) ---')
        query = """
            SELECT created_at, sender_name, message_text, is_ai_reply 
            FROM message_logs 
            WHERE created_at >= ?
            ORDER BY created_at ASC
        """
        cursor.execute(query, (one_day_ago,))
        rows = cursor.fetchall()
        
        if not rows:
            print('No messages found in the last 24 hours.')
        else:
            for row in rows:
                timestamp, name, text, is_ai = row
                role = 'OISHA' if is_ai else name
                print(f'[{timestamp}] {role}: {text}')
                print('-' * 20)
        
        conn.close()
        ssh.close()
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    analyze_last_24h()
