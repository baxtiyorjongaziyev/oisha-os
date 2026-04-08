
import sqlite3
import os

db_path = r"c:\Users\baxti\playground\oisha-os\data\oisha_enterprise.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check for processed_messages table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_messages'")
        if cursor.fetchone():
            cursor.execute("SELECT status, COUNT(*) FROM processed_messages GROUP BY status")
            rows = cursor.fetchall()
            print("Processed messages summary:")
            for row in rows:
                print(f"Status: {row[0]}, Count: {row[1]}")
                
            cursor.execute("SELECT COUNT(*) FROM processed_messages WHERE status='synced'")
            synced_count = cursor.fetchone()[0]
            print(f"Total synced: {synced_count}")
        else:
            print("Table processed_messages not found.")
            
        # Check if there are other relevant tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Tables in DB: {[t[0] for t in tables]}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
