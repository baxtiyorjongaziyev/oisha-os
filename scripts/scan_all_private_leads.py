import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

secret = os.getenv("OISHA_API_SECRET", "")
headers = {
    "X-Oisha-Internal-Secret": secret,
    "Authorization": f"Bearer {secret}"
}
base_url = "http://127.0.0.1:8080/api/internal/mcp"

def main():
    resp = requests.get(f"{base_url}/dialogs?limit=50", headers=headers, timeout=25)
    if resp.status_code != 200:
        print("Error fetching dialogs:", resp.status_code)
        return
        
    dialogs = resp.json().get("dialogs", [])
    
    private_active = []
    groups_active = []
    
    for d in dialogs:
        cid = str(d["id"])
        name = d["name"]
        unread = d.get("unread_count", 0)
        is_user = d.get("is_user", False)
        is_group = d.get("is_group", False)
        
        # Skip self & system bots
        if name in ["Baxtiyorjon Gaziyev", "amoBot", "Telegram", "Jon Asisstant AI", "Theo AI"]:
            continue
            
        try:
            m_resp = requests.get(f"{base_url}/messages/{cid}?limit=5", headers=headers, timeout=10)
            msgs = m_resp.json().get("messages", []) if m_resp.status_code == 200 else []
        except Exception:
            msgs = []
            
        if not msgs:
            continue
            
        last_msg = msgs[0] if msgs else {}
        last_date = last_msg.get("date", "")
        last_sender = last_msg.get("sender_name", "")
        last_text = last_msg.get("text", "")
        is_out = last_msg.get("is_out", False)
        
        item = {
            "id": cid,
            "name": name,
            "unread": unread,
            "last_date": last_date[:16] if last_date else "",
            "last_sender": "Me" if is_out else last_sender,
            "last_text": last_text[:120].replace("\n", " "),
            "needs_reply": (not is_out) and (unread > 0 or "2026-08-19" in last_date or "2026-08-20" in last_date)
        }
        
        if is_user:
            private_active.append(item)
        elif is_group:
            groups_active.append(item)
            
    result = {
        "private_chats": private_active,
        "groups": groups_active
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
