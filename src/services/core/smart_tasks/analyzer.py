"""
Gemini AI prompt engineering, task decision parsing, and task injection mixin.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import requests

from src.settings import settings

logger = logging.getLogger("SmartTaskCreator")


class TaskAnalyzerMixin:
    """Uses AI to determine next smart actions and schedules tasks in AmoCRM."""

    async def analyze_and_create_tasks(self, dry_run: bool = False) -> dict:
        """Barcha faol leadlarni tahlil qilib, smart task yaratadi."""
        from src.utils.ai_utils import _try_all_providers

        stats = {
            "total_leads": 0,
            "analyzed": 0,
            "tasks_created": 0,
            "skipped": 0,
            "errors": 0,
        }

        # Faol leadlarni olish — barchasini olib, Python da filter
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v4/leads",
                params={"limit": 100},
                headers=self._get_headers(),
                timeout=30,
            )
            if resp.status_code != 200:
                return stats
            all_leads = resp.json().get("_embedded", {}).get("leads", [])

            # Python da filter — faqat faol leadlar
            active_leads = [
                l for l in all_leads
                if l.get("pipeline_id") == PIPELINE_ID
                and l.get("status_id") not in (STATUS_IDS["won"], STATUS_IDS["lost"])
            ][:20]  # max 20 ta
            stats["total_leads"] = len(active_leads)
        except Exception as e:
            logger.error("[SMART_TASK] Error getting leads: %s", e)
            return stats

        for lead in active_leads:
            lead_id = lead["id"]

            try:
                # To'liq ma'lumot olish
                data = self.get_lead_full(lead_id)
                if not data:
                    stats["errors"] += 1
                    continue

                # Oxirgi taskni tekshirish — yangi task kerakmi?
                tasks = data.get("tasks", [])
                now = int(time.time())
                has_recent_task = False
                for t in tasks:
                    if not t.get("is_completed"):
                        has_recent_task = True
                        break
                    # 48 soat oldin tugagan task
                    completed_at = t.get("completed_at", 0)
                    if completed_at and (now - completed_at) < 172800:
                        has_recent_task = True
                        break

                if has_recent_task:
                    stats["skipped"] += 1
                    continue

                # AI tahlili
                context = self.format_lead_context(data)
                status_name = self.get_status_name(lead.get("status_id", 0))

                prompt = f"""Sen Oisha AI sotuv kuzatuvchisisen. Quyidagi CRM lead ma'lumotini tahlil qil va smart task yarat.

LEAD HOLATI:
{context}

PIPELINE STATUS: {status_name}

VAZIFA:
1. Lead holatini tahlil qil
2. Qanday qo'ng'iroq/suhbat kerakligini aniqla
3. Aniq task yarat — matn, muddat, tur

JAVOBLI FORMAT (JSON):
{{
  "task_text": "Aniq task matni (masalan: 'Nigora opa bilan breifni aniqlashtirish uchun qo'ng'iroq — logo dizayn narxi haqida')",
  "task_type": "call yoki meeting",
  "priority": "high yoki medium yoki low",
  "reason": "Nima uchun shu task kerak (qisqa)",
  "deadline_hours": 24
}}

DIQQAT:
- Task matni ANIQ bo'lishi kerak — nima haqida gaplashish kerak
- Status ga qarab qadam tanla:
  - first_contact → Qayta qo'ng'iroq, e'tirozlarni aniqlash
  - chat_started → Uchrashuv belgilash
  - consultation → Brief olish, KP yuborish
  - presentation → Follow-up, qaror kutish
  - negotiation → Shartnoma tayyorlash
- Agar lead da kontakt yo'q bo'lsa — task yaratma, "skip" deb yoz"""

                messages = [{"role": "user", "content": prompt}]
                system = "CRM sotuv tahlilchisi. Faqat JSON formatda javob ber."

                result = await _try_all_providers(prompt, system)
                if not result:
                    stats["errors"] += 1
                    continue

                # JSON parse
                text = result.text if hasattr(result, "text") else str(result)
                # JSON ni topish
                start = text.find("{")
                end = text.rfind("}") + 1
                if start == -1 or end == 0:
                    logger.warning("[SMART_TASK] No JSON in AI response for lead %d", lead_id)
                    stats["errors"] += 1
                    continue

                task_data = json.loads(text[start:end])
                stats["analyzed"] += 1

                if dry_run:
                    logger.info(
                        "[SMART_TASK][DRY] Lead %d: %s",
                        lead_id,
                        json.dumps(task_data, ensure_ascii=False)[:200],
                    )
                    stats["tasks_created"] += 1
                    continue

                # Task yaratish
                task_text = task_data.get("task_text", "Qo'ng'iroq qilish")
                deadline_hours = task_data.get("deadline_hours", 24)
                task_type = task_data.get("task_type", "call")

                complete_till = now + (deadline_hours * 3600)

                task_payload = {
                    "text": task_text,
                    "entity_id": lead_id,
                    "entity_type": "leads",
                    "complete_till": complete_till,
                    "responsible_user_id": OWNER_ID,
                    "params": {"type": task_type},
                }

                create_resp = httpx.post(
                    f"{self.base_url}/api/v4/tasks",
                    headers=self._get_headers(),
                    json=[task_payload],
                    timeout=15,
                )

                if create_resp.status_code in (200, 201):
                    stats["tasks_created"] += 1
                    logger.info(
                        "[SMART_TASK] Created for lead %d: %s",
                        lead_id,
                        task_text[:100],
                    )
                else:
                    stats["errors"] += 1
                    logger.error(
                        "[SMART_TASK] Failed to create task for lead %d: %s",
                        lead_id,
                        create_resp.status_code,
                    )

            except Exception as e:
                logger.error("[SMART_TASK] Error processing lead %d: %s", lead_id, e)
                stats["errors"] += 1

        logger.info(
            "[SMART_TASK] Done: %d total, %d analyzed, %d tasks created, %d skipped, %d errors",
            stats["total_leads"],
            stats["analyzed"],
            stats["tasks_created"],
            stats["skipped"],
            stats["errors"],
        )

        return stats
