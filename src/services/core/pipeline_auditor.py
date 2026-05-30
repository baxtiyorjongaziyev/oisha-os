import asyncio
import logging
import json
import csv
import os
import inspect
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.airtable_sync import AirtableSync
from src.database import Database
from src.services.core.call_analyzer import CallAnalyzer

logger = logging.getLogger(__name__)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class PipelineAuditor:
    """Service to reconcile data across AmoCRM, Airtable, and Telegram Userbot history and build strategic Customer Intelligence."""

    def __init__(self, amocrm: AmoCRMSync, airtable: AirtableSync, db: Database):
        self.amocrm = amocrm
        self.airtable = airtable
        self.db = db
        self.report_dir = os.path.join("data", "reports")
        os.makedirs(self.report_dir, exist_ok=True)

        # AI Config
        from google import genai
        from src.settings import settings

        self.genai_client = genai.Client(
            api_key=settings.GEMINI_API_KEY.get_secret_value()
        )
        self.model_name = "gemini-2.0-flash"

        self.call_analyzer = CallAnalyzer(
            amocrm=self.amocrm,
            db=self.db,
            gemini_client=self.genai_client,
            model_name=self.model_name
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
        """Upsert the extracted customer intelligence profile into our database."""
        try:
            conn = await self.db.get_connection()
            now_str = datetime.now(timezone.utc).isoformat()
            
            query = """
                INSERT INTO user_intelligence (
                    user_id, psychotype, pain_points, objections_history, buying_drivers, negotiation_strategy, facts_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    psychotype = excluded.psychotype,
                    pain_points = excluded.pain_points,
                    objections_history = excluded.objections_history,
                    buying_drivers = excluded.buying_drivers,
                    negotiation_strategy = excluded.negotiation_strategy,
                    facts_json = excluded.facts_json,
                    updated_at = excluded.updated_at
            """
            await conn.execute(
                query,
                (
                    user_id,
                    psychotype,
                    pain_points,
                    objections,
                    drivers,
                    negotiation_strategy,
                    json.dumps(facts_json),
                    now_str,
                ),
            )
            await conn.commit()
            logger.info(f"[AUDITOR] Saved user intelligence for {user_id} in DB.")
        except Exception as e:
            logger.error(f"[AUDITOR] DB write error for user_id {user_id}: {e}")

    async def generate_intelligence_profile(
        self,
        deal_info: Dict[str, Any],
        dm_history: List[Dict[str, Any]],
        call_history: List[Dict[str, Any]],
        airtable_project: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Use Gemini 2.0 Flash to synthesize CRM deal context, project delivery data, DM history, and call transcripts into strategic intelligence."""
        # Format DM history snippet
        history_snippet = "No chat history logged."
        if dm_history:
            history_snippet = "\n".join(
                [
                    f"{'Oisha (AI)' if m.get('is_ai_reply') else 'Mijoz'}: {m.get('message_text', '')}"
                    for m in dm_history[-20:]
                ]
            )

        # Format Call History snippet
        call_snippet = "No call recordings analyzed."
        if call_history:
            call_snippet = "\n".join(
                [
                    f"Call Summary: {c.get('summary', '')}\n"
                    f"Mood: {c.get('client_mood', '')}\n"
                    f"Transcript:\n{c.get('transcript', '')[:1000]}"
                    for c in call_history[-5:]
                ]
            )

        airtable_snippet = "No operational project found in Airtable."
        if airtable_project:
            airtable_snippet = (
                f"Project Name: {airtable_project.get('project_name')}\n"
                f"Stage: {airtable_project.get('stage')}\n"
                f"Deadline: {airtable_project.get('deadline')}\n"
                f"PM/Owner: {airtable_project.get('pm')}"
            )

        prompt = (
            "Analyze the following cross-system customer data and generate a unified Customer Intelligence Profile in Uzbek.\n"
            "Identify:\n"
            "1. Client Psychotype: 'Analytical' (fakt va raqamlarni sevadi), 'Assertive' (tezkor va qat'iy), "
            "'Expressive' (hissiyotli va g'oyalarga boy), 'Amiable' (muloyim va munosabatga kirishuvchan).\n"
            "2. Buying Drivers: Brand identity, premium status, market growth, or cost efficiency.\n"
            "3. Key Pain Points and Objections raised in chat or phone calls.\n"
            "4. Win/Close Probability (0 to 100%).\n"
            "5. Strategic Next Task: A highly specific, extremely personalized, tactical NEXT action step (Zadacha) in Uzbek "
            "for the manager to follow up and progress this deal. This should be concrete, e.g., 'Jasurga logotip tekshiruvi narxini yuborish va patent shartnomasini taqdim etish'.\n"
            "6. Strategic Negotiation Plan: exactly 3 specific tactical action steps for the manager to close or win this deal.\n\n"
            "Ensure the output is valid JSON, strictly complying with the following structure:\n"
            "{\n"
            '  "psychotype": "Analytical / Assertive / Expressive / Amiable",\n'
            '  "pain_points": "Extract client\'s real pain points in Uzbek",\n'
            '  "objections": "Objections raised and how to address them in Uzbek",\n'
            '  "buying_drivers": "Key buying drivers in Uzbek",\n'
            '  "close_probability": 85,\n'
            '  "next_task_text": "A highly personalized next action task in Uzbek based on calls and chat history",\n'
            '  "negotiation_strategy": "1. Birinchi qadam...\\n2. Ikkinchi qadam...\\n3. Uchinchi qadam..."\n'
            "}\n\n"
            f"--- AmoCRM Deal Info ---\n"
            f"Deal Name: {deal_info.get('name')}\n"
            f"Price: {deal_info.get('price')} so'm\n"
            f"Status ID: {deal_info.get('status_id')}\n\n"
            f"--- Airtable Project Status ---\n"
            f"{airtable_snippet}\n\n"
            f"--- AmoCRM Call Recordings ---\n"
            f"{call_snippet}\n\n"
            f"--- Telegram DM History ---\n"
            f"{history_snippet}"
        )

        try:
            from google.genai import types

            response = await asyncio.to_thread(
                self.genai_client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            raw_text = (response.text or "").strip()
            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"[AUDITOR] AI profile generation error: {e}")
            return {
                "psychotype": "Amiable",
                "pain_points": "N/A",
                "objections": "N/A",
                "buying_drivers": "Quality",
                "close_probability": 50,
                "next_task_text": "Mijoz bilan aloqaga chiqish va ehtiyojlarni aniqlash",
                "negotiation_strategy": "1. Muloqotni tiklash\n2. Ehtiyojlarni aniqlash\n3. Taklif berish",
            }

    async def audit_all_deals(self, limit: int = 500) -> Dict[str, Any]:
        """Pull 500 deals from AmoCRM, reconcile with local SQLite/Turso and Airtable, and generate the master intelligence report."""
        logger.info(f"🚀 [AUDITOR] Starting CRM 500 Intelligence Audit...")

        # 1. Fetch all detailed leads/deals from AmoCRM
        try:
            logger.info("[AUDITOR] Fetching detailed deals from AmoCRM...")
            leads = await self.amocrm.get_leads_detailed(limit=limit)
            if not leads:
                logger.warning("[AUDITOR] No active deals fetched or AmoCRM authentication is expired.")
                return {"success": False, "reason": "amocrm_auth_expired", "scanned": 0}
        except Exception as ae:
            logger.error(f"[AUDITOR] AmoCRM fetch error: {ae}")
            return {"success": False, "reason": f"amocrm_fetch_error: {ae}", "scanned": 0}

        # 2. Fetch all project records from Airtable
        airtable_projects = {}
        try:
            logger.info("[AUDITOR] Fetching active projects from Airtable...")
            projects = self.airtable.get_projects(force_refresh=True)
            for proj in projects:
                name = proj.get("project_name")
                if name:
                    airtable_projects[name.strip().lower()] = proj
        except Exception as arte:
            logger.warning(f"[AUDITOR] Airtable fetch skipped: {arte}")

        logger.info(f"[AUDITOR] Reconciling {len(leads)} leads against database history and Airtable...")

        results = []
        scanned = 0

        for lead in leads:
            lead_id = lead.get("id")
            if not lead_id:
                continue

            lead_name = lead.get("name", "N/A")
            price = lead.get("price", 0)

            # 3. Process and transcribe new call recordings for this lead
            try:
                logger.info(f"[AUDITOR] Scanning and transcribing call recordings for lead {lead_id}...")
                await self.call_analyzer.process_call_recordings_for_lead(int(lead_id))
            except Exception as e:
                logger.warning(f"[AUDITOR] Call processing failed for lead {lead_id}: {e}")

            # 4. Fetch all historic call transcripts from database
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

            # 5. Retrieve client contact details
            phone = await asyncio.to_thread(self.amocrm.get_lead_phone, int(lead_id))
            user_id = None
            dm_history = []

            # 6. Search user DM message logs in database
            if phone:
                try:
                    user_id = await self.db.get_user_id_by_phone(phone)
                    if user_id:
                        dm_history = await self.db.get_recent_messages(user_id=user_id, limit=30)
                except Exception as dbe:
                    logger.debug(f"[AUDITOR] Database history fetch skipped for {phone}: {dbe}")

            # 7. Search matching project in Airtable
            matched_project = None
            lead_name_clean = lead_name.strip().lower()
            if lead_name_clean in airtable_projects:
                matched_project = airtable_projects[lead_name_clean]
            else:
                # partial matching
                for proj_name, proj_data in airtable_projects.items():
                    if proj_name in lead_name_clean or lead_name_clean in proj_name:
                        matched_project = proj_data
                        break

            # 8. Generate AI intelligence profile based on Calls + DMs + Airtable
            logger.info(f"[AUDITOR] Processing client intelligence for '{lead_name}'...")
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

            # 9. Save to local/Turso user_intelligence table
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

            # 10. Upload structured note back to AmoCRM deal
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

            # 11. Append High Win Probability tag if applicable
            if close_prob >= 80:
                try:
                    await self.amocrm.add_lead_tag(int(lead_id), "High_Win_Prob")
                except Exception:
                    pass

            # 12. Create actual, actionable Task (Zadacha) in AmoCRM
            if next_task_text and next_task_text.upper() != "N/A":
                try:
                    import time
                    # Set due date 24 hours from now
                    complete_till = int(time.time()) + 24 * 3600
                    logger.info(f"[AUDITOR] Creating Strategic Task for lead {lead_id}: {next_task_text}")
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
            await asyncio.sleep(2.0)  # Safe delay to prevent AmoCRM rate limits

        # 10. Write master reports (JSON and CSV)
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
            
            logger.info(f"📊 [AUDITOR] Dashboard CSV created successfully: {csv_path}")
        except Exception as e:
            logger.error(f"[AUDITOR] Report save error: {e}")

        return {
            "success": True,
            "scanned": scanned,
            "json_path": json_path,
            "csv_path": csv_path,
        }
