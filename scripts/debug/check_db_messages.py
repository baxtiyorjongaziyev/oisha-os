import sqlite3

def check_messages(db_path):
    print(f"--- Checking {db_path} ---")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check message_logs
        try:
            cursor.execute("SELECT user_id, message_text, created_at FROM message_logs ORDER BY created_at DESC LIMIT 50")
            msgs = cursor.fetchall()
            if msgs:
                print(f"Last 50 messages in {db_path}:")
                for uid, txt, time in msgs:
                    # Filter out AI replies if we want, but show everything for now
                    print(f"  [{time}] User {uid}: {txt}")
            else:
                print("No messages found.")
        except Exception as e:
            print(f"Could not read message_logs: {e}")

        conn.close()
    except Exception as e:
        print(f"Error opening {db_path}: {e}")

dbs = ["bot_database.db", "vps_bot_database.db", "vps_bot_database_final_v2.db"]
for db in dbs:
    check_messages(db)
