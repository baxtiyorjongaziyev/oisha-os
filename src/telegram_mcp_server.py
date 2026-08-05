"""`python -m src.telegram_mcp_server` uchun shim.

Telegram toollari `oisha` MCP serveriga birlashtirildi — bu yerda ham
o'sha server ishga tushadi.
"""

import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_root, "scripts"))

from oisha_mcp_server import mcp

if __name__ == "__main__":
    mcp.run()
