import os

VAULT_DIR = r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault"
PAGES_DIR = os.path.join(VAULT_DIR, "60-Wiki", "pages")
os.makedirs(PAGES_DIR, exist_ok=True)

PROJECT_PAGES = [
    {
        "filename": "Kamila Pardalari.md",
        "title": "Kamila Pardalari",
        "type": "entity",
        "client": "Kamila Pardalari",
        "service": "Tovar Belgisi (Patent) & Logotip Dizayni",
        "person": "[[Hasanboy Gaziyev]]",
        "status": "Davlat ekspertizasida (7 oy muddat)",
        "summary": "Pardalar va to'qimachilik brendi. Tovar belgisi bo'yicha 1-davlat boji to'langan va rasmiy ekspertiza boshlangan. Qo'shimcha ravishda Logotip ishlab chiqish bo'yicha sotuv olib borilmoqda."
    },
    {
        "filename": "Ledir.md",
        "title": "Ledir",
        "type": "entity",
        "client": "Ledir",
        "service": "Naming & Vizual Konsepsiya",
        "person": "[[Hasanboy Gaziyev]]",
        "status": "Domen va nom band qilinmoqda",
        "summary": "Yangi brend nomi va konsepsiyasi. Jamoa bilan variantlar saralanib, eng ma'qul 2 ta nom tanlangan va ijtimoiy tarmoqlarda unvon/domen band qilinmoqda."
    },
    {
        "filename": "Beyaz.md",
        "title": "Beyaz",
        "type": "entity",
        "client": "Beyaz",
        "service": "Vizual Identika & Dizayn",
        "person": "[[Inomjon]]",
        "status": "Dizayn to'lovi amalga oshirilgan (1 000 000 UZS)",
        "summary": "Vizual dizayn va brending loyihasi. Dizaynerlik xizmat haqi to'langan."
    },
    {
        "filename": "Shirona.md",
        "title": "Shirona",
        "type": "entity",
        "client": "Shirona",
        "service": "Brending & Naming",
        "person": "[[Asadulloh]]",
        "status": "Yakunlash bosqichida",
        "summary": "Brending loyihasi. Dizayn va vizual elementlar ishlab chiqilgan."
    },
    {
        "filename": "Sadiya Cakes.md",
        "title": "Sadiya Cakes",
        "type": "entity",
        "client": "Saltanat opa",
        "service": "Logotip & Qadoq",
        "person": "[[Shahnoza]]",
        "status": "Muzokaralar bosqichida",
        "summary": "Qandolatchilik brendi. Logotip va qadoqlash bo'yicha dastlabki so'rov olingan."
    }
]

for p in PROJECT_PAGES:
    path = os.path.join(PAGES_DIR, p["filename"])
    content = f"""---
title: {p['title']}
type: entity
status: active
tags:
  - client/project
  - jonbranding
sources:
  - "[[60-Wiki/sources/telegram/2026-08-11_to_2026-08-20_Jon-Branding-Ecosystem]]"
  - "[[pages/JonBranding Client and Project Registry]]"
---

# {p['title']}

**Mijoz / Mas'ul:** {p['client']} · {p['person']}  
**Xizmat turi:** {p['service']}  
**Joriy status:** {p['status']}  

## Loyiha Mazmuni
{p['summary']}

## Bog'lanishlar
- Markaz: [[JonBranding]]
- Reestr: [[pages/JonBranding Client and Project Registry|Client Registry]]
- Telegram manba: [[60-Wiki/sources/telegram/2026-08-11_to_2026-08-20_Jon-Branding-Ecosystem|Telegram Ekotizimi]]
- Mas'ul: {p['person']}
- Dizayn guruhi: [[pages/Tez Dizayn Scrum|Tez Dizayn]]
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[+] Created {p['filename']}")
