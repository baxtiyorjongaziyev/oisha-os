import asyncio
import json
import os
import urllib.request
from dotenv import load_dotenv

load_dotenv()

secret = os.getenv("OISHA_API_SECRET", "")
headers = {
    "X-Oisha-Internal-Secret": secret,
    "Authorization": f"Bearer {secret}"
}

def get_dialogs(limit=25):
    url = f"http://127.0.0.1:8080/api/internal/mcp/dialogs?limit={limit}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data
    except Exception as e:
        return {"error": str(e)}

def analyze_private_chats():
    url = "http://127.0.0.1:8080/api/internal/mcp/analyze_private_chats"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print("=== RECENT DIALOGS ===")
    dialogs = get_dialogs(20)
    print(json.dumps(dialogs, indent=2, ensure_ascii=False))
    
    print("\n=== ANALYZE PRIVATE CHATS ===")
    analysis = analyze_private_chats()
    print(json.dumps(analysis, indent=2, ensure_ascii=False))
