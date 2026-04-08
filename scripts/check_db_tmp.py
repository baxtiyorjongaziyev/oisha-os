import sqlite3
import os

db_path = 'c:\\Users\\baxti\\.gemini\\antigravity\\playground\\oisha-os\\bot_database.db'

def check_db():
    if not os.path.exists(db_path):
        print(f"Database fayli topilmadi: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Jadvallarni tekshirish
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"Mavjud jadvallar: {tables}")
        
        if 'processed_messages' in tables:
            cursor.execute("SELECT status, count(*) FROM processed_messages GROUP BY status")
            stats = cursor.fetchall()
            print(f"\n Leadlar statistikasi (processed_messages):")
            for stat in stats:
                print(f" - {stat[0]}: {stat[1]} ta")
                
            cursor.execute("SELECT message_id, status, processed_at FROM processed_messages WHERE status='synced' ORDER BY processed_at DESC LIMIT 5")
            synced = cursor.fetchall()
            print("\n Oxirgi sinxronizatsiya qilingan (synced) leadlar:")
            if not synced:
                 print("  Hali saqlanganlar yo'q.")
            for s in synced:
                print(f"  - MessageID {s[0]} | Vaqt: {s[2]}")
        else:
            print("\n 'processed_messages' jadvali hali yaratilmagan (yoki bot ishlashga ulgurmadi).")
            
    except Exception as e:
        print(f"Xato yuz berdi: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_db()
