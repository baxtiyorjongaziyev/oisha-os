import asyncio
import sqlite3
import os

async def check_ai_messages():
    db_path = "data/bot.db"
    if not os.path.exists(db_path):
        print("Database not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- LAST 20 AI REPLIES ---")
    cursor.execute("""
        SELECT ml.user_id, u.first_name, u.username, ml.message_text, ml.created_at
        FROM message_logs ml
        LEFT JOIN users u ON ml.user_id = u.user_id
        WHERE ml.is_ai_reply = 1
        ORDER BY ml.created_at DESC
        LIMIT 20
    """)
    
    for row in cursor.fetchall():
        uid, name, uname, text, time = row
        print(f"[{time}] TO: {name} (@{uname}) [{uid}]")
        print(f"TEXT: {text}")
        print("-" * 30)
        
    print("\n--- LAST 20 ADVISOR DRAFTS ---")
    # Check if advisor_logs table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='advisor_logs'")
    if cursor.fetchone():
        cursor.execute("SELECT content, created_at FROM advisor_logs ORDER BY created_at DESC LIMIT 20")
        for row in cursor.fetchall():
            print(f"[{row[1]}] DRAFT:\n{row[0]}")
            print("-" * 30)
    else:
        print("advisor_logs table not found.")

    conn.close()

if __name__ == "__main__":
    asyncio.run(check_ai_messages())
