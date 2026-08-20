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

# Target key chats to inspect closely
KEY_CHATS = [
    {"id": "-1002566480563", "name": "Jon Branding Team"},
    {"id": "-1002060253445", "name": "Tez Dizayn - work group"},
    {"id": "-1003803487986", "name": "Kamila Pardalari | Jon Branding | Patent"},
    {"id": "8802892610", "name": "Shahnoza Business Asisstant Jon Work"},
    {"id": "1420365532", "name": "Zuhriddin"},
    {"id": "-1003496493814", "name": "TEZ NATIJA 6 UMUMIY"}
]

def get_messages(chat_id, limit=25):
    url = f"{base_url}/messages/{chat_id}?limit={limit}"
    resp = requests.get(url, headers=headers, timeout=20)
    if resp.status_code == 200:
        return resp.json().get("messages", [])
    return []

def main():
    report = []
    for c in KEY_CHATS:
        msgs = get_messages(c["id"], limit=15)
        formatted = []
        for m in msgs:
            sender = m.get("sender_name", "Unknown")
            is_out = m.get("is_out", False)
            txt = m.get("text", "")
            dt = m.get("date", "")
            formatted.append({
                "time": dt[:16] if dt else "",
                "sender": "Baxtiyorjon (Me)" if is_out else sender,
                "text": txt
            })
        report.append({
            "chat_name": c["name"],
            "chat_id": c["id"],
            "messages": formatted[::-1] # chronological
        })
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
