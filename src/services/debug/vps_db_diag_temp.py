
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
    
    print('\n--- Recent messages sample ---')
    samples = cur.execute("SELECT user_id, message_text FROM message_logs WHERE message_text IS NOT NULL AND message_text != '' ORDER BY created_at DESC LIMIT 5").fetchall()
    for uid, msg in samples:
        print(f'[{uid}]: {msg[:100]}')

except Exception as e:
    print(f'DB Error: {e}')

conn.close()
