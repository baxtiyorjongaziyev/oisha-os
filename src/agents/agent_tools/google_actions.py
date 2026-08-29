import os
import io
import time
import json
import logging
import asyncio
import inspect
from datetime import datetime
from typing import Any, Optional, Dict, List, Tuple
from src.agents.agent_tools.declarations import TOOL_DECLARATIONS

logger = logging.getLogger(__name__)

class GoogleActionsMixin:
    async def _create_calendar_event(
        self,
        summary: str,
        start_time: str,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Google Calendar da tadbir yaratish."""
        import asyncio

        # Tugash vaqti yo'q bo'lsa, 1 soat qo'shish
        if not end_time:
            try:
                start_dt = datetime.datetime.fromisoformat(start_time)
                end_time = (start_dt + datetime.timedelta(hours=1)).isoformat()
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)
                end_time = start_time

        try:
            result = await asyncio.to_thread(
                self.gcalendar.create_event,
                summary=summary,
                start_time=start_time,
                end_time=end_time,
                description=description or "",
            )
            await self._log_action(
                None,
                "create_calendar_event",
                {"summary": summary, "start_time": start_time},
                success=True,
            )
            return {
                "success": True,
                "message": f"Tadbir yaratildi: '{summary}' — {start_time}",
                "event": result,
            }
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"success": False, "error": str(e)}

    async def _save_google_contact(
        self, name: str, phone: str, note: Optional[str] = None
    ) -> Dict[str, Any]:
        """Google Contacts ga kontakt saqlash."""
        import asyncio

        try:
            await asyncio.to_thread(
                self.gcontacts.create_contact,
                first_name=name,
                phone=phone,
                note=note or "Telegram orqali — AI Agent tomonidan saqlandi",
            )
            await self._log_action(
                None,
                "save_google_contact",
                {"name": name, "phone": phone},
                success=True,
            )
            return {
                "success": True,
                "message": f"Google Contacts ga saqlandi: {name} ({phone})",
            }
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"success": False, "error": str(e)}

    async def _search_local_files(
        self, query: str, extension: Optional[str] = None
    ) -> Dict[str, Any]:
        """Lokal fayl tizimidan qidirish."""
        import os
        import glob

        results = []
        search_pattern = f"**/*{query}*"
        if extension:
            search_pattern += (
                extension if extension.startswith(".") else f".{extension}"
            )

        # Xavfsiz qidirish uchun loyiha papkasidan boshlaymiz
        try:
            for file in glob.glob(search_pattern, recursive=True):
                if os.path.isfile(file):
                    results.append(
                        {"name": os.path.basename(file), "path": os.path.abspath(file)}
                    )
                if len(results) > 5:
                    break  # Max 5 result

            return {"success": True, "files": results, "count": len(results)}
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"success": False, "error": str(e)}

    async def _google_drive_search(self, query: str) -> Dict[str, Any]:
        """Google Drive API orqali qidirish."""
        if not self.gdrive:
            return {"success": False, "error": "Google Drive xizmati ulanmagan."}
        try:
            files = await asyncio.to_thread(
                self.gdrive.search_files, query
            )
            return {"success": True, "files": files}
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"success": False, "error": f"Google Drive xatosi: {e}"}

    async def _execute_shell_safe(self, command: str) -> Dict[str, Any]:
        """Faqat ma'lum (whitelist) buyruqlarni bajarish — shell=False bilan RCE dan himoya."""
        import shlex
        import subprocess

        safe_map = {
            "uptime": ["uptime"],
            "df": ["df", "-h"],
            "free": ["free", "-m"],
            "ls": ["ls", "-la"],
            "date": ["date"],
            "dir": ["cmd", "/c", "dir"],
        }

        parts = shlex.split(command)
        if not parts:
            return {"success": False, "error": "Bo'sh buyruq."}

        base_cmd = parts[0]
        if base_cmd not in safe_map:
            return {
                "success": False,
                "error": "Xavfsizlik! Bu buyruqni bajarishga ruxsat yo'q.",
            }

        try:
            result = subprocess.check_output(
                safe_map[base_cmd], shell=False, stderr=subprocess.STDOUT
            ).decode(errors="replace")
            return {"success": True, "output": result}
        except Exception as e:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            return {"success": False, "error": str(e)}
