"""
LLM classification, contact categorization, and comprehensive lead audit logic.
"""
import asyncio
import json
import re
from typing import Any, Dict, Optional, Tuple

import structlog
logger = structlog.get_logger(__name__)

from src.services.core.crm.auditor.db_storage import _maybe_await
from src.services.utils.gemini_fallback import generate_content_with_fallback

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None


class ClassifierMixin:
    """Handles contact classification and multi-channel audit execution."""

    async def classify_contact(
        self,
        lead_name: str,
        contact_name: str,
        phone: str,
        username: str,
        call_summary: str,
        telegram_history: str,
        lead_details: str = "",
        group_history: str = "",
        tasks_history: str = "",
        notes_history: str = "",
        telegram_unanswered_info: str = "",
    ) -> Tuple[str, str, str, str, str]:  # Return (category, explanation, detailed_summary, task_text, telegram_draft_reply)
        """Use Gemini to classify the contact and generate conclusion, follow-up task, and draft reply."""
        if not self.genai_client:
            return "Boshqa", "Gemini API sozlanmagan. Standart toifa 'Boshqa' deb tanlandi.", "", "", ""

        context = {
            "lead_name": lead_name,
            "contact_name": contact_name,
            "phone": phone,
            "username": username,
            "call_summary_or_transcript": call_summary[:2000],
            "telegram_history": telegram_history[:3000],
            "lead_details": lead_details[:2000],
            "group_history": group_history[:3000],
            "tasks_history": tasks_history[:2000],
            "notes_history": notes_history[:3000],
            "telegram_unanswered_info": telegram_unanswered_info,
        }
        from src.services.core.crm.auditor.classifier_prompt import build_classification_prompt

        prompt = build_classification_prompt(context)

        try:
            kwargs = {"model": self.model_name, "contents": [prompt]}
            if genai_types is not None:
                kwargs["config"] = genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )

            # Using generate_content_with_fallback for resiliency
            response, _ = await generate_content_with_fallback(
                self.genai_client,
                primary_model=self.model_name,
                contents=kwargs["contents"],
                config=kwargs.get("config"),
                env_name="GEMINI_CRM_AUDIT_FALLBACK_MODELS",
                log_prefix="[AUDITOR_GEMINI]",
            )
            text = str(getattr(response, "text", "") or "").strip()

            # Parse JSON safely
            data = {}
            if text:
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    # Try regex match
                    match = re.search(r"\{.*\}", text, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))

            category = data.get("category")
            explanation = data.get("explanation", "Sabab taqdim etilmadi.")
            detailed_summary = data.get("detailed_summary", f"Tizim tomonidan avtomatik tahlil: {explanation}")
            next_step_task = data.get("next_step_task", "Mijoz bilan bog'lanib, holatni aniqlashtiring.")
            telegram_draft_reply = data.get("telegram_draft_reply", "")

            valid_categories = {"Mijoz", "Shaxsiy", "Kandidat", "Hamkor/Jamoa", "Boshqa"}
            if category not in valid_categories:
                category = "Boshqa"

            return category, explanation, detailed_summary, next_step_task, telegram_draft_reply
        except Exception as e:
            logger.error("[AUDITOR] Gemini classification/analysis failed: %s", e)

            # Rules-based fallback if Gemini fails
            lowered_history = (telegram_history + " " + call_summary + " " + group_history + " " + notes_history).lower()
            category = "Boshqa"
            if any(w in lowered_history for w in ("mijozimiz emas", "ishlab bo'lmaydi", "pulini qaytar", "not a client", "junk")):
                category = "Boshqa"
                next_step_task = ""
            elif any(w in lowered_history for w in ("rezyume", "resume", "cv", "ishga", "vakansiya", "amaliyot")):
                category = "Kandidat"
                next_step_task = ""
            elif any(w in lowered_history for w in ("branding", "brending", "narxi", "narx", "site", "sayt", "logo", "smm", "dizayn")):
                category = "Mijoz"
                next_step_task = "Mijoz bilan bog'lanib, keyingi kelishuvlarni aniqlashtiring."
            else:
                next_step_task = "Mijoz bilan bog'lanib, keyingi kelishuvlarni aniqlashtiring."

            explanation = f"Xatolik tufayli qoida bo'yicha saralandi (Fallback): {str(e)}"
            detailed_summary = f"Mijoz va uning yozishmalari tahlili xatolik tufayli yakunlanmadi. Aloqa toifasi: {category}."

            return category, explanation, detailed_summary, next_step_task, ""

    async def audit_lead_by_data(self, lead: Dict[str, Any], force: bool = False) -> Optional[str]:
        """Audit and classify a single AmoCRM lead data dictionary."""
        lead_id = lead.get("id")
        if not lead_id:
            return None

        if not force and await self.is_lead_audited(int(lead_id)):
            return "skipped"

        from src.services.core.crm.auditor.audit_context import collect_contact_context
        from src.services.core.crm.auditor.audit_analysis import analyze_and_save
        from src.services.core.crm.auditor.audit_actions import (
            _add_audit_note, _save_draft, _create_follow_up, _tag_lead,
        )

        context = await collect_contact_context(self, lead, lead_id)
        existing_tasks = await self.get_lead_tasks(int(lead_id))
        result = await analyze_and_save(self, lead, lead_id, context, existing_tasks)
        category, summary, task, draft, temperature, temperature_reason = result
        await _add_audit_note(self, lead_id, summary)
        await _save_draft(self, lead_id, context["telegram_user_id"], context["is_unanswered_tg"], draft)
        await _create_follow_up(self, lead, lead_id, task, existing_tasks)
        await _tag_lead(self, lead_id, category, temperature, temperature_reason)
        return category

    async def run_audit(
        self,
        limit: int = 500,
        progress_callback: Optional[callable] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Main entry point. Fetches and audits leads, updates progress."""
        await self.init_db()
        
        leads = await self.fetch_recent_leads(limit=limit)
        stats = {
            "total_leads": len(leads),
            "processed": 0,
            "skipped": 0,
            "categories": {
                "Mijoz": 0,
                "Shaxsiy": 0,
                "Kandidat": 0,
                "Hamkor/Jamoa": 0,
                "Boshqa": 0,
            },
        }

        for idx, lead in enumerate(leads):
            lead_id = lead.get("id")
            if not lead_id:
                continue

            try:
                result = await self.audit_lead_by_data(lead, force=force)
                if result == "skipped":
                    stats["skipped"] += 1
                elif result:
                    stats["processed"] += 1
                    stats["categories"][result] = stats["categories"].get(result, 0) + 1
                
                # Sleep between requests to avoid rate limits
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error("[AUDITOR] Error auditing lead %s: %s", lead_id, e, exc_info=True)
                stats["processed"] += 1
                stats["categories"]["Boshqa"] += 1

            # Progress callback every 10 leads
            if progress_callback and (idx + 1) % 10 == 0:
                try:
                    await progress_callback(idx + 1, len(leads), stats)
                except Exception as cb_err:
                    logger.error("[AUDITOR] Progress callback error: %s", cb_err)

        # Final progress callback
        if progress_callback:
            try:
                await progress_callback(len(leads), len(leads), stats)
            except Exception:
                logger.debug("[CRM_AUDIT] Final progress callback failed", exc_info=True)

        return stats
