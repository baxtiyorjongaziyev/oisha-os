
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
    
    # Check total users
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    # Check synced mass contacts (dummy_id < 0)
    cursor.execute("SELECT COUNT(*) FROM processed_messages WHERE status = 'synced_mass'")
    synced_mass = cursor.fetchone()[0]
    
    # Check total processed
    cursor.execute("SELECT COUNT(*) FROM processed_messages")
    total_processed = cursor.fetchone()[0]

    print(f"--- DATABASE STATUS ---")
    print(f"Total Users in 'users' table: {total_users}")
    print(f"Mass Sync Contacts (synced_mass): {synced_mass}")
    print(f"Total entries in processed_messages: {total_processed}")
    
    conn.close()

if __name__ == "__main__":
    check_sync()
