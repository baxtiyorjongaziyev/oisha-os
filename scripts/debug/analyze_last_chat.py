import paramiko
import os
import sys

# Windowsda emoji chiqarish uchun utf-8 ni majburlash
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

hostname = '109.199.100.137'
username = 'root'
password = '#8tV9Hsm0aMqapdb'

def get_server_info():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password)
        
        container_name = "telegram_business_bot"
        
        print(f"--- RECENT MESSAGES FROM DATABASE (LAST 30) ---")
        py_code = """
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db_path = 'bot_database.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
# Oxirgi 30 ta xabarni olish
cursor.execute("SELECT created_at, user_id, message_text, is_ai_reply FROM message_logs ORDER BY created_at DESC LIMIT 30")
rows = cursor.fetchall()

print(f'Found {len(rows)} messages.')
for r in reversed(rows):
    role = "AI" if r[3] else "USER"
    print(f"[{r[0]}] User: {r[1]} ({role}): {r[2]}")
conn.close()
"""
        cmd = f"docker exec -i {container_name} python3"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdin.write(py_code)
        stdin.channel.shutdown_write()
        
        print(stdout.read().decode('utf-8', errors='replace'))
        err = stderr.read().decode('utf-8', errors='replace')
        if err:
            print("Stderr:")
            print(err)
            
        ssh.close()
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    get_server_info()
