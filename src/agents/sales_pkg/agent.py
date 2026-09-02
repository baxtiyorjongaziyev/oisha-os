"""
SalesAgent core agent implementation.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from src.agents.core import BaseAgent
from src.agents.negotiation_engine import NegotiationEngine
from src.agents.negotiation_verifier import NegotiationOutcomeVerifier
from src.agents.persona_router import PersonaRouter
from src.agents.sales_pkg.actions import SalesActionsMixin

logger = logging.getLogger(__name__)


class SalesAgent(BaseAgent, SalesActionsMixin):
    """Autonomous negotiation-capable sales agent."""

    def __init__(
        self,
        agent_id: str,
        system_prompt: str,
        api_keys: Dict[str, str],
        executor: Optional[Any] = None,
        db: Optional[Any] = None,
    ):
        super().__init__(agent_id, system_prompt, api_keys, executor, db)
        self.products = self._load_products()
        self.verifier = NegotiationOutcomeVerifier()

    def _load_products(self) -> Dict[str, Any]:
        path = os.path.join("data", "agency_products.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[SALES_AGENT] Failed to load products: {e}")
        return {}

    async def _get_negotiation_mode(self) -> str:
        return "autonomous"

    async def call_ai_with_fallback(self, prompt: str, **kwargs) -> str:
        from src.services.utils.gemini_fallback import generate_content_with_fallback
        return await generate_content_with_fallback(
            prompt=prompt,
            model="gemini-1.5-flash",
            temperature=0.7,
        )

    async def load_session_history(self, user_id: int):
        pass

    def get_session_history(self, user_id: int):
        return []

    async def _log_assessment(
        self,
        assessment,
        user_id: Optional[int],
        lead_id: Optional[int],
        task_description: str,
    ) -> None:
        if not self.db:
            return
        try:
            await self.db.execute_write(
                """
                INSERT INTO negotiation_logs (
                    user_id, lead_id, stage, intent, objection,
                    close_prob, mode, context, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    user_id,
                    lead_id,
                    assessment.stage,
                    assessment.intent,
                    assessment.objection,
                    assessment.close_probability,
                    assessment.autonomy_mode,
                    task_description[:500],
                ),
            )
        except Exception as exc:
            logger.debug("[SALES_AGENT] Failed to log assessment: %s", exc)

    async def process_task(
        self,
        task_or_user_id: Any,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if isinstance(task_or_user_id, int):
            user_id = task_or_user_id
            task_description = user_message or ""
            ctx = context or {}
            is_direct_chat = True
        else:
            task_description = str(task_or_user_id)
            ctx = context if isinstance(context, dict) else (user_message if isinstance(user_message, dict) else {})
            user_id = ctx.get("user_id")
            is_direct_chat = False

        lead_id = ctx.get("lead_id")
        phone = ctx.get("phone")
        name = ctx.get("name")

        assessment = await NegotiationEngine.assess_async(
            task_description,
            crm_status=ctx.get("crm_status", ""),
        )

        await self._log_assessment(assessment, user_id, lead_id, task_description)

        esc_reason = self._detect_escalation(task_description, assessment)
        if esc_reason:
            logger.warning("[SALES_AGENT] Escalating to human: %s", esc_reason)
            return (
                "Xabaringizni qabul qildik, tez orada mas'ul xodimimiz siz bilan bog'lanadi."
                if is_direct_chat
                else {
                    "response": "Xabaringizni qabul qildik, tez orada mas'ul xodimimiz siz bilan bog'lanadi.",
                    "escalated": True,
                    "escalation_reason": esc_reason,
                    "assessment": assessment.to_payload(),
                }
            )

        meeting_window = self._extract_meeting_window(task_description)
        if meeting_window and user_id:
            await self._sync_meeting_state(user_id, meeting_window)

        persona = PersonaRouter.select_persona(assessment)
        prompt = PersonaRouter.build_system_prompt(persona, assessment)

        try:
            ai_reply = await self.call_ai_with_fallback(
                prompt=f"{prompt}\n\nMijoz: {task_description}",
            )
        except Exception as e:
            logger.error(f"[SALES_AGENT] AI reply generation failed: {e}")
            ai_reply = self._fallback_reply(assessment, task_description)

        action_plan = await self._build_action_plan(
            assessment=assessment,
            task_description=task_description,
            user_id=user_id,
            lead_id=lead_id,
            phone=phone,
            name=name,
            persona=persona,
            meeting_window=meeting_window,
            ai_reply=ai_reply,
        )

        execution_results = await self._execute_actions(action_plan)

        if self.db and hasattr(self.db, "log_agent_action"):
            await self.db.log_agent_action(self.agent_id, "reply", {"user_id": user_id, "reply": ai_reply})

        if is_direct_chat:
            return ai_reply

        return {
            "response": ai_reply,
            "assessment": assessment.to_payload(),
            "actions": action_plan,
            "execution_results": execution_results,
            "persona": persona,
        }
