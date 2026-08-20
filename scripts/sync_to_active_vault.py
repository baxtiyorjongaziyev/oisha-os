import os
import shutil
import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SRC_VAULT = r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault"
DEST_VAULT = r"C:\Users\baxti\Documents\JonBranding Second Brain"

print(f"[*] Syncing from:\n    {SRC_VAULT}\n  to:\n    {DEST_VAULT}")

# Copy all markdown files and directories recursively
for root, dirs, files in os.walk(SRC_VAULT):
    # skip .obsidian, .git, and .trash
    rel_path = os.path.relpath(root, SRC_VAULT)
    if rel_path.startswith(".obsidian") or rel_path.startswith(".git") or rel_path.startswith(".trash"):
        continue
    
    dest_dir = os.path.join(DEST_VAULT, rel_path)
    os.makedirs(dest_dir, exist_ok=True)
    
    for f in files:
        if f.startswith("."):
            continue
        src_file = os.path.join(root, f)
        dest_file = os.path.join(dest_dir, f)
        
        # copy if newer or missing
        if not os.path.exists(dest_file) or os.path.getmtime(src_file) > os.path.getmtime(dest_file):
            shutil.copy2(src_file, dest_file)
            print(f"  [+] Copied {os.path.join(rel_path, f)}")

# Configure graph.json in DEST_VAULT
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
      "query": "path:70-Telegram",
      "color": {"a": 1, "rgb": 2542079} # Cyan / Telegram (#26C9FF)
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
  "nodeSizeMultiplier": 1.3,
  "lineSizeMultiplier": 1.2,
  "collapse-forces": False,
  "centerStrength": 0.52,
  "repelStrength": 12,
  "linkStrength": 1,
  "linkDistance": 220,
  "scale": 0.5,
  "close": True
}

dest_graph_path = os.path.join(DEST_VAULT, ".obsidian", "graph.json")
with open(dest_graph_path, "w", encoding="utf-8") as f:
    json.dump(graph_config, f, indent=2)
print("[+] Updated graph.json in active JonBranding Second Brain vault!")

# Also ensure 70-Telegram/00 Telegram Miya.md links to all telegram sources and project pages
telegram_miya_path = os.path.join(DEST_VAULT, "70-Telegram", "00 Telegram Miya.md")
with open(telegram_miya_path, "w", encoding="utf-8") as f:
    f.write("""---
title: Telegram Miya
type: synthesis
status: active
tags:
  - telegram
  - second-brain
  - business
sources:
  - "[[60-Wiki/pages/Telegram Business Knowledge Pipeline]]"
  - "[[60-Wiki/sources/telegram/README]]"
  - "[[60-Wiki/sources/telegram/2026-08-11_to_2026-08-20_Jon-Branding-Ecosystem]]"
updated: 2026-08-20
confidence: verified-live
---

# Telegram Miya

Parent: [[10-Projects/Second Brain Integration|Second Brain Integration]] · Hub: [[JonBranding]] · Index: [[60-Wiki/index|Wiki Index]]

## Telegram Knowledge Network

### 🗂 Asosiy Manbalar va Sintezlar
- [[60-Wiki/sources/telegram/2026-08-11_to_2026-08-20_Jon-Branding-Ecosystem|2 yillik Telegram Ekotizimi (2024–2026)]]
- [[60-Wiki/pages/JonBranding Client and Project Registry|Mijozlar va Loyihalar Reestri]]
- [[60-Wiki/pages/Tez Dizayn Scrum|Tez Dizayn Konveyeri]]
- [[60-Wiki/pages/Telegram Business Knowledge Pipeline|Telegram Pipeline]]

### 👥 Jamoa va Mas'ullar
- [[70-Odamlar/Shahnoza|Shahnoza (Business Assistant & Closer)]]
- [[70-Odamlar/Ifora|Ifora (Project Manager & Quality)]]
- [[70-Odamlar/Inomjon|Inomjon (Production Manager & Designer)]]
- [[70-Odamlar/Asadulloh|Asadulloh (Lead Graphic Designer)]]
- [[70-Odamlar/Hasanboy Gaziyev|Hasanboy Gaziyev (Patent Hamkor)]]
- [[70-Odamlar/Zuhriddin|Zuhriddin (Smartcall & Automation)]]

### 🏷 Mijoz Loyihalari
- [[60-Wiki/pages/Kamila Pardalari|Kamila Pardalari (Patent & Logo)]]
- [[60-Wiki/pages/Ledir|Ledir (Naming & Brand)]]
- [[60-Wiki/pages/Beyaz|Beyaz (Vizual Dizayn)]]
- [[60-Wiki/pages/Shirona|Shirona (Brending)]]
- [[60-Wiki/pages/Sadiya Cakes|Sadiya Cakes (Logo)]]
""")
print("[+] Updated 70-Telegram/00 Telegram Miya.md with rich connections!")
