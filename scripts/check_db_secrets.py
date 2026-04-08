import sqlite3
import json

def check_db(db_path):
    print(f"--- Checking {db_path} ---")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check learned_facts
        try:
            cursor.execute("SELECT fact_key, fact_value FROM learned_facts")
            facts = cursor.fetchall()
            if facts:
                print("Found Facts:")
                for k, v in facts:
                    print(f"  {k}: {v}")
            else:
                print("No facts found in learned_facts.")
        except Exception as e:
            print(f"Could not read learned_facts: {e}")

        # Check users for role=owner or similar
        try:
            cursor.execute("SELECT user_id, username, first_name, role FROM users WHERE role IS NOT NULL")
            users = cursor.fetchall()
            if users:
                print("Team Members:")
                for u in users:
                    print(f"  {u}")
        except Exception as e:
            print(f"Could not read users: {e}")

        conn.close()
    except Exception as e:
        print(f"Error opening {db_path}: {e}")

dbs = ["bot_database.db", "vps_bot_database.db", "vps_bot_database_final_v2.db"]
for db in dbs:
    check_db(db)
