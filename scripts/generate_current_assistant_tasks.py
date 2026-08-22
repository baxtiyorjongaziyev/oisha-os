import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from src.services.core.assistant.telegram_assistant_advisor import (
    TelegramAssistantAdvisor,
    SHAHNOZA_USER_ID,
)

advisor = TelegramAssistantAdvisor()

# Immediate tasks derived from current Telegram business state
CURRENT_LIVE_TASKS = [
    {
        "chat_id": -1003803487986,
        "chat_title": "Kamila Pardalari | Jon Branding | Patent",
        "action_type": "Loyiha statusi va Logotip sotuvi",
        "text": "kamila pardalari logo sorayaptila, patent ekspertizasi davom etmoqda",
        "recommendation": (
            "1. Hasanboydan patent ekspertizasining 1-oylik oraliq holatini oling.\n"
            "2. Mijozga yangi logotip va qadoqlash portfoliosini taqdim qiling va narx taklifini (KP) tasdiqlang."
        ),
        "date": "2026-08-20 15:50"
    },
    {
        "chat_id": -5337201825,
        "chat_title": "Ledir | Jon Branding",
        "action_type": "Domen va Ijtimoiy tarmoqlar",
        "text": "Unvan nomini ijtimoiy tarmoqlarda band qilish va brend nomini yakuniy tekshiruvdan o'tkazish",
        "recommendation": (
            "1. Tanlangan 2 ta brend nomi bo'yicha Instagram, Telegram va .uz domenlarini band qilishni tekshiring.\n"
            "2. Natijalarni guruhga hisobot sifatida yozing."
        ),
        "date": "2026-08-20 15:52"
    },
    {
        "chat_id": 8090679294,
        "chat_title": "Gulnoza opa (Mijoz)",
        "action_type": "Yangi Logotip So'rovi",
        "text": "Gulnoza opaga ham logo kerak ekan, talablarni olish kerak",
        "recommendation": (
            "1. Gulnoza opa bilan bog'lanib, soha yo'nalishi va dizayn talablarini (Brief) oling.\n"
            "2. Byudjetini aniqlab, Tez Dizayn konveyeriga vazifa oching."
        ),
        "date": "2026-08-20 15:53"
    },
    {
        "chat_id": 8802892610,
        "chat_title": "Shavkat Urolog (Lid)",
        "action_type": "Uchrashuv va Strategik Sessiya",
        "text": "Doktor Shavkat bilan shaxsiy brend bo'yicha uchrashuv belgilash kutilmoqda",
        "recommendation": (
            "1. Shavkat aka bilan bog'lanib, ertaga soat 14:00 yoki 16:00 ga 15 daqiqalik qisqa uchrashuv vaqtini tasdiqlang."
        ),
        "date": "2026-08-20 15:54"
    }
]

print("[*] Shaxsiy Yordamchi Shahnoza uchun tavsiyalar qayd etilmoqda...")
success = advisor.record_in_obsidian(CURRENT_LIVE_TASKS)
print(f"[+] Obsidian 20-Areas/Yordamchi Vazifalari.md ga muvaffaqiyatli yozildi: {success}")

print("\n" + "="*60)
print("📢 SHAHNOZAGA YUBORILADIGAN OPERATIV TAVSIYALAR:")
print("="*60)
for t in CURRENT_LIVE_TASKS:
    print(advisor.format_telegram_alert(t))
    print("-" * 60)
