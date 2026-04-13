#!/usr/bin/env python3
import csv
import os

FILES_TO_FIX = [
    'tn2_no_phone.csv',
    'tn3_no_phone.csv',
    'tn4_no_phone.csv',
    'tn5_no_phone.csv'
]

def fix_duplicates(filename):
    if not os.path.exists(filename):
        print(f"Skipped: {filename} not found.")
        return

    temp_filename = filename + '.tmp'
    
    with open(filename, 'r', encoding='utf-8') as infile, \
         open(temp_filename, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        writer.writeheader()
        
        # Identify the group code from the filename (e.g. TN2)
        group_code = filename.split('_')[0].upper()
        double_code = f"{group_code} {group_code}"
        
        count = 0
        for row in reader:
            original_name = row.get('Name', '')
            original_family = row.get('Family Name', '')
            
            # Replace double codes and trailing Gr if needed
            new_name = original_name.replace(double_code, group_code)
            new_family = original_family.replace(double_code, group_code)
            
            if new_name != original_name or new_family != original_family:
                row['Name'] = new_name
                row['Family Name'] = new_family
                count += 1
            
            writer.writerow(row)
            
    # Overwrite the original file with the fixed one
    os.replace(temp_filename, filename)
    print(f"Fixed {count} rows in {filename}.")

if __name__ == "__main__":
    for f in FILES_TO_FIX:
        fix_duplicates(f)
    print("Done fixing CSV files.")
