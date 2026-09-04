"""
Call recording analysis orchestration and pipeline runner.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from src.services.call_analytics.helpers import (
    ANALYSIS_MARKER,
    _clip,
    _maybe_await,
    _transcript_impossible_for_duration,
)
from src.services.call_analytics.note_extractor import NoteExtractorMixin
from src.services.call_analytics.normalizer import (
    _normalise_category,
    _normalise_mood,
)
from src.services.core.call_events import CallEventLog

logger = logging.getLogger(__name__)


class CallRunnerMixin(NoteExtractorMixin):
    """Pipeline execution for processing call recordings from leads."""

    def __init__(
        self,
        amocrm: Any,
        db: Any = None,
        voice_processor: Any = None,
        gemini_client: Any = None,
        model_name: Optional[str] = None,
    ):
        self.amocrm = amocrm
        self.db = db
        self.voice_processor = voice_processor

        from src.settings import settings

        self._settings = settings
        self.model_name = (
            model_name
            or getattr(settings, "GEMINI_CALL_MODEL", "gemini-2.5-flash")
            or "gemini-2.5-flash"
        )
        self.max_audio_mb = int(getattr(settings, "AMOCRM_CALL_MAX_AUDIO_MB", 19) or 19)
        self.max_transcript_note_chars = int(
            getattr(settings, "AMOCRM_CALL_TRANSCRIPT_NOTE_CHARS", 6000) or 6000
        )
        self.create_tasks = bool(getattr(settings, "ENABLE_AMOCRM_CALL_TASKS", True))
        self.task_due_hours = int(getattr(settings, "AMOCRM_CALL_TASK_DUE_HOURS", 24) or 24)
        self._moizvonki_session = None
        self.gemini_cooldown_seconds = int(
            os.getenv("GEMINI_CALL_COOLDOWN_SECONDS", "900")
        )
        self._cooldown_loaded = False
        from src.services.utils.free_ai_router import get_free_ai_router

        self.free_ai_router = get_free_ai_router()

        self.genai_client = gemini_client
        if self.genai_client is None:
            api_key = ""
            try:
                api_key = settings.GEMINI_API_KEY.get_secret_value()
            except Exception as exc:
                logger.error("[CALL] Failed to read GEMINI_API_KEY: %s", exc)
                api_key = ""
            if api_key:
                from google import genai

                self.genai_client = genai.Client(api_key=api_key)

        self.openai_client = None
        openai_key = self._get_openai_api_key()
        if openai_key:
            try:
                from openai import OpenAI

                self.openai_client = OpenAI(api_key=openai_key)
            except Exception as exc:
                logger.warning("[CALL] OpenAI fallback client init failed: %s", exc)

    async def _fetch_and_filter_notes(
        self, lead_id: int, one_analysis_per_lead: bool, call_notes_override: Optional[List[Dict[str, Any]]]
    ) -> tuple[Optional[List[Dict[str, Any]]], List[Dict[str, Any]]]:
        try:
            notes = await _maybe_await(self.amocrm.get_lead_notes(lead_id))
        except Exception as exc:
            logger.error("[CALL] Failed to get notes for lead %s: %s", lead_id, exc)
            return None, []

        if one_analysis_per_lead and self._lead_has_analysis(notes or []):
            logger.info("[CALL] Lead already has %s note: lead_id=%s", ANALYSIS_MARKER, lead_id)
            return None, []

        call_notes = (
            call_notes_override
            if call_notes_override is not None
            else [note for note in (notes or []) if self._looks_like_call_note(note)]
        )
        return call_notes, (notes or [])

    async def _handle_audio_pipeline(
        self, audio_url: str, duration: int, phone: str, lead_id: int, call_id: str
    ) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        fetch_result = await self._fetch_audio_bytes(audio_url)
        if not fetch_result:
            return None, None

        audio_bytes, mime_type = fetch_result
        if (len(audio_bytes) / (1024 * 1024)) > self.max_audio_mb:
            logger.warning("[CALL] Audio too large lead_id=%s call_id=%s", lead_id, call_id)
            return None, None

        self._queue_salescoach_voice(audio_bytes, phone, mime_type)

        transcript = await self._transcribe_inline(audio_bytes, mime_type)
        if not transcript or _transcript_impossible_for_duration(transcript, duration):
            return None, None

        omnichannel_context = None
        try:
            from src.services.call_analytics.omnichannel_context import OmnichannelContextFetcher
            fetcher = OmnichannelContextFetcher(
                amocrm=self.amocrm,
                tg_client=getattr(self, "tg_client", None),
                db=self.db,
            )
            omnichannel_context = await fetcher.fetch_lead_omnichannel_context(
                lead_id=lead_id,
                caller_phone=phone,
            )
        except Exception as exc:
            logger.debug("[CALL] Omnichannel context fetch error for lead %s: %s", lead_id, exc)

        analysis = await self.analyze_transcript(
            transcript=transcript,
            duration_seconds=duration,
            omnichannel_context=omnichannel_context,
        )
        return transcript, analysis

    def _queue_salescoach_voice(self, audio_bytes: bytes, phone: str, mime_type: str) -> None:
        try:
            from src.services.core.salescoach_sync import get_salescoach_sync
            salescoach = get_salescoach_sync()
            if salescoach.enabled:
                asyncio.create_task(
                    salescoach.upload_voice(
                        audio_bytes=audio_bytes,
                        customer_phone=phone,
                        content_type=mime_type,
                        ext=mime_type.split("/")[-1] if "/" in mime_type else "ogg",
                    )
                )
        except Exception as exc:
            logger.warning("[CALL] Failed to queue audio for SalesCoach AI: %s", exc)

    async def _dispatch_approval_flow(
        self, lead_id: int, phone: str, call_id: str, duration: int,
        responsible_user_id: Optional[int], manager_name: str, audio_url: str,
        category: str, summary: str, client_mood: str, next_steps: str,
        transcript: str, analysis: Dict[str, Any], note_texts: List[str]
    ) -> None:
        lead_name = str(lead_id)
        try:
            lead_info = await _maybe_await(self.amocrm.get_lead(lead_id))
            if lead_info:
                lead_name = lead_info.get("name") or str(lead_id)
        except Exception as exc:
            logger.error("[CALL] Failed to fetch lead name for %s: %s", lead_id, exc)

        await self._log_call_analysis(
            call_id=call_id, lead_id=lead_id, category=category, summary=summary,
            client_mood=client_mood, next_steps=next_steps, transcript=transcript,
            audio_url=audio_url, caller_phone=phone, task_id=None, analysis=analysis,
            duration_seconds=duration, manager_id=responsible_user_id, manager_name=manager_name,
        )
        try:
            await _maybe_await(self.amocrm.add_lead_tag(lead_id, category))
        except Exception as exc:
            logger.error("[CALL] Failed to add tag to lead %s: %s", lead_id, exc)

        await self._create_follow_up_task(
            lead_id=lead_id, category=category, summary=summary, client_mood=client_mood,
            next_steps=next_steps, responsible_user_id=responsible_user_id,
            agreed_datetime=analysis.get("kelishilgan_vaqt"),
            conversion_advice=analysis.get("konversiya_tavsiyalari"),
        )
        try:
            await self.approval_service.send_for_approval(
                lead_id=lead_id, lead_name=lead_name, phone=phone, call_id=call_id,
                analysis=analysis, note_texts=note_texts, call_duration=duration,
            )
        except Exception as exc:
            logger.error("[CALL] Failed to send approval for lead %s: %s", lead_id, exc)

    async def _dispatch_direct_crm_write(
        self, lead_id: int, phone: str, call_id: str, duration: int,
        responsible_user_id: Optional[int], manager_name: str, audio_url: str,
        category: str, summary: str, client_mood: str, next_steps: str,
        transcript: str, analysis: Dict[str, Any], note_texts: List[str]
    ) -> None:
        for nt in note_texts:
            try:
                await asyncio.to_thread(self.amocrm.add_lead_note, lead_id, nt)
            except Exception as exc:
                logger.error("[CALL] Failed to add note to lead %s: %s", lead_id, exc)

        try:
            await _maybe_await(self.amocrm.add_lead_tag(lead_id, category))
        except Exception as exc:
            logger.error("[CALL] Failed to add tag to lead %s: %s", lead_id, exc)

        task_id = await self._create_follow_up_task(
            lead_id=lead_id, category=category, summary=summary, client_mood=client_mood,
            next_steps=next_steps, responsible_user_id=responsible_user_id,
            agreed_datetime=analysis.get("kelishilgan_vaqt"),
            conversion_advice=analysis.get("konversiya_tavsiyalari"),
        )
        await self._log_call_analysis(
            call_id=call_id, lead_id=lead_id, category=category, summary=summary,
            client_mood=client_mood, next_steps=next_steps, transcript=transcript,
            audio_url=audio_url, caller_phone=phone, task_id=task_id, analysis=analysis,
            duration_seconds=duration, manager_id=responsible_user_id, manager_name=manager_name,
        )
        await self._notify_telegram_call_analysis(
            lead_id=lead_id, call_id=call_id, category=category, summary=summary,
            client_mood=client_mood, next_steps=next_steps, duration_seconds=duration,
            manager_name=manager_name, caller_phone=phone, analysis=analysis, task_id=task_id,
        )
        await self._sync_call_to_customer_360(
            lead_id=lead_id, phone=phone, call_id=call_id, duration=duration,
            manager_name=manager_name, category=category, summary=summary,
            client_mood=client_mood, transcript=transcript, analysis=analysis,
        )

    async def _sync_call_to_customer_360(
        self, lead_id: int, phone: str, call_id: str, duration: int,
        manager_name: str, category: str, summary: str, client_mood: str,
        transcript: str, analysis: Dict[str, Any],
    ) -> None:
        try:
            from src.services.customer_360 import Customer360Collector, Customer360ObsidianSyncer
            collector = Customer360Collector(amocrm=self.amocrm, db=self.db)
            syncer = Customer360ObsidianSyncer()
            call_event = {
                "call_id": call_id,
                "duration_seconds": duration,
                "caller_phone": phone,
                "manager_name": manager_name,
                "category": category,
                "summary": summary,
                "client_mood": client_mood,
                "client_talk_pct": analysis.get("client_talk_pct", 50),
                "manager_talk_pct": analysis.get("manager_talk_pct", 50),
                "seller_score": analysis.get("seller_score"),
                "client_score": analysis.get("client_score"),
                "agreed_datetime": analysis.get("kelishilgan_vaqt"),
                "conversion_advice": analysis.get("konversiya_tavsiyalari"),
                "transcript": transcript,
            }
            profile = await collector.collect_profile(
                identifier=phone or str(lead_id),
                lead_id=lead_id,
                phone=phone,
                call_event=call_event,
            )
            await syncer.sync_profile(profile)
            logger.info(f"[CALL->C360] Customer 360 card synced for {profile.name} (#{lead_id})")
        except Exception as ex:
            logger.warning(f"[CALL->C360] Customer 360 sync error: {ex}")


    async def _process_single_call_note(
        self, note: Dict[str, Any], lead_id: int, notes: List[Dict[str, Any]],
        caller_phone: str, manager_name: str, responsible_user_id: Optional[int],
        write: bool, include_transcript: bool, min_call_duration_seconds: int, event_log: Any,
    ) -> bool:
        params = note.get("params") or {}
        audio_url = self._find_audio_url(note) or self._find_audio_url(params)
        call_id = self._extract_call_id(note, lead_id, audio_url)
        duration = self._extract_call_duration_seconds(note)
        phone = caller_phone or self._extract_phone_from_note(note)

        if write and event_log:
            await event_log.record(
                call_id=call_id, lead_id=lead_id, duration_seconds=duration,
                has_recording=bool(audio_url), manager_id=responsible_user_id,
                manager_name=manager_name, direction=str(note.get("note_type") or ""),
                phone=phone, call_status=params.get("call_status") if isinstance(params, dict) else None,
            )

        if not audio_url or self._note_has_analysis_for_call(notes, call_id) or await self._is_call_processed(call_id):
            return False
        if min_call_duration_seconds and duration and duration < min_call_duration_seconds:
            return False

        transcript, analysis = await self._handle_audio_pipeline(audio_url, duration, phone, lead_id, call_id)
        if not transcript or not analysis:
            return False

        category = _normalise_category(analysis.get("category"))
        client_mood = _normalise_mood(analysis.get("client_mood"))
        summary = str(analysis.get("summary") or "").strip() or _clip(transcript, 350)
        next_steps = str(analysis.get("next_steps") or "N/A").strip() or "N/A"

        note1 = self._build_amocrm_note(
            analysis=analysis, transcript_snippet=transcript if include_transcript else "",
            caller_phone=phone, call_id=call_id, duration_seconds=duration,
        )
        note2 = self._build_client_profile_note(
            analysis=analysis, phone=phone, call_id=call_id, duration_seconds=duration,
        )

        if write:
            if getattr(self, "approval_service", None):
                await self._dispatch_approval_flow(
                    lead_id, phone, call_id, duration, responsible_user_id, manager_name,
                    audio_url, category, summary, client_mood, next_steps, transcript,
                    analysis, [note1, note2],
                )
            else:
                await self._dispatch_direct_crm_write(
                    lead_id, phone, call_id, duration, responsible_user_id, manager_name,
                    audio_url, category, summary, client_mood, next_steps, transcript,
                    analysis, [note1, note2],
                )
            if event_log:
                await event_log.mark_analyzed(call_id)
        return True

    async def process_call_recordings_for_lead(
        self,
        lead_id: int,
        caller_phone: str = "",
        responsible_user_id: Optional[int] = None,
        write: bool = True,
        include_transcript: bool = True,
        one_analysis_per_lead: bool = False,
        max_calls_per_lead: int = 0,
        min_call_duration_seconds: int = 0,
        call_notes_override: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """Process all unprocessed call recordings attached to one AmoCRM lead."""
        await self._load_persisted_cooldown()
        if self._defer_calls_without_fallback():
            return 0

        call_notes, notes = await self._fetch_and_filter_notes(lead_id, one_analysis_per_lead, call_notes_override)
        if not call_notes:
            return 0

        processed = 0
        manager_name = await self._resolve_manager_name(responsible_user_id)
        event_log = CallEventLog(self.db) if self.db else None

        for note in call_notes:
            if max_calls_per_lead and processed >= max_calls_per_lead:
                break
            success = await self._process_single_call_note(
                note=note, lead_id=lead_id, notes=notes, caller_phone=caller_phone,
                manager_name=manager_name, responsible_user_id=responsible_user_id,
                write=write, include_transcript=include_transcript,
                min_call_duration_seconds=min_call_duration_seconds, event_log=event_log,
            )
            if success:
                processed += 1
            if one_analysis_per_lead:
                break
            await asyncio.sleep(0.5)
        return processed


CallAnalyzerRunnerMixin = CallRunnerMixin
