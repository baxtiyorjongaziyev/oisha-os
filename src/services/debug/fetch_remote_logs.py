import paramiko
import sys
import io

# Force UTF-8 for output
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def analyze_remote_chats():
    host = '104.197.19.4'
    user = 'baxtiyorjongaziyev'
    password = 'parol1122'
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {host}...")
        ssh.connect(host, username=user, password=password)
        print("Connected!")
        
        # Get last 100 messages from message_logs
        py_code = """
import sqlite3
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db_path = '/home/baxtiyorjongaziyev/telegram_bot/bot_database.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get recent messages
cursor.execute("SELECT created_at, user_id, message_text, is_ai_reply FROM message_logs ORDER BY created_at DESC LIMIT 100")
logs = cursor.fetchall()

# Get lead stats
cursor.execute("SELECT COUNT(*) FROM users")
total_users = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM users WHERE phone IS NOT NULL AND phone != ''")
users_with_phone = cursor.fetchone()[0]

# Print data in a structured way for the analysis script to parse or just display
print(f'Total Users: {total_users}')
print(f'Users with Phone: {users_with_phone}')
print('--- RECENT LOGS ---')
for r in reversed(logs):
    role = "AI" if r[3] else "USER"
    print(f"[{r[0]}] {role} ({r[1]}): {r[2]}")

conn.close()
"""
        stdin, stdout, stderr = ssh.exec_command("python3")
        stdin.write(py_code)
        stdin.channel.shutdown_write()
        
        output = stdout.read().decode('utf-8', errors='replace')
        print(output)
        
    except Exception as e:
        print(f"FAILED: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    analyze_remote_chats()
