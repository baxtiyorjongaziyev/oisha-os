from src.database import Database
db = Database()
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print(f"Tables: {tables}")
if 'daily_plans' in tables:
    print("SUCCESS: 'daily_plans' table exists.")
    cursor.execute("PRAGMA table_info(daily_plans)")
    columns = [r[1] for r in cursor.fetchall()]
    print(f"Columns: {columns}")
else:
    print("FAILURE: 'daily_plans' table NOT found.")
