"""Uzbek Entrepreneurs Integration Handlers - AmoCRM and Telegram integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from src.database_pool import db_pool
from src.services.core.hisobchi_schema import ensure_hisobchi_db

logger = logging.getLogger(__name__)


@dataclass
class AmoCRMLead:
    entrepreneur_id: int
    full_name: str
    phone: str
    email: Optional[str]
    company: Optional[str]
    industry: Optional[str]
    country: str
    lead_score: int
    call_status: str
    call_notes: Optional[str]


class AmoCRMIntegration:
    """AmoCRM integration for Uzbek entrepreneurs leads."""

    def __init__(self, amocrm_client, db=None):
        self.amocrm = amocrm_client
        self._db = ensure_hisobchi_db(db if db is not None else db_pool)
        self._pipeline_id = None  # Configure this in settings
        self._status_id = None  # Configure this in settings

    async def create_lead_from_entrepreneur(
        self, entrepreneur_data: AmoCRMLead
    ) -> Optional[int]:
        """Create AmoCRM lead from entrepreneur data."""
        try:
            logger.info(
                "[AMOCRM] Creating lead for entrepreneur #%s: %s",
                entrepreneur_data.entrepreneur_id,
                entrepreneur_data.full_name,
            )

            # Create lead in AmoCRM
            lead_data = {
                "name": f"Uzbek Entrepreneur: {entrepreneur_data.full_name}",
                "pipeline_id": self._pipeline_id,
                "status_id": self._status_id,
                "custom_fields_values": [
                    {
                        "field_code": "PHONE",
                        "values": [{"value": entrepreneur_data.phone}],
                    },
                    {
                        "field_code": "EMAIL",
                        "values": [{"value": entrepreneur_data.email}],
                    },
                    {
                        "field_code": "COMPANY",
                        "values": [{"value": entrepreneur_data.company}],
                    },
                    {
                        "field_code": "INDUSTRY",
                        "values": [{"value": entrepreneur_data.industry}],
                    },
                    {
                        "field_code": "COUNTRY",
                        "values": [{"value": entrepreneur_data.country}],
                    },
                    {
                        "field_code": "LEAD_SCORE",
                        "values": [{"value": str(entrepreneur_data.lead_score)}],
                    },
                ],
                "notes": entrepreneur_data.call_notes or "",
            }

            # Call AmoCRM API
            response = await self.amocrm.create_lead(lead_data)

            if response and response.get("id"):
                lead_id = response["id"]

                # Update entrepreneur with AmoCRM lead ID
                await self._db.execute(
                    """
                    UPDATE uzbek_entrepreneurs
                    SET amocrm_lead_id = ?
                    WHERE id = ?
                    """,
                    [lead_id, entrepreneur_data.entrepreneur_id],
                )
                await self._db.commit()

                logger.info(
                    "[AMOCRM] Lead created: #%s → AmoCRM #%s",
                    entrepreneur_data.entrepreneur_id,
                    lead_id,
                )
                return lead_id

            return None

        except Exception as e:
            logger.error("[AMOCRM] Failed to create lead: %s", e)
            return None

    async def update_lead_status(
        self, entrepreneur_id: int, call_result: str, notes: Optional[str] = None
    ) -> bool:
        """Update AmoCRM lead status based on call result."""
        try:
            # Get AmoCRM lead ID
            rows = await self._db.execute(
                "SELECT amocrm_lead_id FROM uzbek_entrepreneurs WHERE id = ?",
                [entrepreneur_id],
            )

            if not rows or not rows[0]["amocrm_lead_id"]:
                logger.warning(
                    "[AMOCRM] No AmoCRM lead ID for entrepreneur #%s", entrepreneur_id
                )
                return False

            amo_lead_id = rows[0]["amocrm_lead_id"]

            # Map call result to AmoCRM status
            status_map = {
                "interested": "NEW_LEAD_STATUS_ID",  # Configure
                "callback": "CALLBACK_STATUS_ID",  # Configure
                "not_interested": "REJECTED_STATUS_ID",  # Configure
                "disconnected": "FAILED_STATUS_ID",  # Configure
            }

            status_id = status_map.get(call_result)
            if not status_id:
                logger.warning("[AMOCRM] Unknown call result: %s", call_result)
                return False

            # Update lead in AmoCRM
            await self.amocrm.update_lead(amo_lead_id, {"status_id": status_id})

            # Add note to lead
            if notes:
                await self.amocrm.add_note(
                    amo_lead_id, f"Call result: {call_result}. {notes}"
                )

            logger.info(
                "[AMOCRM] Updated lead #%s to status: %s", amo_lead_id, call_result
            )
            return True

        except Exception as e:
            logger.error("[AMOCRM] Failed to update lead: %s", e)
            return False


class TelegramIntegration:
    """Telegram integration for notifying operators and team."""

    def __init__(self, client, db=None):
        self.client = client
        self._db = ensure_hisobchi_db(db if db is not None else db_pool)
        self._notification_chat_id = None  # Configure in settings

    async def notify_operator_call_assigned(
        self, operator_id: int, entrepreneur_name: str, entrepreneur_phone: str
    ) -> bool:
        """Send notification to operator about assigned call."""
        try:
            # Get operator's Telegram ID
            rows = await self._db.execute(
                "SELECT telegram_id FROM call_operators WHERE id = ?",
                [operator_id],
            )

            if not rows:
                logger.warning("[TELEGRAM] Operator #%s not found", operator_id)
                return False

            telegram_id = rows[0]["telegram_id"]

            message = (
                f"📞 *Yangi qo'ng'iroq tayinlandi*\n\n"
                f"*Ism:* {entrepreneur_name}\n"
                f"*Telefon:* {entrepreneur_phone}\n\n"
                f"Qo'ng'iroq qiling va natijani kiriting."
            )

            await self.client.send_message(telegram_id, message, parse_mode="markdown")

            logger.info(
                "[TELEGRAM] Notified operator #%s about call: %s",
                operator_id,
                entrepreneur_name,
            )
            return True

        except Exception as e:
            logger.error("[TELEGRAM] Failed to notify operator: %s", e)
            return False

    async def notify_team_call_result(
        self, entrepreneur_name: str, call_result: str, notes: Optional[str] = None
    ) -> bool:
        """Send notification to team about call result."""
        try:
            if not self._notification_chat_id:
                logger.warning("[TELEGRAM] Notification chat ID not configured")
                return False

            emoji_map = {
                "interested": "✅",
                "callback": "📞",
                "not_interested": "❌",
                "disconnected": "📶",
            }

            emoji = emoji_map.get(call_result, "📞")

            message = (
                f"{emoji} *Qo'ng'iroq natijasi*\n\n"
                f"*Ism:* {entrepreneur_name}\n"
                f"*Natija:* {call_result}\n"
            )

            if notes:
                message += f"*Izoh:* {notes}\n"

            await self.client.send_message(
                self._notification_chat_id, message, parse_mode="markdown"
            )

            logger.info(
                "[TELEGRAM] Notified team about call result: %s - %s",
                entrepreneur_name,
                call_result,
            )
            return True

        except Exception as e:
            logger.error("[TELEGRAM] Failed to notify team: %s", e)
            return False

    async def send_daily_report(self, stats: dict) -> bool:
        """Send daily call campaign report to team."""
        try:
            if not self._notification_chat_id:
                return False

            message = (
                f"📊 *Kunlik qo'ng'iroq hisoboti*\n\n"
                f"Jami qo'ng'iroqlar: {stats.get('total', 0)}\n"
                f"Qiziqdi (1 bosdi): {stats.get('interested', 0)}\n"
                f"Qayta qo'ng'iroq (2 bosdi): {stats.get('callback', 0)}\n"
                f"Ulanmadi: {stats.get('disconnected', 0)}\n"
                f"Boshqa: {stats.get('called', 0)}\n"
            )

            await self.client.send_message(
                self._notification_chat_id, message, parse_mode="markdown"
            )

            logger.info("[TELEGRAM] Daily report sent")
            return True

        except Exception as e:
            logger.error("[TELEGRAM] Failed to send report: %s", e)
            return False


class UzbekEntrepreneurIntegrator:
    """Main integrator combining AmoCRM and Telegram."""

    def __init__(self, amocrm_client, telegram_client, db=None):
        self.amocrm = AmoCRMIntegration(amocrm_client, db)
        self.telegram = TelegramIntegration(telegram_client, db)
        self._db = ensure_hisobchi_db(db if db is not None else db_pool)

    async def process_call_result(
        self,
        entrepreneur_id: int,
        call_result: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Process call result - update AmoCRM and notify team."""
        try:
            # Get entrepreneur data
            rows = await self._db.execute(
                "SELECT full_name, call_status FROM uzbek_entrepreneurs WHERE id = ?",
                [entrepreneur_id],
            )

            if not rows:
                logger.warning("[INTEGRATOR] Entrepreneur #%s not found", entrepreneur_id)
                return False

            entrepreneur_name = rows[0]["full_name"]

            # Update AmoCRM lead
            await self.amocrm.update_lead_status(entrepreneur_id, call_result, notes)

            # Notify team
            await self.telegram.notify_team_call_result(
                entrepreneur_name, call_result, notes
            )

            logger.info(
                "[INTEGRATOR] Processed call result for #%s: %s",
                entrepreneur_id,
                call_result,
            )
            return True

        except Exception as e:
            logger.error("[INTEGRATOR] Failed to process call result: %s", e)
            return False

    async def sync_interested_to_amocrm(self) -> int:
        """Sync all interested entrepreneurs to AmoCRM."""
        try:
            rows = await self._db.execute(
                """
                SELECT id, full_name, phone, email, company, industry, country,
                       lead_score, call_status
                FROM uzbek_entrepreneurs
                WHERE call_status = 'interested' AND amocrm_lead_id IS NULL
                LIMIT 50
                """
            )

            synced_count = 0
            for row in rows:
                lead = AmoCRMLead(
                    entrepreneur_id=row["id"],
                    full_name=row["full_name"],
                    phone=row["phone"],
                    email=row["email"],
                    company=row["company"],
                    industry=row["industry"],
                    country=row["country"],
                    lead_score=row["lead_score"],
                    call_status=row["call_status"],
                    call_notes=None,
                )

                lead_id = await self.amocrm.create_lead_from_entrepreneur(lead)
                if lead_id:
                    synced_count += 1

            logger.info("[INTEGRATOR] Synced %s entrepreneurs to AmoCRM", synced_count)
            return synced_count

        except Exception as e:
            logger.error("[INTEGRATOR] Failed to sync to AmoCRM: %s", e)
            return 0
