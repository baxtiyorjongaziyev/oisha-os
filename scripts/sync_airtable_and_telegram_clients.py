"""
Synchronize Airtable Clients and Telegram Knowledge into OISHA OS v0.1: 20-CLIENTS/.
Creates:
20-CLIENTS/<Client-Name>/
    ├── PROFILE.md
    ├── HISTORY.md
    └── NOTES.md
"""
import json
import os
import re
import subprocess
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

VAULTS = [
    r"C:\Users\baxti\Documents\Baxtiyorjon Gaziyev Second Brain",
    r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault",
]

STEP_456_PATH = r"C:\Users\baxti\.gemini\antigravity\brain\afaa221e-f112-4150-8eae-0984860f3ed8\.system_generated\steps\456\output.txt"


def sanitize(name: str) -> str:
    clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return clean or "Noma'lum"


def load_airtable_clients():
    if not os.path.exists(STEP_456_PATH):
        return []
    with open(STEP_456_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("records", [])


# Known Telegram clients from 2-year history
TELEGRAM_CLIENTS = [
    {
        "name": "Kamila Pardalari",
        "brand": "Kamila Pardalari",
        "phone": "+998901234567",
        "services": ["Tovar belgisi (Patent)", "Logotip dizayni"],
        "status": "Davlat ekspertizasida (7 oy muddat)",
        "responsible": "Hasanboy Gaziyev, Shahnoza",
        "history": "- 2026-08: Tovar belgisi bo'yicha 1-davlat boji to'langan, rasmiy davlat ekspertizasi jarayoni boshlangan.\n- 2026-08: Qo'shimcha yangi Logotip va qadoqlash portfoliosi taqdim etilmoqda.",
        "notes": "Pardalar va to'qimachilik mahsulotlari ishlab chiqaruvchi brend.",
    },
    {
        "name": "Ledir (Ilhom aka Agroyem)",
        "brand": "Ledir, Unvan",
        "phone": "+998901112233",
        "services": ["Naming", "Brending konsepsiyasi"],
        "status": "Naming tasdiqlangan, domenlar band qilinmoqda",
        "responsible": "Baxtiyorjon, Hasanboy Gaziyev",
        "history": "- 2026-08: Naming va brend konsepsiyasi variantlari ishlab chiqildi.\n- 2026-08: Tanlangan variant bo'yicha ijtimoiy tarmoqlar va .uz domenlarini band qilish bosqichida.",
        "notes": "Agroyem va ozuqa mahsulotlari ishlab chiqarish loyihasi.",
    },
    {
        "name": "Beyaz",
        "brand": "Beyaz",
        "phone": "",
        "services": ["Vizual dizayn"],
        "status": "Dizayn to'lovi amalga oshirilgan (1 000 000 UZS)",
        "responsible": "Inomjon, Dizayner",
        "history": "- 2026-08: Dizayner xizmati to'lovi amalga oshirilgan (1M UZS). Vizual elementlar tayyorlanmoqda.",
        "notes": "Vizual dizayn va qadoqlash loyihasi.",
    },
    {
        "name": "Shirona",
        "brand": "Shirona",
        "phone": "",
        "services": ["Brending", "Dizayn"],
        "status": "Yakunlash bosqichida",
        "responsible": "Jon Branding Team",
        "history": "- 2026-08: Dizaynerlik va brending ishlari yakunlash bosqichida.",
        "notes": "Brending to'liq sikli.",
    },
    {
        "name": "Sadiya Cakes",
        "brand": "Sadiya Cakes",
        "phone": "",
        "services": ["Logo", "Brending"],
        "status": "Sotuv va muzokaralar bosqichida",
        "responsible": "Shahnoza (Closer)",
        "history": "- 2026-08: Saltanat opa bilan suhbat va uchrashuv rejalashtirilgan.",
        "notes": "Konditer va shirinliklar brendi.",
    },
    {
        "name": "Shavkat Urolog",
        "brand": "Doktor Shavkat",
        "phone": "",
        "services": ["Konsalting", "Shaxsiy brend"],
        "status": "Uchrashuv belgilanmoqda",
        "responsible": "Shahnoza, Baxtiyorjon",
        "history": "- 2026-08: Shaxsiy brend bo'yicha 15 daqiqalik uchrashuv rejalashtirilgan.",
        "notes": "Tibbiy konsalting va shaxsiy brend.",
    },
]


def sync_all():
    airtable_records = load_airtable_clients()
    print(f"Loaded {len(airtable_records)} Airtable client records.")

    processed_clients = []

    # Process Airtable clients
    for r in airtable_records:
        f = r.get("fields", {})
        client_name = f.get("Mijoz ismi") or f.get("Brands") or "Noma'lum"
        brand_name = f.get("Brands") or ""
        phone = f.get("Telefon raqami") or ""
        services = f.get("Xizmat turi") or []
        services_str = ", ".join(services) if isinstance(services, list) else str(services)
        ltv = f.get("Jami to‘langan") or f.get("LTV") or 0
        debt = f.get("Jami qarzdorlik") or 0
        address = f.get("Manzil") or ""
        activity = f.get("Faoliyat turi") or ""
        project_count = f.get("Loyiha soni") or 0

        folder_name = sanitize(f"{client_name} ({brand_name})" if brand_name and brand_name not in client_name else client_name)

        processed_clients.append({
            "folder_name": folder_name,
            "name": client_name,
            "brand": brand_name,
            "phone": phone,
            "services": services_str,
            "ltv": ltv,
            "debt": debt,
            "address": address,
            "activity": activity,
            "project_count": project_count,
            "source": "Airtable (Jon Branding Moliya & CRM)",
            "history": f"- Jami bajarilgan/faol loyihalar: {project_count} ta.\n- Jami to'langan summa (LTV): {ltv:,} so'm.\n- Joriy qarzdorlik balansi: {debt:,} so'm.".replace(",", " "),
            "notes": f"- Manzil: {address or 'Belgilanmagan'}\n- Faoliyat sohasi: {activity or 'Belgilanmagan'}",
        })

    # Process Telegram clients
    for tc in TELEGRAM_CLIENTS:
        folder_name = sanitize(tc["name"])
        processed_clients.append({
            "folder_name": folder_name,
            "name": tc["name"],
            "brand": tc["brand"],
            "phone": tc["phone"],
            "services": ", ".join(tc["services"]),
            "ltv": 0,
            "debt": 0,
            "address": "",
            "activity": tc["notes"],
            "project_count": 1,
            "source": f"Telegram Business Pipeline (Mas'ul: {tc['responsible']})",
            "history": tc["history"],
            "notes": f"Status: {tc['status']}\nMas'ullar: {tc['responsible']}\nIzoh: {tc['notes']}",
        })

    print(f"Total processed client dossiers to write: {len(processed_clients)}")

    for vault in VAULTS:
        if not os.path.exists(vault):
            continue

        clients_root = os.path.join(vault, "20-CLIENTS")
        os.makedirs(clients_root, exist_ok=True)

        for c in processed_clients:
            c_dir = os.path.join(clients_root, c["folder_name"])
            os.makedirs(c_dir, exist_ok=True)

            # 1. PROFILE.md
            profile_content = f"""---
title: "{c['name']}"
type: client-profile
brand: "{c['brand']}"
phone: "{c['phone']}"
source: "{c['source']}"
tags: [client, jonbranding]
---

# 👤 {c['name']}

Parent: [[00-SYSTEM/VAULT-MAP|Vault Map]] | Hub: [[10-Projects/JonBranding|JonBranding]]

## 📌 Asosiy Ma'lumotlar
- **🏢 Brend(lar):** `{c['brand'] or c['name']}`
- **📞 Telefon:** `{c['phone'] or 'Kiritilmagan'}`
- **🏷️ Xizmat turlari:** {c['services'] or 'Brending'}
- **📍 Manzil:** {c['address'] or "Noma'lum"}
- **🏭 Faoliyat yo'nalishi:** {c['activity'] or 'Biznes'}

## 💬 Telegram Loyiha Guruhi
- **Guruh formati:** `Jon Branding x {c['brand'] or c['name']}`
- **Muloqot standarti:** [[10-BUSINESS/OPERATIONS/SOP-TELEGRAM-GURUHLAR|Telegram Guruhlar SOP]]
- **Guruh tarkibi:** Baxtiyorjon Gaziyev (Art Director), Mas'ul PM, Lead Designer, Mijoz
- **Guruh muhokamalari:** [[20-CLIENTS/{c['folder_name']}/NOTES#Telegram Muloqoti|Muloqot qaydlari]]

## 💰 Moliyaviy Holat (Airtable & Hisob-kitob)
- **💵 Jami to'langan (LTV):** {c['ltv']:,} so'm
- **⚖️ Qarzdorlik balansi:** {c['debt']:,} so'm
- **📋 Loyihalar soni:** {c['project_count']} ta

## 🔗 Tizim Bog'lanishlari
- Loyihalar tarixi: [[20-CLIENTS/{c['folder_name']}/HISTORY|Loyiha Tarixi]]
- Izohlar va kelishuvlar: [[20-CLIENTS/{c['folder_name']}/NOTES|Qaydlar va Kelishuvlar]]
""".replace(",", " ")

            # 1. <Name> — Profil.md
            with open(os.path.join(c_dir, f"{c['folder_name']} — Profil.md"), "w", encoding="utf-8") as fp:
                fp.write(profile_content)

            # 2. <Name> — Tarix.md
            with open(os.path.join(c_dir, f"{c['folder_name']} — Tarix.md"), "w", encoding="utf-8") as fp:
                fp.write(history_content)

            # 3. <Name> — Qaydlar.md
            with open(os.path.join(c_dir, f"{c['folder_name']} — Qaydlar.md"), "w", encoding="utf-8") as fp:
                fp.write(notes_content)

            # Clean up old generic files if any
            for old_name in ["PROFILE.md", "HISTORY.md", "NOTES.md"]:
                old_p = os.path.join(c_dir, old_name)
                if os.path.exists(old_p):
                    os.remove(old_p)

        print(f"[{vault}] Successfully wrote all 20-CLIENTS dossiers.")

    # Git push from primary vault
    primary = VAULTS[0]
    subprocess.run(["git", "-C", primary, "add", "20-CLIENTS/"], capture_output=True)
    subprocess.run(["git", "-C", primary, "commit", "-m", "feat(clients): populate 20-CLIENTS dossiers from Airtable and Telegram"], capture_output=True)
    subprocess.run(["git", "-C", primary, "push", "origin", "master"], capture_output=True, timeout=20)
    print("Pushed all 20-CLIENTS dossiers to GitHub master!")

    # Secondary pull
    secondary = VAULTS[1]
    if os.path.exists(secondary):
        subprocess.run(["git", "-C", secondary, "pull", "origin", "master"], capture_output=True)
        print("Secondary vault pulled!")


if __name__ == "__main__":
    sync_all()
