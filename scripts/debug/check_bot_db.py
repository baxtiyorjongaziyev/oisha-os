
import sqlite3
import os

db_path = r"c:\Users\baxti\playground\oisha-os\data\bot_database.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Tables in DB: {tables}")
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"Table {table}: {count} rows")
            
        if 'processed_messages' in tables:
            cursor.execute("SELECT status, COUNT(*) FROM processed_messages GROUP BY status")
            rows = cursor.fetchall()
            print("Processed messages summary:")
            for row in rows:
                print(f"Status: {row[0]}, Count: {row[1]}")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
