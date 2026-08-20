import os
import json

VAULTS = [
    r"C:\Users\baxti\Documents\JonBranding Second Brain",
    r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault"
]

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
      "color": {"a": 1, "rgb": 15277667} # Pink/Red (#e91e63)
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
  "nodeSizeMultiplier": 1.25,
  "lineSizeMultiplier": 1.0,
  "collapse-forces": False,
  "centerStrength": 0.38,
  "repelStrength": 16,
  "linkStrength": 0.9,
  "linkDistance": 260,
  "scale": 0.45,
  "close": True
}

for v in VAULTS:
    if os.path.exists(v):
        g_path = os.path.join(v, ".obsidian", "graph.json")
        with open(g_path, "w", encoding="utf-8") as f:
            json.dump(graph_config, f, indent=2)
        print(f"[+] Updated graph.json in {v}")
