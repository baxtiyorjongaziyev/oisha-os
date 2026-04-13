import csv
import os

# O'qish
input_file = 'tez_natija_4_contacts.csv'
output_file = 'google_contacts_import.csv'

contacts = []

with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        first_name = row['first_name']
        last_name = row['last_name']
        phone = row['phone']
        username = row['username']
        
        if not phone:
            continue  # Telefon yo'qlarni o'tkazib yuborish
        
        # Ism formati: "Ism Familya TN4 Gr"
        if last_name:
            full_name = f"{first_name} {last_name} TN4 Gr"
            family_name = f"{last_name} TN4 Gr"
        else:
            full_name = f"{first_name} TN4 Gr"
            family_name = "TN4 Gr"
        
        # Note
        note = f"@{username}" if username else "Tez Natija 4"
        
        contacts.append({
            'Name': full_name,
            'Given Name': first_name,
            'Family Name': family_name,
            'Phone 1 - Value': phone,
            'Phone 1 - Type': 'Mobile',
            'Notes': note,
            'Labels': 'TEZ NATIJA 4'  # Label muhim!
        })

# Google Contacts formatida saqlash
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Name', 'Given Name', 'Family Name', 'Phone 1 - Value', 'Phone 1 - Type', 'Notes', 'Labels']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(contacts)

print(f"✅ {len(contacts)} ta kontakt {output_file} fayliga saqlandi!")
print()
print("📱 Google Contacts-ga import qilish uchun:")
print("   1. https://contacts.google.com ga kiring")
print("   2. Chap menyuda 'Import' ni bosing")
print(f"   3. {output_file} faylini tanlang")
print("   4. Label: TEZ NATIJA 4 avtomatik tanlanadi")
