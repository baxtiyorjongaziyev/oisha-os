import os
import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

VAULTS = [
    r"C:\Users\baxti\Documents\JonBranding Second Brain",
    r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault"
]

# Premium, clean, uncluttered graph configuration
clean_graph_config = {
  "collapse-filter": True,
  "search": "-path:90-AI/archive -path:40-Archive", # Exclude archive clutter
  "showTags": False,           # Turn off tag clutter
  "showAttachments": False,    # Turn off attachments clutter
  "hideUnresolved": True,      # Hide dead/broken links (cleans up 50% of the mess!)
  "showOrphans": False,        # Hide floating disconnected scratch notes
  "collapse-color-groups": False,
  "colorGroups": [
    {
      "query": "path:10-Projects",
      "color": {"a": 1, "rgb": 1096065} # Emerald Green (#10B981)
    },
    {
      "query": "path:20-Areas",
      "color": {"a": 1, "rgb": 9133302} # Purple (#8B5CF6)
    },
    {
      "query": "path:60-Wiki/sources/telegram",
      "color": {"a": 1, "rgb": 960233} # Telegram Blue (#0EA5E9)
    },
    {
      "query": "path:70-Telegram",
      "color": {"a": 1, "rgb": 960233} # Telegram Blue (#0EA5E9)
    },
    {
      "query": "path:60-Wiki/pages",
      "color": {"a": 1, "rgb": 16096779} # Amber Gold (#F59E0B)
    },
    {
      "query": "path:70-Odamlar",
      "color": {"a": 1, "rgb": 15485081} # Rose Pink (#EC4899)
    },
    {
      "query": "path:30-Resources",
      "color": {"a": 1, "rgb": 6514417} # Indigo (#6366F1)
    }
  ],
  "collapse-display": True,
  "showArrow": False,          # Disabling arrows eliminates arrow-head clutter
  "textFadeMultiplier": 1.2,   # Text shows smoothly on hover/zoom (no overlapping text wall!)
  "nodeSizeMultiplier": 0.95,  # Elegant, clean node dots
  "lineSizeMultiplier": 0.6,   # Thin, refined lines
  "collapse-forces": True,
  "centerStrength": 0.28,      # Gentle center gravity (no tight clump)
  "repelStrength": 18,         # High repulsion (nodes breathe and spread out gracefully)
  "linkStrength": 0.8,
  "linkDistance": 280,         # Wide connections for distinct spatial clusters
  "scale": 0.6,
  "close": True
}

for v in VAULTS:
    if os.path.exists(v):
        g_path = os.path.join(v, ".obsidian", "graph.json")
        with open(g_path, "w", encoding="utf-8") as f:
            json.dump(clean_graph_config, f, indent=2)
            
        ws_path = os.path.join(v, ".obsidian", "workspace.json")
        if os.path.exists(ws_path):
            try:
                with open(ws_path, "r", encoding="utf-8") as f:
                    ws_data = json.load(f)
                
                def inject(obj):
                    if isinstance(obj, dict):
                        if obj.get("type") == "graph":
                            obj["state"] = clean_graph_config
                        for k, val in obj.items():
                            inject(val)
                    elif isinstance(obj, list):
                        for item in obj:
                            inject(item)
                            
                inject(ws_data)
                with open(ws_path, "w", encoding="utf-8") as f:
                    json.dump(ws_data, f, indent=2)
            except Exception as e:
                pass
        print(f"[+] Beautified graph in: {v}")
