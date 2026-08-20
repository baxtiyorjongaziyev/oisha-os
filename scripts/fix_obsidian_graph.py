import os
import json

VAULT_DIR = r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault"

# 1. Configure .obsidian/graph.json with proper colors and settings
graph_config = {
  "collapse-filter": False,
  "search": "",
  "showTags": True,
  "showAttachments": False,
  "hideUnresolved": False,
  "showOrphans": True,
  "collapse-color-groups": False,
  "colorGroups": [
    {
      "query": "path:10-Projects",
      "color": {"a": 1, "rgb": 4443984} # Green (#43D150)
    },
    {
      "query": "path:20-Areas",
      "color": {"a": 1, "rgb": 10565887} # Purple (#A136FF)
    },
    {
      "query": "path:60-Wiki/sources/telegram",
      "color": {"a": 1, "rgb": 2542079} # Cyan / Telegram Blue (#26C9FF)
    },
    {
      "query": "path:60-Wiki/pages",
      "color": {"a": 1, "rgb": 16750848} # Orange (#FFA700)
    },
    {
      "query": "path:70-Odamlar",
      "color": {"a": 1, "rgb": 16728464} # Pink (#FF3790)
    },
    {
      "query": "path:30-Resources",
      "color": {"a": 1, "rgb": 3394815} # Blue (#33CDFF)
    },
    {
      "query": "path:50-Daily",
      "color": {"a": 1, "rgb": 9868950} # Grey (#969696)
    }
  ],
  "collapse-display": False,
  "showArrow": True,
  "textFadeMultiplier": 0,
  "nodeSizeMultiplier": 1.25,
  "lineSizeMultiplier": 1.2,
  "collapse-forces": False,
  "centerStrength": 0.52,
  "repelStrength": 12,
  "linkStrength": 1,
  "linkDistance": 220,
  "scale": 0.5,
  "close": True
}

graph_path = os.path.join(VAULT_DIR, ".obsidian", "graph.json")
with open(graph_path, "w", encoding="utf-8") as f:
    json.dump(graph_config, f, indent=2)
print("[+] Updated .obsidian/graph.json with rich color groups and showOrphans: true")

# 2. Create People entity notes in 70-Odamlar/ so they connect directly in the Graph
PEOPLE = [
    {
        "filename": "Shahnoza.md",
        "name": "Shahnoza",
        "role": "Business Assistant & Closer",
        "team": "Jon Branding Team",
        "scope": "Sotuvlar, lidlar bilan aloqa, uchrashuvlar belgilash, mijozlar follow-up"
    },
    {
        "filename": "Ifora.md",
        "name": "Ifora",
        "role": "Project Manager & Quality Controller",
        "team": "Jon Branding Team",
        "scope": "Loyiha muddatlari, topshiriqlar nazorati, jamoa boshqaruvi"
    },
    {
        "filename": "Inomjon.md",
        "name": "Inomjon",
        "role": "Production Manager & Designer",
        "team": "Jon Branding Team / Tez Dizayn",
        "scope": "Dizayn maketlarini topshirish, mijozga yuborish, naming va bannerlar"
    },
    {
        "filename": "Asadulloh.md",
        "name": "Asadulloh",
        "role": "Lead Graphic Designer",
        "team": "Tez Dizayn",
        "scope": "Tezkor dizayn sprintlari, logotip va banner ishlab chiqish"
    },
    {
        "filename": "Hasanboy Gaziyev.md",
        "name": "Hasanboy Gaziyev",
        "role": "Patent & Trademark Expert",
        "team": "Patent Hamkor",
        "scope": "Tovar belgilari, patent ekspertizasi, brend himoyasi (Kamila Pardalari, Ledir)"
    },
    {
        "filename": "Zuhriddin.md",
        "name": "Zuhriddin",
        "role": "AI Automation & Smartcall Partner",
        "team": "Smartcall",
        "scope": "Ovozli robotlar, Telegram CRM botlari, avtomatlashtirish"
    }
]

people_dir = os.path.join(VAULT_DIR, "70-Odamlar")
os.makedirs(people_dir, exist_ok=True)

for p in PEOPLE:
    p_path = os.path.join(people_dir, p["filename"])
    content = f"""---
title: {p['name']}
type: person
status: active
team: {p['team']}
role: {p['role']}
tags:
  - odamlar
  - team
sources:
  - "[[60-Wiki/sources/telegram/2026-08-11_to_2026-08-20_Jon-Branding-Ecosystem]]"
---

# {p['name']}

**Roli:** {p['role']}  
**Jamoa:** [[JonBranding|{p['team']}]]  
**Faoliyat sohasi:** {p['scope']}  

## Bog'langan Loyihalar va Chatlar
- [[60-Wiki/sources/telegram/2026-08-11_to_2026-08-20_Jon-Branding-Ecosystem|Telegram Ekotizimi]]
- [[pages/JonBranding Client and Project Registry|Mijozlar Reestri]]
- [[20-Areas/Jamoa va PM|Jamoa va PM]]
"""
    with open(p_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[+] Created/Updated 70-Odamlar/{p['filename']}")
