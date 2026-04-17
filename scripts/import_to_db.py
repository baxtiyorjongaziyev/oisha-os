import csv
import sqlite3
import os

def import_scraped_list():
    print("[OISHA] Importing scraped list to Database...")
    db_path = 'data/bot.db'
    csv_path = 'data/juma_outreach_list.csv'
    
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Ensure the intent column exists (safety)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN intent TEXT")
    except:
        pass # Already exists

    count = 0
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_id = int(row['user_id'])
            name = row['name']
            first_name = name.split(' ')[0] if name else "Do'stim"
            last_name = ' '.join(name.split(' ')[1:]) if name and ' ' in name else ""
            phone = row['phone']
            username = row['username'].replace('@', '') if row['username'] else None
            
            # UPSERT: Insert or update intent
            query = """
                INSERT INTO users (user_id, first_name, last_name, username, phone, intent)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    intent = 'TN5_CLASSMATE',
                    phone = COALESCE(users.phone, EXCLUDED.phone),
                    username = COALESCE(users.username, EXCLUDED.username)
            """
            cursor.execute(query, (user_id, first_name, last_name, username, phone, 'TN5_CLASSMATE'))
            count += 1

    conn.commit()
    conn.close()
    print(f"Successfully processed {count} contacts. All set as 'TN5_CLASSMATE'.")

if __name__ == "__main__":
    import_scraped_list()
