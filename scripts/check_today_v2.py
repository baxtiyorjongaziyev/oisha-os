import sqlite3

def check_today():
    try:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        
        # Checking for today, March 29, 2026
        today = "2026-03-29"
        query = "SELECT created_at, user_id, message_text FROM message_logs WHERE created_at LIKE ? ORDER BY created_at DESC LIMIT 30"
        cursor.execute(query, (f"{today}%",))
        rows = cursor.fetchall()
        
        print(f"--- Bugungi suhbatlar ({today}) ---")
        if not rows:
            print("Bugun hali birorta ma'lumot saqlanmagan yoki xabarlar bazaga tushmadi.")
            return

        for r in rows:
            print(f"[{r[0]}] User {r[1]}: {r[2][:150]}")
            
        conn.close()
    except Exception as e:
        print(f"Xato: {e}")

if __name__ == "__main__":
    check_today()
