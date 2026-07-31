"""Eskirgan: `scripts/oisha_mcp_server.py` ga birlashtirildi.

Ilgari Telegram va AmoCRM toollari uchun alohida MCP serverlar bor edi.
Endi bittasi — `oisha` — ikkalasini ham beradi.

Bu fayl mavjud MCP konfiguratsiyalari (Claude Desktop, Oracle'dagi eski
yozuvlar) darrov buzilmasligi uchun qoldirilgan va yangi serverga
yo'naltiradi. Yangi sozlamalarda to'g'ridan-to'g'ri oisha_mcp_server.py
ishlatilsin.
"""

import os
import runpy
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    print(
        "[DEPRECATED] scripts/telegram_mcp_server.py -> scripts/oisha_mcp_server.py",
        file=sys.stderr,
    )
    runpy.run_path(
        os.path.join(_SCRIPT_DIR, "oisha_mcp_server.py"), run_name="__main__"
    )
