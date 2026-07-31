"""`python -m src.telegram_mcp_server` uchun shim.

Telegram toollari `oisha` MCP serveriga birlashtirildi — bu yerda ham
o'sha server ishga tushadi.
"""

import os
import runpy
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
real_script = os.path.join(project_root, "scripts", "oisha_mcp_server.py")

# exec() ishlatmaymiz (bandit B102).
sys.path.insert(0, os.path.join(project_root, "scripts"))
runpy.run_path(real_script, run_name="__main__")
