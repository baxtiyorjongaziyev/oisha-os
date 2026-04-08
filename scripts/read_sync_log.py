
import os

file_path = r"c:\Users\baxti\playground\oisha-os\sync_output.txt"
if os.path.exists(file_path):
    with open(file_path, 'rb') as f:
        content = f.read()
        # Try a few encodings
        for enc in ['utf-16', 'utf-8', 'latin-1']:
            try:
                text = content.decode(enc)
                print(f"--- CONTENT ({enc}) ---")
                print(text[-2000:]) # Last 2000 chars
                break
            except:
                continue
else:
    print("File not found")
