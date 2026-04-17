
import sqlite3
import datetime
import os

def inject_final():
    db_file = "bot_database.db"
    now_vps = datetime.datetime.now()
    # 30 minutes ago in VPS time
    msg_time = (now_vps - datetime.timedelta(minutes=30)).isoformat()
    
    msg = "FINAL TEST: Brending strategiyasi uchun qancha vaqt ketadi? Bizga juda tez kerek."
    user_id = 99887766
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO message_logs (user_id, message_text, is_ai_reply, created_at) VALUES (?, ?, ?, ?)", 
                       (user_id, msg, 0, msg_time))
        conn.commit()
        print(f"Successfully injected message at {msg_time}")
        
        # Verify immediately
        cursor.execute("SELECT count(*) FROM message_logs WHERE created_at >= ?", (msg_time,))
        count = cursor.fetchone()[0]
        print(f"Verification: Found {count} messages >= {msg_time}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inject_final()
