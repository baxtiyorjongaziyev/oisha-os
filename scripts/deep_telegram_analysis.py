import os
import json
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

secret = os.getenv("OISHA_API_SECRET", "")
headers = {
    "X-Oisha-Internal-Secret": secret,
    "Authorization": f"Bearer {secret}"
}
port = os.getenv("PORT", os.getenv("API_PORT", "8000"))
base_url = f"http://127.0.0.1:{port}/api/internal/mcp"

def get_dialogs(limit=35):
    url = f"{base_url}/dialogs?limit={limit}"
    resp = requests.get(url, headers=headers, timeout=20)
    if resp.status_code == 200:
        return resp.json().get("dialogs", [])
    return []

def get_messages(chat_id, limit=20):
    url = f"{base_url}/messages/{chat_id}?limit={limit}"
    resp = requests.get(url, headers=headers, timeout=20)
    if resp.status_code == 200:
        return resp.json().get("messages", [])
    return []

def main():
    dialogs = get_dialogs(30)
    
    summary = {
        "groups": [],
        "private_chats": [],
        "unread_total": 0,
        "action_items": []
    }
    
    for d in dialogs:
        cid = str(d["id"])
        name = d["name"]
        unread = d.get("unread_count", 0)
        summary["unread_total"] += unread
        
        is_user = d.get("is_user", False)
        is_group = d.get("is_group", False)
        is_channel = d.get("is_channel", False)
        
        # Fetch last 5 messages for context
        try:
            msgs = get_messages(cid, limit=7)
        except Exception:
            msgs = []
            
        recent_text = []
        for m in msgs:
            sender = m.get("sender_name", "Unknown")
            is_out = m.get("is_out", False)
            txt = m.get("text", "")[:120].replace("\n", " ")
            dt = m.get("date", "")
            prefix = "Me" if is_out else sender
            recent_text.append(f"{prefix}: {txt}")
            
        item = {
            "id": cid,
            "name": name,
            "unread": unread,
            "is_user": is_user,
            "is_group": is_group,
            "is_channel": is_channel,
            "recent_messages": recent_text
        }
        
        if is_group:
            summary["groups"].append(item)
        elif is_user:
            # Skip self and common bots
            if name not in ["Baxtiyorjon Gaziyev", "amoBot", "Telegram"]:
                summary["private_chats"].append(item)
        else:
            summary["groups"].append(item)

    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
