import re
import os

files = [
    r"c:\Users\baxti\playground\oisha-os\src\agents\ai_router.py",
    r"c:\Users\baxti\playground\oisha-os\src\agents\autonomous_sales_agent.py",
    r"c:\Users\baxti\playground\oisha-os\src\agents\deal_lifecycle_manager.py",
    r"c:\Users\baxti\playground\oisha-os\src\agents\surgical_negotiator.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\ai\conversation_engine.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\agent_orchestrator.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\apollo_enrich.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\auto_task_creator.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\client_project_checklist.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\daily_enforcer.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\docusign_sync.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\hisobchi_handlers.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\mandatory_workflow.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\project_phases.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\salescoach_sync.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\service_configurator.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\smart_task_creator.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\tool_adapters.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\core\workflow_telegram_bot.py",
    r"c:\Users\baxti\playground\oisha-os\src\services\utils\free_ai_router.py"
]

migrated_files = []

for fp in files:
    with open(fp, "r", encoding="utf-8") as f:
        content = f.read()

    global_regex = re.compile(r"^[ \t]*global\s+(_[a-zA-Z0-9_,\s]+)(?:\n|;)", re.MULTILINE)
    
    matches = global_regex.findall(content)
    if not matches:
        continue
        
    vars_to_replace = []
    for match in matches:
        vs = [v.strip() for v in match.split(',')]
        for v in vs:
            if v.startswith("_"):
                vars_to_replace.append(v)
                
    vars_to_replace = list(set(vars_to_replace))
    if not vars_to_replace:
        continue
        
    content = global_regex.sub("", content)
    
    for var in vars_to_replace:
        prop_name = var[1:]
        var_regex = re.compile(r"\b" + re.escape(var) + r"\b")
        content = var_regex.sub(f"app_ctx.{prop_name}", content)
        
    if "from src.context import app_ctx" not in content:
        if "from __future__ import annotations" in content:
            content = content.replace("from __future__ import annotations\n", "from __future__ import annotations\nfrom src.context import app_ctx\n", 1)
        else:
            first_import = re.search(r"^(?:import|from) ", content, re.MULTILINE)
            if first_import:
                idx = first_import.start()
                content = content[:idx] + "from src.context import app_ctx\n" + content[idx:]
            else:
                content = "from src.context import app_ctx\n" + content
                
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)
    migrated_files.append(fp)

print("Migrated files:")
for mf in migrated_files:
    print(mf)
