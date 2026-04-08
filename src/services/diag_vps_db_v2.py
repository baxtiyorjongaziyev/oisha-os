
import sqlite3
import datetime
import os

def diag():
    db_file = "bot_database.db"
    now_vps = datetime.datetime.now()
    one_day_ago = (now_vps - datetime.timedelta(days=1)).isoformat()
    
    print(f"VPS NOW: {now_vps.isoformat()}")
    print(f"ONE DAY AGO (QUERY START): {one_day_ago}")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 1. Total count
        cursor.execute("SELECT count(*) FROM message_logs")
        total = cursor.fetchone()[0]
        print(f"Total messages in DB: {total}")
        
        # 2. Match count
        cursor.execute("SELECT count(*) FROM message_logs WHERE created_at >= ?", (one_day_ago,))
        match_count = cursor.fetchone()[0]
        print(f"Messages in last 24h (>= {one_day_ago}): {match_count}")
        
        # 3. Sample
        if match_count > 0:
            cursor.execute("SELECT created_at, message_text FROM message_logs WHERE created_at >= ? LIMIT 3", (one_day_ago,))
            for row in cursor.fetchall():
                print(f"MATCH: {row[0]} | {row[1]}")
        else:
            print("No matches found. Checking latest entry raw value:")
            cursor.execute("SELECT created_at FROM message_logs ORDER BY created_at DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                print(f"Latest in DB: {row[0]}")
            else:
                print("DB table is EMPTY!")
                
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    diag()
