"""Smart Task Creator — CRM ma'lumotlarini AI tahlili asosida smart task yaratadi.

Lead status, notes, tags, kontakt, pipeline holatiga qarab:
- Qo'ng'iroq qilish kerakmi?
- Qanday mavzuda gaplashish kerak?
- Keyingi qadam nima?
- Qachon qilish kerak?

24/7 BackgroundMonitor dan chaqiriladi.
"""

from __future__ import annotations
from src.context import app_ctx

import json
import time
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Pipeline va status ID lari
PIPELINE_ID = 10117998
STATUS_IDS = {
    "new": 80178214,           # Nerazobranoe
    "first_contact": 86076798, # Birinchi kontakt qilindi
    "no_contact": 80178226,    # Bog'lanib bo'lmadi
    "chat_started": 80178222,  # Muloqot boshlandi
    "meeting": 80178218,       # Uchrashuv belgilandi
    "consultation": 86306474,  # Konsultatsiya o'tdi
    "brief": 86306478,         # Brief / Ehtiyoj aniqlandi
    "presentation": 86306482,  # Prezentatsiya & KP
    "followup": 86306486,      # Follow-up / Qaror kutilyapti
    "negotiation": 86306490,   # Muzokara / Shartnoma
    "advance": 86306494,       # 50% Avans olindi
    "won": 142,                # Muvoffaqiyatli
    "lost": 143,               # Yopildi, muvoffaqiyatsiz
}

OWNER_ID = 13021974  # Baxtiyorjon


class SmartTaskCreator:
    """CRM ma'lumotlarini tahlil qilib, smart task yaratadi."""

    def __init__(self, token_file: str = "data/amocrm_token.json"):
        self.token_file = token_file
        self.base_url = "https://jonbrandingagency.amocrm.ru"
        self._token: Optional[str] = None
        self._token_expires: float = 0

    def _load_token(self) -> Optional[str]:
        """Token ni fayldan yuklash."""
        import os

        if not os.path.exists(self.token_file):
            return None

        try:
            with open(self.token_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)

            token = data.get("access_token")
            expires = data.get("expires_at", 0)

            if not token or time.time() > expires:
                return None

            self._token = token
            self._token_expires = expires
            return token

        except Exception as e:
            logger.error("[SMART_TASK] Token load error: %s", e)
            return None

    def _get_headers(self) -> dict:
        """API headerlari."""
        if not self._token or time.time() > self._token_expires:
            self._load_token()
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def get_lead_full(self, lead_id: int) -> dict:
        """Lead ning to'liq ma'lumotini olish — contacts, tags, notes."""
        try:
            # Lead + contacts + tags (bitta so'rov)
            resp = httpx.get(
                f"{self.base_url}/api/v4/leads/{lead_id}",
                params={"with": "contacts,tags"},
                headers=self._get_headers(),
                timeout=30,
            )
            if resp.status_code != 200:
                return {}
            lead = resp.json()

            # Notes (bitta so'rov)
            notes = []
            try:
                notes_resp = httpx.get(
                    f"{self.base_url}/api/v4/leads/{lead_id}/notes",
                    headers=self._get_headers(),
                    timeout=30,
                )
                if notes_resp.status_code == 200:
                    notes = notes_resp.json().get("_embedded", {}).get("notes", [])
            except Exception as exc:
                logger.debug("[SMART_TASK] Notes fetch failed for lead %d: %s", lead_id, exc)

            # Tasks (bitta so'rov)
            tasks = []
            try:
                tasks_resp = httpx.get(
                    f"{self.base_url}/api/v4/tasks",
                    params={
                        "filter[entity_id]:eq": lead_id,
                        "filter[entity_type]:eq": "leads",
                        "limit": 10,
                    },
                    headers=self._get_headers(),
                    timeout=30,
                )
                if tasks_resp.status_code == 200:
                    tasks = tasks_resp.json().get("_embedded", {}).get("tasks", [])
            except Exception as exc:
                logger.debug("[SMART_TASK] Tasks fetch failed for lead %d: %s", lead_id, exc)

            # Contact phones — faqat bitta contact uchun
            phones = []
            contacts = lead.get("_embedded", {}).get("contacts", [])
            if contacts:
                try:
                    c_resp = httpx.get(
                        f"{self.base_url}/api/v4/contacts/{contacts[0]['id']}",
                        headers=self._get_headers(),
                        timeout=30,
                    )
                    if c_resp.status_code == 200:
                        for cf in c_resp.json().get("custom_fields_values", []):
                            if cf.get("field_code") == "PHONE":
                                for v in cf.get("values", []):
                                    phones.append(v.get("value", ""))
                except Exception as exc:
                    logger.debug("[SMART_TASK] Contact phones fetch failed for lead %d: %s", lead_id, exc)

            return {
                "lead": lead,
                "notes": notes,
                "tasks": tasks,
                "phones": phones,
            }

        except Exception as e:
            logger.error("[SMART_TASK] Error getting lead %d: %s", lead_id, e)
            return {}

    def format_lead_context(self, data: dict) -> str:
        """Lead ma'lumotlarini AI uchun formatlash."""
        lead = data.get("lead", {})
        notes = data.get("notes", [])
        tasks = data.get("tasks", [])
        phones = data.get("phones", [])

        lines = []
        lines.append(f"LEAD: {lead.get('name', 'Nomalum')}")
        lines.append(f"ID: {lead.get('id')}")
        lines.append(f"Status ID: {lead.get('status_id')}")
        lines.append(f"Narx: {lead.get('price', 0)} so'm")
        lines.append(f"Yaratilgan: {lead.get('created_at')}")
        lines.append(f"Yangilangan: {lead.get('updated_at')}")

        # Tags
        tags = lead.get("_embedded", {}).get("tags", [])
        if tags:
            lines.append(f"Tags: {', '.join(t.get('name', '') for t in tags)}")

        # Phones
        if phones:
            lines.append(f"Telefonlar: {', '.join(phones)}")

        # Notes
        if notes:
            lines.append(f"\nCRM Yozuvlari ({len(notes)}):")
            for n in notes[-5:]:  # oxirgi 5 ta
                ntype = n.get("note_type", "common")
                params = n.get("params", {})
                text = params.get("text", "")
                if text:
                    lines.append(f"  [{ntype}]: {text[:300]}")

        # Tasks
        if tasks:
            lines.append(f"\nTasklar ({len(tasks)}):")
            for t in tasks[-3:]:  # oxirgi 3 ta
                completed = "YAKUNLANGAN" if t.get("is_completed") else "BAJARILMADI"
                lines.append(f"  [{completed}] {t.get('text', '')[:200]}")

        return "\n".join(lines)

    def get_status_name(self, status_id: int) -> str:
        """Status ID dan nom qaytarish."""
        for name, sid in STATUS_IDS.items():
            if sid == status_id:
                return name
        return f"unknown_{status_id}"

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


# Singleton
app_ctx.creator: Optional[SmartTaskCreator] = None


def get_smart_task_creator() -> SmartTaskCreator:
    """SmartTaskCreator singleton."""
    if app_ctx.creator is None:
        app_ctx.creator = SmartTaskCreator()
    return app_ctx.creator


async def run_smart_task_creation(dry_run: bool = False) -> dict:
    """BackgroundMonitor dan chaqiriladi."""
    creator = get_smart_task_creator()
    return await creator.analyze_and_create_tasks(dry_run=dry_run)


if __name__ == "__main__":
    import asyncio
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry-run" in sys.argv
    stats = asyncio.run(run_smart_task_creation(dry_run=dry))
    print(f"Stats: {json.dumps(stats, indent=2)}")
