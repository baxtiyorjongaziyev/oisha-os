import logging
import asyncio
import inspect
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

from src.agents.agent_tools.crm_actions import CrmActionsMixin
from src.agents.agent_tools.google_actions import GoogleActionsMixin
from src.agents.agent_tools.team_actions import TeamActionsMixin

class AgentToolExecutor(
    CrmActionsMixin,
    GoogleActionsMixin,
    TeamActionsMixin,
):
    """
    AI Agent toollarini bajaruvchi markaziy klass.
    Modulli action mixinlarini birlashtiradi.
    """
    def __init__(self, db, gcontacts, gcalendar, gsheet, amocrm, bot_app, config, gdrive=None):
        self.db = db
        self.gcontacts = gcontacts
        self.gcalendar = gcalendar
        self.gsheet = gsheet
        self.amocrm = amocrm
        self.gdrive = gdrive
        self.bot_app = bot_app  # Telegram Application (bot.send_message uchun)
        self.config = config
        self._scouter = None

    async def execute(
        self,
        function_name: str,
        function_args: dict,
        context_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Gemini chaqirgan tool ni bajarish va natijani qaytarish."""
        logger.info(f"[AGENT TOOL] Executing: {function_name}({function_args})")
        try:
            if function_name == "save_lead_info":
                return await self._save_lead_info(**function_args)
            elif function_name == "create_calendar_event":
                return await self._create_calendar_event(**function_args)
            elif function_name == "save_google_contact":
                return await self._save_google_contact(**function_args)
            elif function_name == "send_stars_invoice":
                return await self._send_stars_invoice(**function_args)
            elif function_name == "forward_to_crm_group":
                return await self._forward_to_crm_group(**function_args)
            elif function_name == "get_user_profile":
                return await self._get_user_profile(**function_args)
            elif function_name == "get_team_members":
                return await self._get_team_members()
            elif function_name == "assign_task_to_human":
                return await self._assign_task_to_human(**function_args)
            elif function_name == "sherlock_user_profile":
                return await self._sherlock_user_profile(**function_args)
            elif function_name == "get_crm_status_tool":
                return await self._get_crm_status_tool(**function_args)
            elif function_name == "update_lead_status":
                return await self._update_lead_status(**function_args)
            elif function_name == "create_followup_task":
                return await self._create_followup_task(**function_args)
            elif function_name == "add_lead_note":
                return await self._add_lead_note(**function_args)
            elif function_name == "qualify_lead":
                return await self._qualify_lead(**function_args)
            elif function_name == "search_local_files":
                return await self._search_local_files(**function_args)
            elif function_name == "google_drive_search":
                return await self._google_drive_search(**function_args)
            elif function_name == "execute_shell_safe":
                return await self._execute_shell_safe(**function_args)
            elif function_name == "search_crm_leads":
                return await self._search_crm_leads(**function_args)
            elif function_name == "get_airtable_projects":
                return await self._get_airtable_projects(**function_args)
            elif function_name == "get_today_stats":
                return await self._get_today_stats()
            else:
                return {"success": False, "error": f"Unknown tool: {function_name}"}
        except Exception as e:
            logger.error(f"[AGENT TOOL ERROR] {function_name}: {e}")
            await self._log_action(
                context_user_id,
                function_name,
                function_args,
                success=False,
                error=str(e),
            )
            return {"success": False, "error": str(e)}

    async def _call_maybe_async(self, fn, *args, **kwargs):
        result = fn(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _db_call(self, method_name: str, *args, **kwargs):
        fn = getattr(self.db, method_name, None)
        if not fn:
            raise AttributeError(f"DB method not available: {method_name}")
        return await self._call_maybe_async(fn, *args, **kwargs)

    async def _resolve_lead_context(
        self,
        *,
        user_id: Optional[int] = None,
        lead_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        user_info: Dict[str, Any] = {}
        phone: Optional[str] = None

        if user_id is not None:
            user_info = await self._db_call("get_user_info", user_id) or {}
            phone = user_info.get("phone")

        lead: Optional[Dict[str, Any]] = None
        resolved_lead_id = lead_id

        if resolved_lead_id is None and phone:
            lead = await asyncio.to_thread(self.amocrm.get_lead_by_phone, phone)
            resolved_lead_id = lead.get("id") if lead else None
        elif resolved_lead_id is not None:
            lead = {"id": resolved_lead_id}
            if hasattr(self.amocrm, "get_lead_phone"):
                try:
                    phone = phone or await asyncio.to_thread(
                        self.amocrm.get_lead_phone, resolved_lead_id
                    )
                except Exception as e:
                    logger.warning(f"[AGENT TOOL] Lead phone resolve error: {e}")

        return {
            "user_info": user_info,
            "phone": phone,
            "lead": lead,
            "lead_id": resolved_lead_id,
        }
