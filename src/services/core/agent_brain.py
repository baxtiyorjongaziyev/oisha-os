"""
OishaBrain — LLM-powered failure diagnostics and self-improvement.

Fetches recent agent_actions failures from DB, asks Gemini to diagnose,
and either auto-notifies the owner or logs the proposed fix.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from google import genai
from src.settings import settings

logger = logging.getLogger(__name__)

_DIAGNOSE_PROMPT = """
You are OishaBrain, the self-improvement engine of Oisha-OS.

Recent agent failures (last {n} errors):
{failures_json}

Analyze these failures and return a JSON object with this exact schema:
{
  "diagnosis": "root cause summary (2-3 sentences)",
  "affected_component": "module or function name",
  "proposed_fix": "concrete code-level fix description",
  "priority": "critical|high|medium|low",
  "safe_to_auto_apply": false,
  "owner_action_needed": "what the owner should do (1 sentence)"
}

Return ONLY valid JSON. No markdown, no explanation outside JSON.
"""


class OishaBrain:
    """Diagnoses failures, proposes fixes, notifies owner via Telegram."""

    def __init__(self, db=None, gemini_api_key: Optional[str] = None, bot_token: Optional[str] = None, owner_id: Optional[int] = None):
        self.db = db
        self.bot_token = bot_token
        self.owner_id = owner_id
        self.gemini_model = os.getenv("GEMINI_BRAIN_MODEL", settings.GEMINI_CALL_MODEL)
        self._client: Optional[genai.Client] = None
        if gemini_api_key:
            self._client = genai.Client(api_key=gemini_api_key)

    async def evolve(self, task: str, limit: int = 20) -> Dict[str, Any]:
        """
        Main entry point.
        - Fetches recent failures from DB
        - Asks Gemini to diagnose
        - Notifies owner if safe_to_auto_apply is False
        - Logs result to agent_actions
        """
        failures = await self._fetch_failures(limit)

        if not failures:
            result = {
                "diagnosis": "No recent failures detected.",
                "affected_component": "none",
                "proposed_fix": "System is healthy.",
                "priority": "low",
                "safe_to_auto_apply": False,
                "owner_action_needed": "No action required.",
                "task": task,
                "analyzed_at": datetime.now().isoformat(),
            }
            await self._log(result)
            return result

        result = await self._diagnose(failures, task)
        await self._log(result)

        if result.get("priority") in ("critical", "high"):
            await self._notify_owner(result)

        return result

    async def _fetch_failures(self, limit: int):
        if not self.db or not hasattr(self.db, "execute"):
            return []
        try:
            rows = await self.db.execute(
                "SELECT action_type, action_data, created_at FROM agent_actions "
                "WHERE success = 0 ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [
                {
                    "action_type": r[0],
                    "action_data": r[1],
                    "created_at": r[2],
                }
                for r in (rows or [])
            ]
        except Exception as e:
            logger.error(f"[OishaBrain] fetch failures error: {e}")
            return []

    async def _call_diagnose_llm(self, prompt: str) -> str:
        if self._client is not None:
            try:
                import asyncio

                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=self.gemini_model,
                    contents=prompt,
                )
                text = (getattr(response, "text", "") or "").strip()
                if text:
                    return text
            except Exception as exc:
                logger.debug("[OishaBrain] Primary Gemini failed, falling back: %s", exc)
        from src.services.utils.free_ai_router import get_free_ai_router

        router = getattr(self, "_router", None) or get_free_ai_router()
        result = await router.generate_text(
            prompt,
            system="Faqat valid JSON obyekt qaytaring.",
            max_tokens=700,
            temperature=0.2,
        )
        return (getattr(result, "text", "") or "").strip()

    async def _diagnose(self, failures: list, task: str) -> Dict[str, Any]:
        failures_dump = json.dumps(failures, ensure_ascii=False, indent=2)[:3000]
        prompt = (
            _DIAGNOSE_PROMPT
            .replace("{n}", str(len(failures)))
            .replace("{failures_json}", failures_dump)
        )

        try:
            raw = (await self._call_diagnose_llm(prompt)) or "{}"
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end > start:
                raw = raw[start : end + 1]
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Diagnosis JSON is not an object")
            parsed["task"] = task
            parsed["analyzed_at"] = datetime.now().isoformat()
            return parsed
        except Exception as e:
            logger.error(f"[OishaBrain] Gemini diagnose error: {e}")
            return {
                "diagnosis": f"Gemini call failed: {e}",
                "affected_component": "agent_brain",
                "proposed_fix": "Check Gemini API quota and model availability.",
                "priority": "medium",
                "safe_to_auto_apply": False,
                "owner_action_needed": "Check Gemini API quota.",
                "task": task,
                "analyzed_at": datetime.now().isoformat(),
            }

    async def _notify_owner(self, result: Dict[str, Any]) -> None:
        if not self.bot_token or not self.owner_id:
            return
        import html as std_html

        text = (
            "🧠 <b>OishaBrain Alert</b>\n"
            f"Priority: <code>{std_html.escape(str(result.get('priority', 'unknown')))}</code>\n\n"
            f"<b>Diagnosis</b>\n{std_html.escape(str(result.get('diagnosis', '')))}\n\n"
            f"<b>Component</b>: <code>{std_html.escape(str(result.get('affected_component', '')))}</code>\n"
            f"<b>Proposed fix</b>: {std_html.escape(str(result.get('proposed_fix', '')))}\n\n"
            f"<b>Owner action</b>: {std_html.escape(str(result.get('owner_action_needed', '')))}"
        )
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={
                    "chat_id": self.owner_id,
                    "text": text,
                    "parse_mode": "HTML",
                })
        except Exception as e:
            logger.error(f"[OishaBrain] Telegram notify error: {e}")

    async def _log(self, result: Dict[str, Any]) -> None:
        if not self.db or not hasattr(self.db, "log_agent_action"):
            return
        try:
            await self.db.log_agent_action(
                user_id=0,
                action_type="agent_brain_evolve",
                data=result,
                success=True,
            )
        except Exception as e:
            logger.error(f"[OishaBrain] log error: {e}")


# Singleton — initialized properly in main.py with db, api_key, bot_token, owner_id
oisha_brain = OishaBrain()
