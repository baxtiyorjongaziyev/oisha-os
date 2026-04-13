
import sqlite3
import os
import sys
from dotenv import load_dotenv

# Add current path to import bot modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

def migrate():
    from database import Database
    
    local_db_path = "vps_bot_database_final_v2.db"
    
    print(f"Connecting to local DB: {local_db_path}...")
    local_conn = sqlite3.connect(local_db_path)
    local_cursor = local_conn.cursor()
    
    # Initialize Remote Database (Turso)
    print("Initializing Remote Turso DB...")
    remote_db = Database() # This will use config.TURSO_DATABASE_URL/TOKEN
    remote_db.init_db() # Ensure tables exist on Turso
    
    remote_conn = remote_db.get_connection()
    remote_cursor = remote_conn.cursor()

    tables = ["users", "message_logs", "tasks", "purchases", "learned_facts", "agent_actions"]
    
    for table in tables:
        print(f"Migrating table: {table}...")
        try:
            local_cursor.execute(f"SELECT * FROM {table}")
            rows = local_cursor.fetchall()
            
            if not rows:
                print(f"Table {table} is empty. Skipping.")
                continue
                
            # Get column names
            local_cursor.execute(f"PRAGMA table_info({table})")
            cols = [c[1] for c in local_cursor.fetchall()]
            placeholders = ",".join(["?"] * len(cols))
            
            # Using INSERT OR IGNORE to avoid duplicates if re-run
            remote_cursor.executemany(f"INSERT OR IGNORE INTO {table} VALUES ({placeholders})", rows)
            remote_conn.commit()
            print(f"Successfully migrated {len(rows)} rows to {table}.")
        except Exception as e:
            print(f"Error migrating {table}: {e}")

    local_conn.close()
    remote_conn.close()
    print("Migration finished!")

if __name__ == "__main__":
    load_dotenv()
    migrate()
