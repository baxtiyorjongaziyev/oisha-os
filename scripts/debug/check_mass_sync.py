
import sqlite3
import os
import sys

# Add src to sys.path
sys.path.append(r"c:\Users\baxti\playground\oisha-os\src")

def check_sync():
    db_path = r"c:\Users\baxti\playground\oisha-os\data\bot_database.db"
    
    if not os.path.exists(db_path):
        print(f"Baza topilmadi: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check synced mass contacts specifically
    cursor.execute("SELECT COUNT(*) FROM processed_messages WHERE message_id < 0")
    mass_synced = cursor.fetchone()[0]
    
    # Last 5 mass synced
    cursor.execute("SELECT message_id, reason FROM processed_messages WHERE message_id < 0 ORDER BY processed_at DESC LIMIT 5")
    last_5 = cursor.fetchall()

    print(f"--- MASS SYNC STATUS ---")
    print(f"Total Mass Synced Contacts (dummy IDs < 0): {mass_synced}")
    print(f"Last 5: {last_5}")
    
    conn.close()

if __name__ == "__main__":
    check_sync()
