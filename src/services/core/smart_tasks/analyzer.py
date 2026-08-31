"""Gemini AI prompt engineering, task decision parsing, and task injection mixin."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional
import httpx

from src.settings import settings

logger = logging.getLogger("SmartTaskCreator")

PIPELINE_ID = 8847846
OWNER_ID = 11751146
STATUS_IDS = {"won": 142, "lost": 143}


def _has_recent_task(tasks: List[Dict[str, Any]], now: int) -> bool:
    for t in tasks:
        if not t.get("is_completed"):
            return True
        completed_at = t.get("completed_at", 0)
        if completed_at and (now - completed_at) < 172800:
            return True
    return False


class TaskAnalyzerMixin:
    """Uses AI to determine next smart actions and schedules tasks in AmoCRM."""

    def _fetch_active_leads(self) -> List[Dict[str, Any]]:
        resp = httpx.get(
            f"{self.base_url}/api/v4/leads",
            params={"limit": 100},
            headers=self._get_headers(),
            timeout=30,
        )
        if resp.status_code != 200:
            return []
        all_leads = resp.json().get("_embedded", {}).get("leads", [])
        return [
            l for l in all_leads
            if l.get("pipeline_id") == PIPELINE_ID
            and l.get("status_id") not in (STATUS_IDS["won"], STATUS_IDS["lost"])
        ][:20]

    async def _generate_task_decision(self, lead: Dict[str, Any], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        from src.utils.ai_utils import _try_all_providers

        context = self.format_lead_context(data)
        prompt = (
            "Sen Oisha AI sotuv kuzatuvchisisen. Quyidagi CRM lead malumotini tahlil qil va smart task yarat.\n\n"
            + f"LEAD HOLATI:\n{context}\n\n"
            + f"PIPELINE STATUS: {status_name}\n\n"
            + "VAZIFA: 1. Lead holatini tahlil qil. 2. Aniq task yarat.\n"
            + "JAVOBLI FORMAT (JSON): {\"task_text\": \"...\", \"task_type\": \"call\", \"deadline_hours\": 24}\n"
            + "Faqat JSON qaytar."
        )
        result = await _try_all_providers(prompt, "CRM sotuv tahlilchisi. Faqat JSON formatda javob ber.")
        if not result:
            return None
        text = result.text if hasattr(result, "text") else str(result)
        start, end = text.find("{"), text.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        try:
            return json.loads(text[start:end])
        except Exception:
            return None

    def _post_amocrm_task(self, lead_id: int, task_data: Dict[str, Any], now: int) -> bool:
        task_text = task_data.get("task_text", "Qo'ng'iroq qilish")
        deadline_hours = task_data.get("deadline_hours", 24)
        task_type = task_data.get("task_type", "call")
        payload = {
            "text": task_text,
            "entity_id": lead_id,
            "entity_type": "leads",
            "complete_till": now + (deadline_hours * 3600),
            "responsible_user_id": OWNER_ID,
            "params": {"type": task_type},
        }
        res = httpx.post(
            f"{self.base_url}/api/v4/tasks",
            headers=self._get_headers(),
            json=[payload],
            timeout=15,
        )
        return res.status_code in (200, 201)

    async def _process_single_lead(self, lead: Dict[str, Any], dry_run: bool, now: int, stats: dict) -> None:
        lead_id = lead["id"]
        try:
            data = self.get_lead_full(lead_id)
            if not data:
                stats["errors"] += 1
                return
            if _has_recent_task(data.get("tasks", []), now):
                stats["skipped"] += 1
                return
            decision = await self._generate_task_decision(lead, data)
            if not decision:
                stats["errors"] += 1
                return
            stats["analyzed"] += 1
            if dry_run or self._post_amocrm_task(lead_id, decision, now):
                stats["tasks_created"] += 1
            else:
                stats["errors"] += 1
        except Exception as e:
            logger.error("[SMART_TASK] Error processing lead %d: %s", lead_id, e)
            stats["errors"] += 1

    async def analyze_and_create_tasks(self, dry_run: bool = False) -> dict:
        """Barcha faol leadlarni tahlil qilib, smart task yaratadi."""
        stats = {"total_leads": 0, "analyzed": 0, "tasks_created": 0, "skipped": 0, "errors": 0}
        try:
            active_leads = self._fetch_active_leads()
            stats["total_leads"] = len(active_leads)
        except Exception as e:
            logger.error("[SMART_TASK] Error getting leads: %s", e)
            return stats

        now = int(time.time())
        for lead in active_leads:
            await self._process_single_lead(lead, dry_run, now, stats)
        logger.info("[SMART_TASK] Done: %d total, %d created, %d skipped", stats["total_leads"], stats["tasks_created"], stats["skipped"])
        return stats
