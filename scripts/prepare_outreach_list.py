import csv
import sqlite3
import os

def prepare_list():
    contacts = []
    
    # 1. Load from CSV
    csv_path = 'data/csv/tn5_with_phone.csv'
    if os.path.exists(csv_path):
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # CSV has headers: Name,Given Name,Family Name,Phone 1 - Value,Phone 1 - Type,Notes,Labels
            for row in reader:
                name = row.get('Name') or f"{row.get('Given Name', '')} {row.get('Family Name', '')}".strip()
                phone = row.get('Phone 1 - Value', '').strip()
                if phone:
                    # Clean phone number (remove +, spaces)
                    clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
                    contacts.append({'name': name, 'phone': clean_phone, 'source': 'CSV'})

    print(f"Loaded {len(contacts)} contacts from CSV.")

    # 2. Load from Database
    db_path = 'data/bot.db'
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Look for TN5 classmates
        cursor.execute("SELECT first_name, last_name, phone, username, intent FROM users WHERE last_name LIKE '%TN%' OR intent = 'TN5_CLASSMATE'")
        rows = cursor.fetchall()
        for row in rows:
            name = f"{row[0]} {row[1]}".strip()
            phone = row[2]
            contacts.append({'name': name, 'phone': phone, 'source': 'DB'})
        conn.close()
        print(f"Loaded {len(rows)} potential contacts from DB.")

    # 3. Deduplicate (by phone)
    unique_contacts = {}
    for c in contacts:
        if c['phone'] and c['phone'] not in unique_contacts:
            unique_contacts[c['phone']] = c
    
    print(f"Unique contacts found so far: {len(unique_contacts)}")
    
    # Save to a temporary worklist
    with open('data/juma_outreach_list.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'phone', 'source'])
        writer.writeheader()
        for c in unique_contacts.values():
            writer.writerow(c)
    
    print("Saved worklist to data/juma_outreach_list.csv")

if __name__ == "__main__":
    prepare_list()
