"""
Pipeline Auditor core service.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
from typing import Any, Dict, List, Optional

import structlog
from src.database import Database
from src.services.core.airtable_sync import AirtableSync
from src.services.core.call_analyzer import CallAnalyzer
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.pipeline.ai_profile import generate_intelligence_profile
from src.services.core.pipeline.helpers import _maybe_await, _save_user_intelligence
from src.settings import settings

logger = structlog.get_logger()


class PipelineAuditor:
    """Service to reconcile data across AmoCRM, Airtable, and Telegram Userbot history."""

    def __init__(
        self,
        amocrm: AmoCRMSync,
        airtable: AirtableSync,
        db: Database,
        genai_client=None,
    ):
        self.amocrm = amocrm
        self.airtable = airtable
        self.db = db
        self.report_dir = os.path.join("data", "reports")
        os.makedirs(self.report_dir, exist_ok=True)

        from google import genai

        self.genai_client = genai_client
        if self.genai_client is None:
            api_key = (settings.GEMINI_API_KEY.get_secret_value() or "").strip()
            if api_key:
                try:
                    self.genai_client = genai.Client(api_key=api_key)
                except Exception as exc:
                    logger.warning("[AUDITOR] Gemini client init skipped: %s", exc)
            else:
                logger.warning("[AUDITOR] GEMINI_API_KEY missing; local fallbacks enabled.")
        self.model_name = os.getenv(
            "GEMINI_PIPELINE_AUDITOR_MODEL", settings.GEMINI_CALL_MODEL
        )

        self.call_analyzer = CallAnalyzer(
            amocrm=self.amocrm,
            db=self.db,
            gemini_client=self.genai_client,
            model_name=self.model_name,
        )

    async def _save_user_intelligence(
        self,
        user_id: int,
        psychotype: str,
        pain_points: str,
        objections: str,
        drivers: str,
        negotiation_strategy: str,
        facts_json: dict,
    ):
        await _save_user_intelligence(
            self.db,
            user_id,
            psychotype,
            pain_points,
            objections,
            drivers,
            negotiation_strategy,
            facts_json,
        )

    async def generate_intelligence_profile(
        self,
        deal_info: Dict[str, Any],
        dm_history: List[Dict[str, Any]],
        call_history: List[Dict[str, Any]],
        airtable_project: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return await generate_intelligence_profile(
            self.genai_client,
            self.model_name,
            deal_info,
            dm_history,
            call_history,
            airtable_project,
        )

    async def audit_all_deals(self, limit: int = 500) -> Dict[str, Any]:
        logger.info("🚀 [AUDITOR] Starting CRM 500 Intelligence Audit...")

        try:
            leads = await self.amocrm.get_leads_detailed(limit=limit)
            if not leads:
                return {"success": False, "reason": "amocrm_auth_expired", "scanned": 0}
        except Exception as ae:
            logger.error(f"[AUDITOR] AmoCRM fetch error: {ae}")
            return {"success": False, "reason": f"amocrm_fetch_error: {ae}", "scanned": 0}

        airtable_projects = {}
        try:
            projects = self.airtable.get_projects(force_refresh=True)
            for proj in projects:
                name = proj.get("project_name")
                if name:
                    airtable_projects[name.strip().lower()] = proj
        except Exception as arte:
            logger.warning(f"[AUDITOR] Airtable fetch skipped: {arte}")

        results = []
        scanned = 0

        for lead in leads:
            lead_id = lead.get("id")
            if not lead_id:
                continue

            lead_name = lead.get("name", "N/A")
            price = lead.get("price", 0)

            try:
                await self.call_analyzer.process_call_recordings_for_lead(
                    int(lead_id),
                    min_call_duration_seconds=settings.AMOCRM_CALL_ANALYSIS_MIN_DURATION_SECONDS,
                )
            except Exception as e:
                logger.warning(f"[AUDITOR] Call processing failed for lead {lead_id}: {e}")

            call_history = []
            try:
                conn = await self.db.get_connection()
                q = "SELECT transcript, summary, next_steps, client_mood FROM call_analyses WHERE lead_id = ? ORDER BY analyzed_at DESC"
                res = conn.execute(q, (int(lead_id),))
                if hasattr(res, "__aenter__"):
                    async with res as cur:
                        rows = await _maybe_await(cur.fetchall())
                else:
                    cur = await _maybe_await(res)
                    rows = await _maybe_await(cur.fetchall())
                for r in rows or []:
                    call_history.append({
                        "transcript": r[0],
                        "summary": r[1],
                        "next_steps": r[2],
                        "client_mood": r[3],
                    })
            except Exception as e:
                logger.debug(f"[AUDITOR] DB call history fetch skipped: {e}")

            phone = await asyncio.to_thread(self.amocrm.get_lead_phone, int(lead_id))
            user_id = None
            dm_history = []

            if phone:
                try:
                    user_id = await self.db.get_user_id_by_phone(phone)
                    if user_id:
                        dm_history = await self.db.get_recent_messages(user_id=user_id, limit=30)
                except Exception as dbe:
                    logger.debug(f"[AUDITOR] Database history fetch skipped for {phone}: {dbe}")

            matched_project = None
            lead_name_clean = lead_name.strip().lower()
            if lead_name_clean in airtable_projects:
                matched_project = airtable_projects[lead_name_clean]
            else:
                for proj_name, proj_data in airtable_projects.items():
                    if proj_name in lead_name_clean or lead_name_clean in proj_name:
                        matched_project = proj_data
                        break

            profile = await self.generate_intelligence_profile(
                deal_info=lead,
                dm_history=dm_history,
                call_history=call_history,
                airtable_project=matched_project,
            )

            psychotype = profile.get("psychotype", "Amiable")
            pain_points = profile.get("pain_points", "N/A")
            objections = profile.get("objections", "N/A")
            drivers = profile.get("buying_drivers", "N/A")
            close_prob = profile.get("close_probability", 50)
            strategy = profile.get("negotiation_strategy", "1. Aloqa")
            next_task_text = profile.get("next_task_text", "Mijoz bilan aloqaga chiqish va ehtiyojlarni aniqlash")

            if user_id:
                await self._save_user_intelligence(
                    user_id=user_id,
                    psychotype=psychotype,
                    pain_points=pain_points,
                    objections=objections,
                    drivers=drivers,
                    negotiation_strategy=strategy,
                    facts_json={
                        "deal_id": lead_id,
                        "deal_name": lead_name,
                        "price": price,
                        "close_probability": close_prob,
                        "airtable_match": bool(matched_project)
                    }
                )

            crm_note = (
                f"🕌 **[Oisha-OS: Customer Intelligence Profile]** 🛡️\n"
                f"👤 Psixotip: #{psychotype}\n"
                f"🎯 Win Probability: {close_prob}%\n"
                f"📌 Ehtiyoj/Pain Points: {pain_points}\n"
                f"💡 Haridor motivlari: {drivers}\n"
                f"🚀 [Surgical Strategy] Muzokara rejasi:\n{strategy}"
            )
            try:
                await asyncio.to_thread(self.amocrm.add_lead_note, int(lead_id), crm_note)
            except Exception as cne:
                logger.debug(f"[AUDITOR] CRM note skip for lead {lead_id}: {cne}")

            if close_prob >= 80:
                try:
                    await self.amocrm.add_lead_tag(int(lead_id), "High_Win_Prob")
                except Exception:
                    logger.warning("[AUDITOR] Failed to add High_Win_Prob tag to lead %s", lead_id, exc_info=True)

            if next_task_text and next_task_text.upper() != "N/A":
                try:
                    from src.utils.task_scheduler import task_deadline
                    complete_till = task_deadline(due_in_hours=24)
                    await self.amocrm.create_task(
                        element_id=int(lead_id),
                        text=f"🎯 [Oisha-OS: Strategic Next Step] {next_task_text}",
                        complete_till=complete_till,
                        responsible_user_id=lead.get("responsible_user_id"),
                    )
                except Exception as cte:
                    logger.warning(f"[AUDITOR] AmoCRM task creation failed for lead {lead_id}: {cte}")

            results.append({
                "deal_id": lead_id,
                "deal_name": lead_name,
                "price": price,
                "phone": phone or "N/A",
                "psychotype": psychotype,
                "close_probability": close_prob,
                "pain_points": pain_points,
                "negotiation_strategy": strategy.replace("\n", " | "),
                "airtable_synced": "Yes" if matched_project else "No"
            })

            scanned += 1
            await asyncio.sleep(2.0)

        json_path = os.path.join(self.report_dir, "crm_500_intelligence_report.json")
        csv_path = os.path.join(self.report_dir, "crm_500_intelligence_dashboard.csv")

        try:
            with open(json_path, "w", encoding="utf-8") as jf:
                json.dump(results, jf, ensure_ascii=False, indent=2)

            with open(csv_path, "w", encoding="utf-8", newline="") as cf:
                writer = csv.DictWriter(
                    cf,
                    fieldnames=[
                        "deal_id", "deal_name", "price", "phone",
                        "psychotype", "close_probability", "pain_points",
                        "negotiation_strategy", "airtable_synced"
                    ]
                )
                writer.writeheader()
                writer.writerows(results)
        except Exception as e:
            logger.error(f"[AUDITOR] Report save error: {e}")

        return {
            "success": True,
            "scanned": scanned,
            "json_path": json_path,
            "csv_path": csv_path,
        }
