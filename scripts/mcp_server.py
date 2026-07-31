"""Eskirgan: `scripts/oisha_mcp_server.py` ga birlashtirildi.

AmoCRM / Airtable / Instagram toollari endi yagona `oisha` MCP serverida,
Telegram toollari bilan birga. Bu fayl mavjud konfiguratsiyalar buzilmasligi
uchun yo'naltiruvchi sifatida qoldirilgan.
"""

import os
import runpy
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    print(
        "[DEPRECATED] scripts/mcp_server.py -> scripts/oisha_mcp_server.py",
        file=sys.stderr,
    )
    runpy.run_path(
        os.path.join(_SCRIPT_DIR, "oisha_mcp_server.py"), run_name="__main__"
    )
