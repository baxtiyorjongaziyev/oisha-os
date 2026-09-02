"""
CRM lead lookup, task creation, note syncing, and admin notification mixin.
"""
from __future__ import annotations

import os
from typing import Any, List, Optional
import structlog

from src.services.core.meetings.models import (
    LEAD_TERMS,
    ContextMessage,
    MeetingCandidate,
)

logger = structlog.get_logger()


class MeetingCrmSyncMixin:
    """Handles CRM lead correlation, task scheduling in AmoCRM, and Telegram alerts."""

    async def _save_meeting_state(
        self, peer: Any, participant_name: str, candidate: MeetingCandidate
    ) -> None:
        user_id = getattr(peer, "id", None)
        if not user_id:
            return
        username = getattr(peer, "username", None)
        try:
            await self.db.upsert_user(
                user_id,
                participant_name,
                username=username,
                meeting_time=candidate.start_time.isoformat(),
                meeting_status="scheduled",
            )
        except Exception as exc:
            logger.debug(f"[MEETING] DB meeting state skipped: {exc}")

    async def _sync_crm_lead_if_needed(
        self,
        peer: Any,
        participant_name: str,
        messages: List[ContextMessage],
        candidate: MeetingCandidate,
    ) -> Optional[int]:
        if os.getenv("ENABLE_CALENDAR_CRM_SYNC", "1").strip().lower() in {
            "0",
            "false",
            "no",
            "off",
        }:
            return None
        if not self.amocrm:
            return None
        is_auth_blocked = getattr(self.amocrm, "is_auth_blocked", None)
        if callable(is_auth_blocked) and is_auth_blocked():
            logger.info("[MEETING] AmoCRM sync skipped: OAuth reauthorization required.")
            return None

        user_id = getattr(peer, "id", None)
        username = getattr(peer, "username", None)
        context_text = "\n".join(msg.text for msg in messages[-10:])
        lead_data = await self._detect_lead(context_text, peer, participant_name)
        if not lead_data.get("is_lead"):
            return None

        crm_key = f"calendar:crm_synced:{user_id or participant_name}:{candidate.start_time.isoformat()}"
        if self.db and str(await self.db.get_state(crm_key, "")):
            return None

        phone = (
            lead_data.get("phone")
            or getattr(peer, "phone", None)
            or ""
        )
        note = self._build_crm_note(
            participant_name=participant_name,
            username=username,
            candidate=candidate,
            context_text=context_text,
            lead_data=lead_data,
        )
        lead_name = f"Telegram Meeting Lead: {participant_name}"

        lead_id: Optional[int] = None
        try:
            if phone:
                task_result = await self._create_existing_lead_meeting_task(
                    phone=str(phone),
                    candidate=candidate,
                    participant_name=participant_name,
                    note=note,
                )
                lead_id = task_result
                if not lead_id:
                    lead_id = await self.amocrm.ensure_lead(
                        name=lead_name,
                        phone=str(phone),
                        note=note,
                    )
            if not lead_id and hasattr(self.amocrm, "create_standalone_lead"):
                lead_id = await self.amocrm.create_standalone_lead(
                    name=lead_name,
                    note=note,
                    tags=["TELEGRAM_MEETING_LEAD"],
                )
        except Exception as exc:
            logger.warning(f"[MEETING] AmoCRM lead sync failed: {exc}")
            return None

        if lead_id and self.db:
            await self.db.set_state(crm_key, str(lead_id))
            if user_id:
                try:
                    await self.db.set_state(f"crm:lead:{user_id}", str(lead_id))
                except Exception:
                    logger.warning("[MEETING] Failed to persist CRM lead state for user", exc_info=True)

        if lead_id:
            logger.info(f"[MEETING] AmoCRM meeting lead synced: {lead_id}")
        return lead_id

    async def _create_existing_lead_meeting_task(
        self,
        phone: str,
        candidate: MeetingCandidate,
        participant_name: str,
        note: str,
    ) -> Optional[int]:
        """Mavjud ochiq AmoCRM sdelka bo'lsa, yangi lead emas task yaratish."""
        task_text = self._build_meeting_task_text(candidate, participant_name)
        complete_till = int(candidate.start_time.timestamp())

        if hasattr(self.amocrm, "create_meeting_task_for_phone"):
            result = await self.amocrm.create_meeting_task_for_phone(
                phone=phone,
                task_text=task_text,
                complete_till=complete_till,
                note=note,
            )
            if isinstance(result, dict) and result.get("success"):
                return int(result["lead_id"])
            if (
                isinstance(result, dict)
                and result.get("reason") != "active_lead_not_found"
            ):
                raise RuntimeError(
                    f"existing_lead_task_failed:{result.get('reason') or 'unknown'}"
                )
            return None

        if not hasattr(self.amocrm, "find_active_lead_by_phone"):
            return None

        lead = self.amocrm.find_active_lead_by_phone(phone)
        if not lead:
            return None

        lead_id = int(lead["id"])
        if hasattr(self.amocrm, "create_task"):
            task = await self.amocrm.create_task(
                element_id=lead_id,
                text=task_text,
                complete_till=complete_till,
                responsible_user_id=lead.get("responsible_user_id"),
            )
            if not task:
                raise RuntimeError("existing_lead_task_failed")
        if hasattr(self.amocrm, "add_lead_note"):
            self.amocrm.add_lead_note(lead_id, note)
        return lead_id

    async def _detect_lead(
        self,
        context_text: str,
        peer: Any,
        participant_name: str,
    ) -> dict:
        profile = {
            "id": getattr(peer, "id", None),
            "first_name": participant_name,
            "username": getattr(peer, "username", None),
        }
        if self.lead_detector:
            try:
                lead_data = await self.lead_detector.extract_lead_info(
                    context_text, profile
                )
                if isinstance(lead_data, dict):
                    return lead_data
            except Exception as exc:
                logger.debug(f"[MEETING] Lead detector fallback: {exc}")

        lowered = context_text.lower()
        is_lead = any(term in lowered for term in LEAD_TERMS)
        return {
            "is_lead": is_lead,
            "intent_category": "MEETING_LEAD" if is_lead else "MEETING_ONLY",
            "needs": "Telegram suhbatida uchrashuv belgilandi",
        }

    def _build_crm_note(
        self,
        participant_name: str,
        username: Optional[str],
        candidate: MeetingCandidate,
        context_text: str,
        lead_data: dict,
    ) -> str:
        return (
            "Oisha: Telegram suhbatidan avtomatik uchrashuv/lead signali.\n"
            f"Mijoz: {participant_name}\n"
            f"Telegram: @{username or 'yoq'}\n"
            f"Uchrashuv vaqti: {candidate.start_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"Manzil: {candidate.location or 'korsatilmagan'}\n"
            f"Lead turi: {lead_data.get('intent_category', 'meeting_lead')}\n"
            f"Ehtiyoj: {lead_data.get('needs') or 'Uchrashuv belgilandi'}\n\n"
            f"Suhbat konteksti:\n{context_text[-1800:]}"
        )

    def _build_meeting_task_text(
        self, candidate: MeetingCandidate, participant_name: str
    ) -> str:
        location = candidate.location or "manzil ko'rsatilmagan"
        return (
            f"Uchrashuv: {participant_name} bilan "
            f"{candidate.start_time.strftime('%d.%m.%Y %H:%M')} da. "
            f"Manzil: {location}. Oisha Telegram suhbatidan avtomatik qo'ydi."
        )

    async def _notify_admin(
        self, candidate: MeetingCandidate, participant_name: str
    ) -> None:
        if not self.admin_notifier:
            return
        try:
            location_label = candidate.location or "Manzil ko'rsatilmagan"
            text = (
                "Oisha Google Calendar'ga uchrashuv qo'shdi\n"
                f"Mijoz: {participant_name}\n"
                f"Vaqt: {candidate.start_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"Manzil: {location_label}"
            )
            await self.admin_notifier.notify_lead(text)
        except Exception as exc:
            logger.debug(f"[MEETING] Admin notify skipped: {exc}")
