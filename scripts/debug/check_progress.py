import sqlite3
import os

def check_progress():
    db_path = os.path.join('data', 'bot_database.db')
    if not os.path.exists(db_path):
        print("Baza hali yaratilmagan.")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Prefixlar bo'yicha hisoblash
    prefixes = ['TN2', 'TN3', 'TN4', 'TN5']
    print("👸🛡️ Oisha-OS: Tez Natija Sync Progress:")
    
    total = 0
    for prefix in prefixes:
        cursor.execute("SELECT COUNT(*) FROM users WHERE first_name LIKE ?", (f"{prefix}%",))
        count = cursor.fetchone()[0]
        print(f"📦 {prefix}: {count} ta a'zo saqlangan.")
        total += count
        
    print(f"✅ Jami: {total} ta a'zo Smart Memory'da!")
    conn.close()

if __name__ == "__main__":
    check_progress()
