
import sqlite3
import os

db_path = r"c:\Users\baxti\playground\oisha-os\data\bot_database.db"

def reset_test_contacts():
    if not os.path.exists(db_path):
        print("Baza topilmadi")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Delete last 5 synced mass contacts to allow re-run
    cursor.execute("""
        DELETE FROM processed_messages 
        WHERE message_id IN (
            SELECT message_id FROM processed_messages 
            WHERE status = 'synced_mass' 
            ORDER BY processed_at DESC 
            LIMIT 5
        )
    """)
    rows_deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"Reset {rows_deleted} contacts for re-sync testing.")

if __name__ == "__main__":
    reset_test_contacts()
