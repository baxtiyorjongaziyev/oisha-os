
import sqlite3
import datetime

def analyze_local_db():
    conn = sqlite3.connect('vps_bot_database_final_v2.db')
    cursor = conn.cursor()
    
    # Get columns of message_logs
    cursor.execute("PRAGMA table_info(message_logs);")
    columns = cursor.fetchall()
    col_names = [c[1] for c in columns]
    
    # Calculate 24h ago
    one_day_ago = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
    
    print(f"\n--- ANALYZING MESSAGES SINCE {one_day_ago} ---")
    
    select_cols = []
    if 'created_at' in col_names: select_cols.append('created_at')
    # Try common names for sender
    if 'sender_name' in col_names: select_cols.append('sender_name')
    elif 'user_id' in col_names: select_cols.append('user_id')
    
    if 'message_text' in col_names: select_cols.append('message_text')
    if 'is_ai_reply' in col_names: select_cols.append('is_ai_reply')
    
    query = f"SELECT {', '.join(select_cols)} FROM message_logs WHERE created_at >= ? ORDER BY created_at ASC"
    cursor.execute(query, (one_day_ago,))
    rows = cursor.fetchall()
    
    if not rows:
        print('No messages found in the last 24h.')
    else:
        for row in rows:
            # Map columns for printing
            data = dict(zip(select_cols, row))
            timestamp = data.get('created_at', 'N/A')
            sender = data.get('sender_name', data.get('user_id', 'Unknown'))
            text = data.get('message_text', '')
            is_ai = data.get('is_ai_reply', 0)
            
            role = 'OISHA' if is_ai else sender
            print(f"[{timestamp}] {role}: {text}")
            print("-" * 30)
            
    conn.close()

if __name__ == '__main__':
    analyze_local_db()
