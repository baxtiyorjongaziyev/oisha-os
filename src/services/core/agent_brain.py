"""
OishaBrain — LLM-powered failure diagnostics and self-improvement.

Fetches recent agent_actions failures from DB, asks Gemini to diagnose,
and either auto-notifies the owner or logs the proposed fix.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from google import genai

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

    async def _diagnose(self, failures: list, task: str) -> Dict[str, Any]:
        if not self._client:
            return {
                "diagnosis": "Gemini client not configured (GEMINI_API_KEY missing).",
                "affected_component": "agent_brain",
                "proposed_fix": "Set GEMINI_API_KEY in environment.",
                "priority": "high",
                "safe_to_auto_apply": False,
                "owner_action_needed": "Add GEMINI_API_KEY to Cloud Secret Manager.",
                "task": task,
                "analyzed_at": datetime.now().isoformat(),
            }

        prompt = _DIAGNOSE_PROMPT.format(
            n=len(failures),
            failures_json=json.dumps(failures, ensure_ascii=False, indent=2)[:3000],
        )

        try:
            response = self._client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            raw = response.text or "{}"
            # Strip markdown fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
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
        text = (
            f"🧠 *OishaBrain Alert*\n"
            f"Priority: `{result.get('priority', 'unknown')}`\n\n"
            f"*Diagnosis*\n{result.get('diagnosis', '')}\n\n"
            f"*Component*: `{result.get('affected_component', '')}`\n"
            f"*Proposed fix*: {result.get('proposed_fix', '')}\n\n"
            f"*Owner action*: {result.get('owner_action_needed', '')}"
        )
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={
                    "chat_id": self.owner_id,
                    "text": text,
                    "parse_mode": "Markdown",
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
                action_data=result,
                success=True,
            )
        except Exception as e:
            logger.error(f"[OishaBrain] log error: {e}")


# Singleton — initialized properly in main.py with db, api_key, bot_token, owner_id
oisha_brain = OishaBrain()
