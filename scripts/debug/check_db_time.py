
import sqlite3
import datetime

def check_db_time():
    try:
        conn = sqlite3.connect('vps_bot_database_final_v2.db')
        cursor = conn.cursor()
        cursor.execute("SELECT created_at FROM message_logs ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        print(f"Latest message in DB: {row[0] if row else 'None'}")
        print(f"Local now: {datetime.datetime.now().isoformat()}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_db_time()
