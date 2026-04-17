import sqlite3
import os

db_path = os.path.join(os.getcwd(), 'data', 'bot.db')
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    # Try current directory data
    db_path = os.path.join('data', 'bot.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Checking scheduled_jobs for 2026-04-08:")
try:
    cursor.execute("SELECT * FROM scheduled_jobs WHERE run_date = '2026-04-08'")
    rows = cursor.fetchall()
    if not rows:
        print("No jobs found for today.")
    for row in rows:
        print(row)
except Exception as e:
    print(f"Error checking today's jobs: {e}")

print("\nChecking last 10 logs in scheduled_jobs:")
try:
    cursor.execute("SELECT * FROM scheduled_jobs ORDER BY created_at DESC LIMIT 10")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
except Exception as e:
    print(f"Error checking last logs: {e}")

conn.close()
