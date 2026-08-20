import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

secret = os.getenv("OISHA_API_SECRET", "")
headers = {
    "X-Oisha-Internal-Secret": secret,
    "Authorization": f"Bearer {secret}"
}

print(f"[*] Testing GET /api/internal/mcp/dialogs?limit=10 ...")
t0 = time.time()
try:
    resp = requests.get("http://127.0.0.1:8080/api/internal/mcp/dialogs?limit=10", headers=headers, timeout=60)
    print(f"[+] Status: {resp.status_code}, Latency: {time.time()-t0:.2f}s")
    if resp.status_code == 200:
        data = resp.json()
        print(f"[+] Dialogs count: {len(data.get('dialogs', []))}")
        for d in data.get("dialogs", []):
            print(f" - [{d.get('id')}] {d.get('name')} (user={d.get('is_user')}, group={d.get('is_group')}, unread={d.get('unread_count')})")
    else:
        print(f"[!] Body: {resp.text}")
except Exception as e:
    print(f"[!] Error after {time.time()-t0:.2f}s: {e}")
