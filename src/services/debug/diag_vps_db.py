
import sqlite3
import datetime
import subprocess

def diag():
    print("--- VPS TIME ---")
    print(datetime.datetime.now().isoformat())
    
    db_file = "bot_database.db"
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        print("--- RECENT MSGS ---")
        cursor.execute("SELECT created_at, message_text FROM message_logs ORDER BY created_at DESC LIMIT 5")
        for row in cursor.fetchall():
            print(f"{row[0]} | {row[1]}")
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

if __name__ == "__main__":
    diag()
