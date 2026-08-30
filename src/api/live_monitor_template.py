"""
HTML Dashboard template loader for Live Monitor.
"""
from pathlib import Path

_HTML_PATH = Path(__file__).parent / "templates" / "dashboard.html"
DASHBOARD_HTML = _HTML_PATH.read_text(encoding="utf-8") if _HTML_PATH.exists() else ""
