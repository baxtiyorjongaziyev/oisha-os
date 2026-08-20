import os
import json
import time
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv

load_dotenv()

secret = os.getenv("OISHA_API_SECRET", "")
headers = {
    "X-Oisha-Internal-Secret": secret,
    "Authorization": f"Bearer {secret}"
}
base_url = "http://127.0.0.1:8080/api/internal/mcp"

# Target key business chats
TARGET_CHATS = [
    {"id": "-1002566480563", "name": "Jon Branding Team", "type": "team"},
    {"id": "-1002060253445", "name": "Tez Dizayn - work group", "type": "design"},
    {"id": "-1003803487986", "name": "Kamila Pardalari | Jon Branding | Patent", "type": "patent_client"},
    {"id": "-5337201825", "name": "Ledir | Jon Branding", "type": "branding_client"},
    {"id": "8802892610", "name": "Shahnoza Business Assistant", "type": "sales_assistant"},
    {"id": "8090679294", "name": "Hasanboy Gaziyev", "type": "patent_partner"},
    {"id": "1420365532", "name": "Zuhriddin", "type": "automation_partner"}
]

def fetch_all_messages_for_chat(chat_id, max_pages=15):
    """Fetch paginated messages going back in time up to 2 years."""
    all_msgs = []
    before_id = None
    cutoff_date = datetime(2024, 8, 1, tzinfo=timezone.utc)
    
    for page in range(max_pages):
        url = f"{base_url}/messages/{chat_id}?limit=100"
        if before_id:
            url += f"&before_id={before_id}"
            
        try:
            resp = requests.get(url, headers=headers, timeout=25)
            if resp.status_code != 200:
                print(f"[!] Error fetching {chat_id} (status {resp.status_code})")
                break
                
            msgs = resp.json().get("messages", [])
            if not msgs:
                break
                
            reached_cutoff = False
            for m in msgs:
                dt_str = m.get("date")
                if dt_str:
                    try:
                        # parse iso format
                        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        if dt < cutoff_date:
                            reached_cutoff = True
                            break
                    except Exception:
                        pass
                all_msgs.append(m)
                
            if reached_cutoff or len(msgs) < 100:
                break
                
            before_id = msgs[-1]["id"]
            time.sleep(0.3)
        except Exception as e:
            print(f"[!] Exception fetching {chat_id} page {page}: {e}")
            break
            
    return all_msgs

def filter_business_insights(messages):
    """Filter and classify messages into projects, finance, decisions, SOPs."""
    keywords_finance = ["so'm", "som", "uzs", "$", "dollar", "to'lov", "tolov", "boji", "narx", "avans", "chek", "hisob", "shartnoma"]
    keywords_projects = ["logo", "brend", "brand", "identity", "patent", "namuna", "tovar belgisi", "dizayn", "variant", "prezentatsiya", "maket"]
    keywords_clients = ["mijoz", "klient", "lead", "uchrashuv", "meeting", "closer", "suhbat", "taklif", "kp", "kontakt"]
    keywords_decisions = ["kelishdik", "tasdiq", "qildik", "boshladik", "rejasi", "qoida", "sop", "topshiriq"]

    categorized = {
        "finance_signals": [],
        "project_milestones": [],
        "client_leads": [],
        "decisions_and_sops": []
    }
    
    for m in messages:
        txt = m.get("text", "")
        if not txt or txt.startswith("[Media"):
            continue
        txt_lower = txt.lower()
        sender = m.get("sender_name", "Unknown")
        is_out = m.get("is_out", False)
        prefix = "Baxtiyorjon (Owner)" if is_out else sender
        date_str = m.get("date", "")[:10]
        
        entry = {
            "date": date_str,
            "sender": prefix,
            "text": txt[:300].replace("\n", " ")
        }
        
        if any(k in txt_lower for k in keywords_finance):
            categorized["finance_signals"].append(entry)
        if any(k in txt_lower for k in keywords_projects):
            categorized["project_milestones"].append(entry)
        if any(k in txt_lower for k in keywords_clients):
            categorized["client_leads"].append(entry)
        if any(k in txt_lower for k in keywords_decisions):
            categorized["decisions_and_sops"].append(entry)
            
    return categorized

def main():
    full_report = {}
    total_msgs = 0
    
    print("[*] 2 yillik Telegram yozishmalarini yuklash boshlandi...")
    for c in TARGET_CHATS:
        cid = c["id"]
        cname = c["name"]
        print(f"[*] Chat yuklanmoqda: {cname} ({cid})...")
        msgs = fetch_all_messages_for_chat(cid, max_pages=15)
        total_msgs += len(msgs)
        print(f"[+] {cname}: {len(msgs)} ta xabar yuklandi.")
        
        insights = filter_business_insights(msgs)
        full_report[cname] = {
            "id": cid,
            "type": c["type"],
            "total_messages": len(msgs),
            "insights": insights
        }
        
    out_file = "data/telegram_2yr_extracted_knowledge.json"
    os.makedirs("data", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(full_report, indent=2, ensure_ascii=False))
        
    print(f"\n[✅] Jami {total_msgs} ta xabar tahlil qilindi va {out_file} ga saqlandi!")

if __name__ == "__main__":
    main()
