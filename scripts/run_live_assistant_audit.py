import os
import sys
import json
import requests
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from src.services.core.assistant.telegram_assistant_advisor import (
    TelegramAssistantAdvisor,
    SHAHNOZA_USER_ID,
)

# Oracle VM MCP API configuration
API_URL = "http://163.192.10.104:8080/api/internal/mcp"
OISHA_SECRET = "8f94b1a8d052b66bf130c007137f7a22bf7230b77b7ccb8a"

headers = {
    "X-Oisha-Internal-Secret": OISHA_SECRET,
    "Authorization": f"Bearer {OISHA_SECRET}"
}

print("[*] 1. Oracle VM dagi jonli Telegram muloqotlarini olish...")

advisor = TelegramAssistantAdvisor()
audit_tasks = []

# Fetch active dialogs
try:
    resp = requests.get(f"{API_URL}/dialogs?limit=15", headers=headers, timeout=10)
    if resp.status_code == 200:
        dialogs = resp.json().get("dialogs", [])
        print(f"[+] {len(dialogs)} ta faol dialog topildi.")
        
        for d in dialogs:
            chat_id = d.get("id")
            title = d.get("name") or d.get("title") or "Noma'lum"
            
            # Fetch last 5 messages for this chat
            try:
                m_resp = requests.get(f"{API_URL}/messages/{chat_id}?limit=5", headers=headers, timeout=10)
                if m_resp.status_code == 200:
                    messages = m_resp.json().get("messages", [])
                    task = advisor.analyze_chat_for_assistant(
                        chat_id=chat_id,
                        chat_title=title,
                        messages=messages,
                        owner_id=150074828,
                    )
                    if task:
                        audit_tasks.append(task)
                        print(f"  [⚡ Yangi Tavsiya] {title}: {task['action_type']}")
            except Exception as m_err:
                pass
    else:
        print(f"[!] Dialoglar API javobi: {resp.status_code}")
except Exception as e:
    print(f"[!] Live API ulanishida xatolik: {e}. Zaxira tahlil ishlatilmoqda.")

# If live API is unreachable or no new unread, check extracted live knowledge
if not audit_tasks and os.path.exists("data/telegram_2yr_extracted_knowledge.json"):
    with open("data/telegram_2yr_extracted_knowledge.json", "r", encoding="utf-8") as f:
        cache_data = json.load(f)
    
    for cname, cinfo in cache_data.items():
        if "Shahnoza" in cname or "Team" in cname:
            continue
        msgs = cinfo.get("messages", [])
        if msgs:
            task = advisor.analyze_chat_for_assistant(
                chat_id=cinfo.get("chat_id", 0),
                chat_title=cname,
                messages=msgs[-5:],
                owner_id=150074828,
            )
            if task:
                audit_tasks.append(task)

print(f"\n[*] 2. Jami shakllantirilgan tavsiyalar soni: {len(audit_tasks)} ta")

# 3. Record in Obsidian Second Brain
if audit_tasks:
    recorded = advisor.record_in_obsidian(audit_tasks)
    print(f"[+] Obsidian 20-Areas/Yordamchi Vazifalari.md ga yozildi: {recorded}")
    
    # Print formatted alerts for Shahnoza
    print("\n" + "="*50)
    print("📢 SHAHNOZAGA YUBORILADIGAN TAVSIYALAR RO'YXATI:")
    print("="*50)
    for t in audit_tasks:
        print(advisor.format_telegram_alert(t))
        print("-" * 50)
else:
    print("[+] Hozirda zudlik bilan aralashuv talab qiluvchi yangi muammoli xabarlar yo'q.")
