import os
import json
import shutil
import sys

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    python_exe = os.path.join(project_root, ".venv", "Scripts", "python.exe")
    
    if not os.path.exists(python_exe):
        print(f"[ERROR] Python virtual environment executable not found at {python_exe}")
        print("Please ensure you have run your virtual environment setup.")
        sys.exit(1)
        
    print(f"[INFO] Found project root: {project_root}")
    print(f"[INFO] Found Python executable: {python_exe}")
    
    # Define our MCP server definitions with absolute paths
    mcp_servers = {
        "oisha-amocrm": {
            "command": python_exe,
            "args": [
                "-X",
                "utf8",
                "-m",
                "src.mcp_server"
            ],
            "env": {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1"
            },
            "cwd": project_root
        },
        "oisha-telegram": {
            "command": python_exe,
            "args": [
                "-X",
                "utf8",
                "-m",
                "src.telegram_mcp_server"
            ],
            "env": {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1"
            },
            "cwd": project_root
        }
    }
    
    appdata = os.environ.get("APPDATA")
    if not appdata:
        print("[ERROR] APPDATA environment variable not found.")
        sys.exit(1)
        
    targets = [
        {
            "name": "Claude Desktop",
            "path": os.path.join(appdata, "Claude", "claude_desktop_config.json"),
            "key": "mcpServers"
        },
        {
            "name": "ChatGPT Desktop",
            "path": os.path.join(appdata, "ChatGPT", "config.json"),
            "key": "mcpServers"
        }
    ]
    
    for target in targets:
        name = target["name"]
        config_path = target["path"]
        key = target["key"]
        
        config_dir = os.path.dirname(config_path)
        if not os.path.exists(config_dir):
            print(f"[WARNING] Directory for {name} does not exist: {config_dir}. Skipping.")
            continue
            
        print(f"\n[CONFIG] Configuring {name} at {config_path}...")
        
        # Load existing config or create new one
        config_data = {}
        if os.path.exists(config_path):
            try:
                # Backup
                backup_path = config_path + ".bak"
                shutil.copy2(config_path, backup_path)
                print(f"  [BACKUP] Created backup: {backup_path}")
                
                with open(config_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        config_data = json.loads(content)
            except Exception as e:
                print(f"  [ERROR] Error reading config file: {e}. Starting fresh.")
                config_data = {}
                
        # Inject MCP servers
        if key not in config_data:
            config_data[key] = {}
            
        for s_name, s_def in mcp_servers.items():
            config_data[key][s_name] = s_def
            print(f"  [OK] Registered server: {s_name}")
            
        # Write back
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            print(f"  [SUCCESS] Successfully configured {name}!")
        except Exception as e:
            print(f"  [ERROR] Failed to write config file for {name}: {e}")

if __name__ == "__main__":
    main()
