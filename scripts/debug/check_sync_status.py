import csv
import os
import re

def count_unique_leads():
    files = [
        'tn2_with_phone.csv', 'tn2_no_phone.csv',
        'tn3_with_phone.csv', 'tn3_no_phone.csv',
        'tn4_with_phone.csv', 'tn4_no_phone.csv',
        'tn5_with_phone.csv', 'tn5_no_phone.csv'
    ]
    unique_identifiers = set()
    
    for filename in files:
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        phone = row.get('Phone 1 - Value', '').strip().replace('+', '')
                        username = row.get('Notes', '').strip().replace('@', '')
                        
                        if phone:
                            unique_identifiers.add(phone)
                        elif username:
                            unique_identifiers.add(username)
            except Exception:
                pass
                        
    return len(unique_identifiers)

def get_stats_from_logs():
    processed_count = 0
    not_found_count = 0
    saved_count = 0
    
    # Parse sync_output.txt for progress
    if os.path.exists('sync_output.txt'):
        with open('sync_output.txt', 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # OK 158. ... - telefondan saqlandi
            # INFO 159. ... - Telegramda topilmadi
            saved_matches = re.findall(r'OK \d+\.', content)
            not_found_matches = re.findall(r'INFO \d+\. .* - Telegramda topilmadi', content)
            
            saved_count = len(saved_matches)
            not_found_count = len(not_found_matches)
            processed_count = saved_count + not_found_count
            
    return processed_count, saved_count, not_found_count

def count_synced_file():
    sync_file = 'data/synced_contacts.txt'
    if os.path.exists(sync_file):
        with open(sync_file, 'r', encoding='utf-8') as f:
            return len([line for line in f if line.strip()])
    return 0

def main():
    total = count_unique_leads()
    processed, log_saved, not_found = get_stats_from_logs()
    
    # data/synced_contacts.txt is more reliable for total saved across all runs
    actual_saved = count_synced_file()
    
    # Estimating total processed (roughly)
    # Since we don't track permanent "not found", we use the log's ratio or just the log's count
    
    remaining = total - (actual_saved + not_found) # This is an approximation
    if remaining < 0: remaining = 0
    
    progress_percent = ((total - remaining) / total * 100) if total > 0 else 0
    
    print("=" * 40)
    print("      OISHA-OS SYNC MONITOR V2")
    print("=" * 40)
    print(f"Jami leadlar soni:      {total}")
    print(f"Tekshirib chiqildi:     {total - remaining}")
    print(f"  - Telegrami borlar:   {actual_saved} (Saqlandi)")
    print(f"  - Telegrami yo'qlar:  {not_found} (O'tkazib yuborildi)")
    print("-" * 40)
    print(f"Hali kutilmoqda:        {remaining}")
    print(f"Umumiy progress:        {progress_percent:.2f}%")
    print("=" * 40)
    
    if os.path.exists('sync_error.txt'):
        print("\nOxirgi loglar (sync_error.txt):")
        with open('sync_error.txt', 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            for line in lines[-3:]:
                print(">> " + line.strip())

if __name__ == "__main__":
    main()
