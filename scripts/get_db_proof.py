
import sqlite3
import os
import sys

# Add root dir to path
root_dir = r"c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
sys.path.append(root_dir)

def get_db_proof():
    db_path = os.path.join(root_dir, 'bot_database.db')
    if not os.path.exists(db_path):
        print(f"❌ Database fayli topilmadi: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- 📊 MA'LUMOTLAR BAZASI (BOT ISHLAGANI ISBOTI) ---")
    
    # 1. Statuslar bo'yicha hisobot
    cursor.execute("SELECT status, COUNT(*) FROM processed_messages GROUP BY status")
    stats = cursor.fetchall()
    if not stats:
        print("ℹ️ Hozircha qayta ishlangan xabarlar yo'q.")
    else:
        for status, count in stats:
            desc = "Muvaffaqiyatli saqlangan" if status in ["synced", "synced_mass"] else status
            print(f"✅ Status: {desc} | Soni: {count}")

    # 2. Oxirgi 5 ta muvaffaqiyatli sync
    print("\n--- 📝 OXIRGI 5 TA MUVAFFARIYATLI SAQLANGAN LIDLAR ---")
    cursor.execute("""
        SELECT message_id, chat_id, status 
        FROM processed_messages 
        WHERE status IN ('synced', 'synced_mass') 
        ORDER BY rowid DESC 
        LIMIT 5
    """)
    recent = cursor.fetchall()
    for row in recent:
        print(f"✅ MsgID: {row[0]} | Guruh: {row[1]} | Status: {row[2]}")

    conn.close()

if __name__ == "__main__":
    get_db_proof()
