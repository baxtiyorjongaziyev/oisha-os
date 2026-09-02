"""
Pipeline Auditor core service.
"""
from __future__ import annotations

import asyncio
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
        self.model_name = os.getenv("GEMINI_PIPELINE_AUDITOR_MODEL", settings.GEMINI_CALL_MODEL)
        self.call_analyzer = CallAnalyzer(amocrm=self.amocrm, db=self.db, gemini_client=self.genai_client, model_name=self.model_name)

    async def _save_user_intelligence(self, **kwargs):
        return await _save_user_intelligence(self.db, **kwargs)

    async def generate_intelligence_profile(self, deal_info: Dict[str, Any], dm_history: List[Dict[str, Any]], call_history: List[Dict[str, Any]], airtable_project: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await generate_intelligence_profile(self.genai_client, self.model_name, deal_info, dm_history, call_history, airtable_project)

    async def _fetch_call_history(self, lead_id: int) -> List[Dict[str, Any]]:
        call_history = []
        try:
            conn = await self.db.get_connection()
            q = "SELECT transcript, summary, next_steps, client_mood FROM call_analyses WHERE lead_id = ? ORDER BY analyzed_at DESC"
            res = conn.execute(q, (lead_id,))
            cur = await _maybe_await(res)
            rows = await _maybe_await(cur.fetchall())
            for r in rows or []:
                call_history.append({"transcript": r[0], "summary": r[1], "next_steps": r[2], "client_mood": r[3]})
        except Exception:
            pass
        return call_history

    async def _match_project_and_dm(self, lead_name: str, phone: Optional[str], airtable_projects: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], Optional[int], List[Dict[str, Any]]]:
        user_id, dm_history = None, []
        if phone:
            try:
                user_id = await self.db.get_user_id_by_phone(phone)
                if user_id:
                    dm_history = await self.db.get_recent_messages(user_id=user_id, limit=30)
            except Exception:
                pass
        clean_name = lead_name.strip().lower()
        matched = airtable_projects.get(clean_name)
        if not matched:
            for pname, pdata in airtable_projects.items():
                if pname in clean_name or clean_name in pname:
                    matched = pdata
                    break
        return matched, user_id, dm_history

    async def _apply_lead_profile(self, lead: Dict[str, Any], profile: Dict[str, Any], user_id: Optional[int], matched_project: Optional[Dict[str, Any]]) -> None:
        lead_id = int(lead.get("id"))
        ptype = profile.get("psychotype", "Amiable")
        prob = profile.get("close_probability", 50)
        strat = profile.get("negotiation_strategy", "1. Aloqa")
        next_task_text = profile.get("next_task_text")
        if user_id:
            await self._save_user_intelligence(
                user_id=user_id, psychotype=ptype, pain_points=profile.get("pain_points", "N/A"),
                objections=profile.get("objections", "N/A"), drivers=profile.get("buying_drivers", "N/A"),
                negotiation_strategy=strat, facts_json={"deal_id": lead_id, "deal_name": lead.get("name"), "price": lead.get("price", 0), "close_probability": prob, "airtable_match": bool(matched_project)},
            )
        crm_note = f"🕌 **[Oisha-OS: Customer Intelligence]**\n👤 #{ptype} | Win: {prob}%\n🚀 Reja:\n{strat}"
        try:
            await asyncio.to_thread(self.amocrm.add_lead_note, lead_id, crm_note)
            if prob >= 80:
                await self.amocrm.add_lead_tag(lead_id, "High_Win_Prob")
            if next_task_text and next_task_text.upper() != "N/A":
                from src.utils.task_scheduler import task_deadline
                complete_till = task_deadline(due_in_hours=24)
                await self.amocrm.create_task(
                    element_id=lead_id,
                    text=f"🎯 [Oisha-OS: Strategic Next Step] {next_task_text}",
                    complete_till=complete_till,
                    responsible_user_id=lead.get("responsible_user_id"),
                )
        except Exception:
            pass

    async def _audit_single_lead(self, lead: Dict[str, Any], airtable_projects: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        lead_id = lead.get("id")
        if not lead_id:
            return None
        try:
            await self.call_analyzer.process_call_recordings_for_lead(int(lead_id), min_call_duration_seconds=settings.AMOCRM_CALL_ANALYSIS_MIN_DURATION_SECONDS)
        except Exception:
            pass

        calls = await self._fetch_call_history(int(lead_id))
        phone = await asyncio.to_thread(self.amocrm.get_lead_phone, int(lead_id))
        matched, uid, dms = await self._match_project_and_dm(lead.get("name", "N/A"), phone, airtable_projects)
        profile = await self.generate_intelligence_profile(deal_info=lead, dm_history=dms, call_history=calls, airtable_project=matched)
        await self._apply_lead_profile(lead, profile, uid, matched)
        return {"deal_id": lead_id, "deal_name": lead.get("name", "N/A"), "price": lead.get("price", 0), "psychotype": profile.get("psychotype"), "win_probability": profile.get("close_probability")}

    async def audit_all_deals(self, limit: int = 500) -> Dict[str, Any]:
        """Audit all deals in CRM and update customer intelligence profiles."""
        logger.info("🚀 [AUDITOR] Starting CRM Intelligence Audit...")
        try:
            leads = await self.amocrm.get_leads_detailed(limit=limit)
            if not leads:
                return {"success": False, "reason": "amocrm_auth_expired", "scanned": 0}
        except Exception as ae:
            return {"success": False, "reason": f"amocrm_fetch_error: {ae}", "scanned": 0}

        airtable_projects = {}
        try:
            for p in self.airtable.get_projects(force_refresh=True):
                if p.get("project_name"):
                    airtable_projects[p["project_name"].strip().lower()] = p
        except Exception:
            pass

        results = []
        for lead in leads:
            res = await self._audit_single_lead(lead, airtable_projects)
            if res:
                results.append(res)
            await asyncio.sleep(0.1)

        return {"success": True, "scanned": len(results), "deals": results}
