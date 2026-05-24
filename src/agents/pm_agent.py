import logging
from typing import Any, Dict, Optional

from .core import BaseAgent

logger = logging.getLogger(__name__)

_STAGE_KEYWORDS = {
    "boshlandi": "in_progress",
    "tugadi": "done",
    "to'xtatildi": "on_hold",
    "bekor": "cancelled",
    "tayyor": "done",
    "jarayonda": "in_progress",
    "kutilmoqda": "pending",
}


class PMAgent(BaseAgent):
    """Project Manager agent — responds to team + updates Airtable/CRM when keywords detected."""

    def __init__(
        self,
        agent_id: str,
        system_prompt: str,
        api_keys: Dict[str, str],
        executor: Optional[Any] = None,
        db: Optional[Any] = None,
    ):
        super().__init__(agent_id, system_prompt, api_keys, executor, db)
        self.team_system_prompt = (
            "Siz JonBranding agentligining Project Manager assistentisiz.\n"
            "Vazifalar: topshiriqlar nazorati, muddatlar kuzatuvi, jamoa muloqoti.\n"
            "Uslub: professional, qat'iy, 'siz/aka/opa' bilan murojaat."
        )

    async def process_task(
        self,
        user_id: int,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        await self.load_session_history(user_id)
        self.update_history(user_id, "user", task_description)

        is_team = context and context.get("role") == "Jamoa"
        extra = (
            "\n\n[MISSION: PM] Jamoaga yordam bering, muddatlarni kuzating."
            if is_team
            else ""
        )

        history = self.get_session_history(user_id)
        contents = [
            {
                "role": "user" if t["role"] == "user" else "model",
                "parts": [{"text": t["content"]}],
            }
            for t in history
        ]

        original = self.system_prompt
        self.system_prompt = original + extra
        reply = await self.call_ai_with_fallback(contents, user_id)
        self.system_prompt = original

        # --- Real tool execution ---
        await self._try_airtable_update(task_description, context)
        await self._try_crm_note(user_id, task_description, reply, context)

        self.update_history(user_id, "assistant", reply)
        return reply

    async def _try_airtable_update(
        self, text: str, context: Optional[Dict]
    ) -> None:
        if not self.executor:
            return
        detected_stage = None
        lower = text.lower()
        for keyword, stage in _STAGE_KEYWORDS.items():
            if keyword in lower:
                detected_stage = stage
                break
        if not detected_stage:
            return

        record_id = (context or {}).get("airtable_record_id")
        if not record_id:
            return

        try:
            result = await self.executor.execute(
                "airtable.update_stage",
                {"record_id": record_id, "stage": detected_stage},
                context_user_id=0,
            )
            logger.info(f"[PM] Airtable updated: {result}")
        except Exception as e:
            logger.warning(f"[PM] Airtable update skipped: {e}")

    async def _try_crm_note(
        self,
        user_id: int,
        task_text: str,
        reply: str,
        context: Optional[Dict],
    ) -> None:
        if not self.executor:
            return
        lead_id = (context or {}).get("crm_lead_id")
        if not lead_id:
            return

        note = f"[PM Update] {task_text[:200]}"
        try:
            result = await self.executor.execute(
                "amocrm.add_lead_note",
                {"lead_id": lead_id, "text": note},
                context_user_id=user_id,
            )
            logger.info(f"[PM] CRM note added: {result}")
        except Exception as e:
            logger.warning(f"[PM] CRM note skipped: {e}")
