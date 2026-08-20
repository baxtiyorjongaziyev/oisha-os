import os
import sys
import time
import json
import subprocess

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

VAULT_PATH = r"C:\Users\baxti\Documents\JonBranding Second Brain"
OBSIDIAN_EXE = r"C:\Users\baxti\AppData\Local\Programs\Obsidian\Obsidian.exe"

print("[*] 1. Obsidian jarayonlarini to'xtatish...")
subprocess.run(["taskkill", "/f", "/im", "Obsidian.exe"], capture_output=True)
time.sleep(1.5)

# Full graph settings with color groups
graph_options = {
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
      "color": {"a": 1, "rgb": 3066993} # Green (#2ecc71)
    },
    {
      "query": "path:20-Areas",
      "color": {"a": 1, "rgb": 10181046} # Purple (#9b59b6)
    },
    {
      "query": "path:60-Wiki/sources/telegram",
      "color": {"a": 1, "rgb": 35020} # Telegram Blue (#0088cc)
    },
    {
      "query": "path:70-Telegram",
      "color": {"a": 1, "rgb": 239604} # Light Cyan (#03a9f4)
    },
    {
      "query": "path:60-Wiki/pages",
      "color": {"a": 1, "rgb": 15105570} # Orange (#e67e22)
    },
    {
      "query": "path:70-Odamlar",
      "color": {"a": 1, "rgb": 15277667} # Pink (#e91e63)
    },
    {
      "query": "path:30-Resources",
      "color": {"a": 1, "rgb": 15844367} # Yellow (#f1c40f)
    },
    {
      "query": "path:50-Daily",
      "color": {"a": 1, "rgb": 8359053} # Slate Grey (#7f8c8d)
    }
  ],
  "collapse-display": False,
  "showArrow": True,
  "textFadeMultiplier": -0.2,
  "nodeSizeMultiplier": 1.3,
  "lineSizeMultiplier": 1.1,
  "collapse-forces": False,
  "centerStrength": 0.4,
  "repelStrength": 16,
  "linkStrength": 0.9,
  "linkDistance": 250,
  "scale": 0.5,
  "close": True
}

# 2. Update graph.json in vault
graph_file = os.path.join(VAULT_PATH, ".obsidian", "graph.json")
with open(graph_file, "w", encoding="utf-8") as f:
    json.dump(graph_options, f, indent=2)
print("[+] Updated .obsidian/graph.json")

# 3. Update workspace.json so the graph leaf has graph_options embedded in its state
ws_file = os.path.join(VAULT_PATH, ".obsidian", "workspace.json")
if os.path.exists(ws_file):
    try:
        with open(ws_file, "r", encoding="utf-8") as f:
            ws_data = json.load(f)
        
        # Inject graph_options into any graph leaf in workspace
        def inject_graph_state(obj):
            if isinstance(obj, dict):
                if obj.get("type") == "graph":
                    obj["state"] = graph_options
                for k, v in obj.items():
                    inject_graph_state(v)
            elif isinstance(obj, list):
                for item in obj:
                    inject_graph_state(item)
                    
        inject_graph_state(ws_data)
        
        with open(ws_file, "w", encoding="utf-8") as f:
            json.dump(ws_data, f, indent=2)
        print("[+] Injected graph color options into .obsidian/workspace.json")
    except Exception as e:
        print(f"[!] Error updating workspace.json: {e}")

# 4. Start Obsidian
print("[*] 4. Obsidian ilovasini ishga tushirish...")
subprocess.Popen([OBSIDIAN_EXE, f"obsidian://open?vault=JonBranding%20Second%20Brain"])
print("[✅] Obsidian muvaffaqiyatli qayta ochildi!")
