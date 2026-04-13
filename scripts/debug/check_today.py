import sqlite3
from datetime import datetime

def check_today():
    try:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        
        # Get all messages from today (2026-03-29)
        today = "2026-03-29"
        query = "SELECT timestamp, user_id, message FROM messages WHERE timestamp LIKE ? ORDER BY timestamp DESC"
        cursor.execute(query, (f"{today}%",))
        rows = cursor.fetchall()
        
        print(f"--- Bugungi suhbatlar tahlili ({today}) ---")
        if not rows:
            print("Bugun hali birorta ma'lumot saqlanmagan yoki xabarlar bazaga tushmadi.")
            return

        for r in rows:
            print(f"[{r[0]}] User {r[1]}: {r[2][:100]}...")
            
        conn.close()
    except Exception as e:
        print(f"Xato: {e}")

if __name__ == "__main__":
    check_today()
