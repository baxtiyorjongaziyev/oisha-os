"""
AmoCRMLeadEnricher main coordinator.
"""
from __future__ import annotations

import inspect
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

try:
    from google import genai
except ImportError:
    genai = None

from src.settings import settings
from src.services.core.crm.enrichment.ai_synthesizer import AiSynthesizerMixin
from src.services.core.crm.enrichment.history_collector import HistoryCollectorMixin
from src.services.core.crm.enrichment.models import (
    LeadEnrichmentResult,
    _clip,
    _secret_to_text,
    maybe_await,
    normalize_phone,
)

logger = logging.getLogger("AmoCRMLeadEnrichment")


class AmoCRMLeadEnricher(HistoryCollectorMixin, AiSynthesizerMixin):
    """Enriches AmoCRM leads with Telegram private conversation history and AI analysis."""

    def __init__(
        self,
        amocrm: Any,
        db: Any = None,
        user_client: Any = None,
        gemini_api_key: Optional[str] = None,
        message_limit: Optional[int] = None,
        refresh_hours: Optional[int] = None,
        model_name: Optional[str] = None,
    ):
        self.amocrm = amocrm
        self.db = db
        self.user_client = user_client
        self.message_limit = int(
            message_limit
            if message_limit is not None
            else getattr(settings, "AMOCRM_ENRICHMENT_MESSAGE_LIMIT", 20)
        )
        self.refresh_hours = int(
            refresh_hours
            if refresh_hours is not None
            else getattr(settings, "AMOCRM_ENRICHMENT_REFRESH_HOURS", 24)
        )
        self.model_name = (
            model_name
            or os.getenv("GEMINI_AMOCRM_ENRICHMENT_MODEL")
            or settings.GEMINI_CALL_MODEL
        )

        api_key = (gemini_api_key or _secret_to_text(settings.GEMINI_API_KEY)).strip()
        self.genai_client = None
        if api_key and genai is not None:
            try:
                self.genai_client = genai.Client(api_key=api_key)
            except Exception as exc:
                logger.warning("[AMO_ENRICH] Gemini client init skipped: %s", exc)


    async def enrich_lead(
        self,
        lead_id: int,
        lead_data: Optional[Dict[str, Any]] = None,
        phone: Optional[str] = None,
        force: bool = False,
    ) -> LeadEnrichmentResult:
        lead_data = lead_data or {}
        normalized_phone = normalize_phone(phone)
        if not normalized_phone:
            return LeadEnrichmentResult(
                status="skipped",
                lead_id=int(lead_id),
                reason="phone_missing",
            )

        if not force and await self._recently_enriched(int(lead_id), normalized_phone):
            return LeadEnrichmentResult(
                status="skipped",
                lead_id=int(lead_id),
                phone=normalized_phone,
                reason="recently_enriched",
            )

        profile = await self._find_telegram_profile(normalized_phone)
        telegram_user_id = self._profile_user_id(profile)
        messages = await self._collect_messages(telegram_user_id)
        analysis = await self._build_analysis(
            lead_data=lead_data,
            phone=normalized_phone,
            profile=profile,
            messages=messages,
        )
        note = self._format_note(
            lead_id=int(lead_id),
            lead_data=lead_data,
            phone=normalized_phone,
            profile=profile,
            messages=messages,
            analysis=analysis,
        )

        note_result = await maybe_await(self.amocrm.add_lead_note(int(lead_id), note))
        note_added = bool(note_result)
        tags_added: List[str] = []

        if note_added:
            tags_added = await self._add_tags(int(lead_id), profile)
            await self._mark_enriched(
                lead_id=int(lead_id),
                phone=normalized_phone,
                telegram_user_id=telegram_user_id,
                message_count=len(messages),
            )

            # Auto-classify and tag lead automatically inside AmoCRM
            try:
                from src.services.core.crm.crm_contacts_auditor import CRMContactsAuditor
                auditor = CRMContactsAuditor(
                    amocrm=self.amocrm,
                    db=self.db,
                    tg_client=self.user_client,
                )
                category = await auditor.audit_lead_by_data(lead_data, force=force)
                if category and category != "skipped":
                    tags_added.append(category)
            except Exception as audit_exc:
                logger.error("[AMO_ENRICH] Auto-classification failed for lead %s: %s", lead_id, audit_exc)

        return LeadEnrichmentResult(
            status="enriched" if note_added else "failed",
            lead_id=int(lead_id),
            phone=normalized_phone,
            telegram_user_id=telegram_user_id,
            note_added=note_added,
            reason=None if note_added else "note_add_failed",
            tags_added=tags_added,
        )
