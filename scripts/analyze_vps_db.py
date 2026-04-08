
import sqlite3

def analyze_db():
    conn = sqlite3.connect('vps_bot_database.db')
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables: {tables}")
    
    # Get last 100 messages to find the 'rasvo' examples
    try:
        # Check if table 'message_logs' exists
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='message_logs'")
        if cursor.fetchone()[0] == 0:
            print("Table 'message_logs' does not exist.")
            return

        cursor.execute("SELECT user_id, message_text, is_ai_reply, created_at FROM message_logs ORDER BY created_at DESC LIMIT 100")
        rows = cursor.fetchall()
        print('--- LAST 100 MESSAGES ---')
        for row in reversed(rows):
            role = 'OISHA' if row[2] else 'USER'
            print(f'[{row[3]}] {role} ({row[0]}): {row[1]}')
            print('-' * 20)
            
    except Exception as e:
        print(f"Error querying message_logs: {e}")
        # Try to describe table
        cursor.execute("PRAGMA table_info(message_logs)")
        print(f"Message_logs table info: {cursor.fetchall()}")

    conn.close()

if __name__ == '__main__':
    analyze_db()
