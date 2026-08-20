import os
import re
from dotenv import load_dotenv

load_dotenv()

session_file = "data/userbot_session_string.txt"
if os.path.exists(session_file):
    with open(session_file, "r", encoding="utf-8") as f:
        saved_session = f.read().strip()
    
    if saved_session:
        print(f"[*] Valid saved session found ({len(saved_session)} chars).")
        
        env_file = ".env"
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            if "USERBOT_SESSION_STRING=" in content:
                content = re.sub(r"USERBOT_SESSION_STRING=.*", f"USERBOT_SESSION_STRING={saved_session}", content)
            else:
                content += f"\nUSERBOT_SESSION_STRING={saved_session}\n"
            
            with open(env_file, "w", encoding="utf-8") as f:
                f.write(content)
            print("[+] .env file updated with valid USERBOT_SESSION_STRING!")
        else:
            print("[!] .env file not found.")
    else:
        print("[!] Saved session file is empty.")
else:
    print("[!] data/userbot_session_string.txt does not exist.")
