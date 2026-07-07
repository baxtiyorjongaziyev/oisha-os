import asyncio
import sqlite3

def run_migration():
    conn = sqlite3.connect("data/bot.db")
    cursor = conn.cursor()
    columns = [
        ("profit_estimate", "INTEGER DEFAULT 0"),
        ("source_manager", "TEXT DEFAULT 'oisha'"),
        ("external_task_id", "TEXT"),
        ("is_frog", "BOOLEAN DEFAULT 0")
    ]
    for col, dtype in columns:
        try:
            cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col} {dtype}")
            print(f"Added column {col}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col} already exists")
            else:
                print(f"Error adding {col}: {e}")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    run_migration()
