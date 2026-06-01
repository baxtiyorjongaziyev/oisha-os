"""
ambassador_journey.py
~~~~~~~~~~~~~~~~~~~~~
Core service to manage the Ambassador Journey automation (Farmer strategy).
Tracks completed deals, schedules NPS surveys, generates personalized Uzbek outreach via Gemini,
and handles Telegram userbot dispatching.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.settings import settings

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None

logger = logging.getLogger(__name__)


class AmbassadorJourneyManager:
    """
    Orchestrates the lifecycle of Brand Ambassadors (Farmer strategy).
    Automates NPS surveys, referral tracking, and proactive customer relationship nurturing.
    """

    def __init__(
        self,
        amocrm: Any,
        db: Any,
        user_client: Optional[Any] = None,
        gemini_api_key: Optional[str] = None,
    ):
        self.amocrm = amocrm
        self.db = db
        self.user_client = user_client
        self.gemini_api_key = gemini_api_key
        self.gemini_model = os.getenv(
            "GEMINI_AMBASSADOR_MODEL", settings.GEMINI_CALL_MODEL
        )

        self.genai_client = None
        if gemini_api_key and genai is not None:
            try:
                self.genai_client = genai.Client(api_key=gemini_api_key)
            except Exception as e:
                logger.error(f"[AMBASSADOR] Failed to init Gemini GenAI client: {e}")

    async def sync_won_leads_to_ambassadors(self, limit: int = 50) -> Dict[str, Any]:
        """
        Scan recent AmoCRM deals, find successfully closed deals (status_id = 142),
        and synchronize them as Ambassadors in the local DB.
        """
        logger.info(f"[AMBASSADOR] Syncing won leads up to limit: {limit}...")
        try:
            leads = await self.amocrm.get_leads_detailed(limit=limit)
        except Exception as e:
            logger.error(f"[AMBASSADOR] Failed to fetch leads from AmoCRM: {e}")
            return {"synced": 0, "errors": 1}

        if not leads or not isinstance(leads, list):
            logger.info("[AMBASSADOR] No leads retrieved.")
            return {"synced": 0, "errors": 0}

        synced_count = 0
        for lead in leads:
            status_id = lead.get("status_id")
            # 142 is typical 'Successfully Realized' in AmoCRM
            if status_id != 142:
                continue

            lead_id = lead.get("id")
            if not lead_id:
                continue

            # Check if this contact has a valid phone
            phone = self._extract_phone(lead)
            phone_getter = getattr(self.amocrm, "get_primary_contact_phone", None)
            if not phone and callable(phone_getter):
                phone = await phone_getter(lead)
            contact_name = self._extract_contact_name(lead)
            brand_name = lead.get("name", "N/A")

            # Ambassador messages are Telegram actions, so schedule only when
            # the amoCRM contact can be mapped to a real local Telegram user.
            user_id = None
            if phone and hasattr(self.db, "get_user_id_by_phone"):
                user_id = await self.db.get_user_id_by_phone(phone)
            if not user_id:
                logger.info(
                    "[AMBASSADOR] Lead %s skipped: Telegram user not resolved from phone.",
                    lead_id,
                )
                continue
            
            # Upsert into local database
            try:
                # Attempt to update user status
                await self.db.update_lead_journey(
                    user_id=int(user_id),
                    stage="Ambassador",
                    status="active",
                    next_action="Send NPS Survey",
                    close_probability=100.0,
                )

                # Check if we already scheduled an NPS survey
                if not await self._has_nps_scheduled(int(user_id), int(lead_id)):
                    await self._schedule_nps_survey(int(user_id), int(lead_id), contact_name, brand_name)
                    synced_count += 1
            except Exception as e:
                logger.error(f"[AMBASSADOR] Error syncing lead {lead_id}: {e}")

        logger.info(f"[AMBASSADOR] Sync done. Added {synced_count} new Ambassador touchpoints.")
        return {"synced": synced_count, "errors": 0}

    async def generate_nps_survey_text(
        self, client_name: str, brand_name: str, service_type: str = "Branding"
    ) -> str:
        """
        Generate a warm, custom, highly-personalized Uzbek NPS outreach message via Gemini AI.
        """
        prompt = (
            f"Siz Jon Branding agency AI operatsion tizimi - Oishasiz. "
            f"Mijozimiz '{client_name}' uchun '{brand_name}' loyihasi doirasida '{service_type}' "
            f"ishlari muvaffaqiyatli yakunlandi va topshirildi. "
            f"Mijoz bilan aloqalarni mustahkamlash (Farmer strategy) va NPS (Net Promoter Score) ballini "
            f"aniqlash uchun juda samimiy, nafis, hurmat bilan yozilgan o'zbek tilidagi shaxsiy Telegram xabarini tayyorlang. "
            f"Xabarda quyidagilar bo'lishi shart:\n"
            f"1. Loyihani muvaffaqiyatli topshirilgani bilan samimiy tabrik.\n"
            f"2. Bizning xizmatlarimiz va natijalardan qanchalik mamnunligini 1 dan 10 gacha bo'lgan reytingda baholashini so'rash.\n"
            f"3. Uning har qanday taklif va mulohazalarini eshitishga tayyorligimiz.\n"
            f"4. Brendimizni boshqa hamkorlariga tavsiya qila olishi (referral) haqida chiroyli ishora.\n"
            f"Tonaliti: professional, samimiy, ulug'vor (elit) va do'stona. Emojilardan nafis foydalaning. "
            f"Jon Branding jamoasi va shaxsan CEO nomidan bo'lsin. Faqatgina yuboriladigan yakuniy xabar matnini qaytaring."
        )

        fallback_text = (
            f"Assalomu alaykum, {client_name}! 😊\n\n"
            f"Siz bilan '{brand_name}' loyihasi ustida ishlash biz uchun katta sharaf bo'ldi. "
            f"Hamkorligimiz natijasida yaratilgan yangi brendingiz muvaffaqiyatli rivojlanishini tilaymiz! ✨\n\n"
            f"Xizmatlarimiz sifatini yanada oshirish maqsadida biz bilan ishlash tajribangizni "
            f"1 dan 10 ballgacha baholasangiz, juda mamnun bo'lardik. Har qanday taklif va mulohazalaringiz biz uchun qimmatli. \n\n"
            f"Hurmat bilan,\nJon Branding jamoasi! 👑"
        )

        if not self.genai_client:
            logger.warning("[AMBASSADOR] Gemini client not initialized. Using fallback NPS text.")
            return fallback_text

        try:
            config = genai_types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=800,
            )
            response = await self.genai_client.aio.models.generate_content(
                model=self.gemini_model,
                contents=prompt,
                config=config,
            )
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as e:
            logger.error(f"[AMBASSADOR] Gemini NPS generation failed: {e}")

        return fallback_text

    async def process_scheduled_touchpoints(self) -> Dict[str, Any]:
        """
        Fetch all pending ambassador journey touchpoints, send automated Telegram nudges,
        and update statuses.
        """
        logger.info("[AMBASSADOR] Processing pending touchpoints...")
        conn = await self.db.get_connection()
        
        try:
            async with conn.execute(
                "SELECT id, user_id, lead_id, touchpoint_type, sent_message FROM ambassador_journey_logs WHERE status = 'pending'"
            ) as cursor:
                pending_jobs = await cursor.fetchall()
        except Exception as e:
            logger.error(f"[AMBASSADOR] Failed to read database logs: {e}")
            return {"sent": 0, "failed": 0}

        if not pending_jobs:
            logger.info("[AMBASSADOR] No pending touchpoints found.")
            return {"sent": 0, "failed": 0}

        logger.info(f"[AMBASSADOR] Found {len(pending_jobs)} pending touchpoint(s).")
        sent = 0
        failed = 0

        for row in pending_jobs:
            log_id, user_id, lead_id, touchpoint_type, message_text = (
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
            )

            logger.info(f"[AMBASSADOR] Dispatching {touchpoint_type} to user {user_id}...")
            
            telegram_sent = False
            # If userbot is available, try to send message via Telegram
            if self.user_client:
                try:
                    # Search for entity (can be phone, username, or peer ID)
                    # For simplicity, we fallback to log_manual if not found
                    entity = await self._resolve_telegram_entity(user_id)
                    if entity:
                        await self.user_client.send_message(entity, message_text)
                        telegram_sent = True
                        logger.info(f"✅ [AMBASSADOR] Proactive message sent to user {user_id} via Telegram.")
                    else:
                        logger.warning(f"[AMBASSADOR] Telegram entity not resolved for user {user_id}.")
                except Exception as tg_err:
                    logger.error(f"[AMBASSADOR] Userbot send failed for user {user_id}: {tg_err}")

            now = datetime.now().isoformat()
            new_status = "sent" if telegram_sent else "logged_manual"

            try:
                await conn.execute(
                    "UPDATE ambassador_journey_logs SET status = ?, sent_at = ? WHERE id = ?",
                    (new_status, now, log_id),
                )
                await conn.commit()
                if telegram_sent:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"[AMBASSADOR] Failed to update job {log_id}: {e}")
                failed += 1

            await asyncio.sleep(2.0)  # Rate limiting between Telegram nudges

        return {"sent": sent, "failed": failed}

    async def _has_nps_scheduled(self, user_id: int, lead_id: int) -> bool:
        conn = await self.db.get_connection()
        async with conn.execute(
            "SELECT 1 FROM ambassador_journey_logs WHERE user_id = ? AND lead_id = ? AND touchpoint_type = 'nps_survey'",
            (user_id, lead_id),
        ) as cursor:
            return bool(await cursor.fetchone())

    async def _schedule_nps_survey(self, user_id: int, lead_id: int, client_name: str, brand_name: str):
        logger.info(f"[AMBASSADOR] Generating and scheduling NPS survey for {client_name} (lead {lead_id})...")
        
        # 1. Generate Uzbek survey text via Gemini AI
        survey_message = await self.generate_nps_survey_text(
            client_name=client_name or "Mijoz",
            brand_name=brand_name or "Yangi Loyiha",
        )

        now = datetime.now().isoformat()
        conn = await self.db.get_connection()
        
        # 2. Insert as pending job
        await conn.execute(
            "INSERT INTO ambassador_journey_logs (user_id, lead_id, touchpoint_type, sent_message, status, scheduled_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, lead_id, "nps_survey", survey_message, "pending", now, now),
        )
        await conn.commit()
        logger.info(f"✅ [AMBASSADOR] Scheduled pending NPS survey in DB for user {user_id}.")

    async def _resolve_telegram_entity(self, user_id: int) -> Optional[Any]:
        """Attempt to resolve telegram entity using local username or phone."""
        conn = await self.db.get_connection()
        async with conn.execute(
            "SELECT username, phone FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                username, phone = row[0], row[1]
                if username:
                    try:
                        return await self.user_client.get_input_entity(username)
                    except Exception:
                        pass
                if phone:
                    try:
                        return await self.user_client.get_input_entity(phone)
                    except Exception:
                        pass
        return None

    def _extract_phone(self, lead: Dict[str, Any]) -> str:
        try:
            contacts = (
                lead.get("_embedded", {}).get("contacts", [])
                or lead.get("contacts", [])
            )
            for contact in contacts:
                fields = contact.get("custom_fields_values") or []
                for field in fields:
                    if str(field.get("field_code", "")).upper() == "PHONE":
                        vals = field.get("values") or []
                        if vals:
                            return str(vals[0].get("value", ""))
        except Exception:
            pass
        return ""

    def _extract_contact_name(self, lead: Dict[str, Any]) -> str:
        try:
            contacts = (
                lead.get("_embedded", {}).get("contacts", [])
                or lead.get("contacts", [])
            )
            if contacts:
                return str(contacts[0].get("name", ""))
        except Exception:
            pass
        return ""
