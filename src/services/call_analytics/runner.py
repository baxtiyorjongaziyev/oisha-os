import os
import re
import io
import time
import json
import logging
import asyncio
import hashlib
import inspect
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import structlog
import requests as _requests
from src.database import Database
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.stt_service import STTService
from src.services.core.call_events import CallEventLog
from src.services.core.call_analyses_schema import ensure_call_analysis_schema
from src.services.core.sales_playbook import (
    IDEAL_CLIENT_TALK_PCT,
    MAX_ACCEPTABLE_PAUSE_SECONDS,
    OUTCOME_LABELS_UZ,
    OUTCOME_UNKNOWN,
    STAGE_WEIGHTS,
    normalise_outcome,
    outcome_converted,
    outcome_prompt_uz,
    rubric_prompt_uz,
)
from src.services.utils.transcript import (
    detect_pauses,
    format_timestamp,
    has_timestamps,
    speaker_split,
    strip_timestamps,
    talk_ratio_verdict,
)
from src.time_utils import get_local_now, get_local_timezone
from src.services.call_analytics.helpers import *

logger = structlog.get_logger()

class CallRunnerMixin:
    def __init__(
        self,
        amocrm: AmoCRMSync,
        db: Database,
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
        """
        Process all unprocessed call recordings attached to one AmoCRM lead.
        Returns the number of successfully analyzed recordings.
        """
        await self._load_persisted_cooldown()
        if self._defer_calls_without_fallback():
            logger.info(
                "[CALL] Gemini quota cooldown active; deferring lead %s.",
                lead_id,
            )
            return 0

        try:
            notes = await _maybe_await(self.amocrm.get_lead_notes(lead_id))
        except Exception as exc:
            logger.error("[CALL] Failed to get notes for lead %s: %s", lead_id, exc)
            return 0

        if one_analysis_per_lead and self._lead_has_analysis(notes or []):
            logger.info("[CALL] Lead already has %s note: lead_id=%s", ANALYSIS_MARKER, lead_id)
            return 0

        call_notes = (
            call_notes_override
            if call_notes_override is not None
            else [note for note in (notes or []) if self._looks_like_call_note(note)]
        )
        if not call_notes:
            logger.info("[CALL] No call recording notes found for lead %s", lead_id)
            return 0

        processed = 0
        attempted = 0
        # Menejer ismi lead bo'yicha o'zgarmaydi — siklda qayta so'ramaymiz.
        manager_name = await self._resolve_manager_name(responsible_user_id)
        event_log = CallEventLog(self.db) if self.db else None

        for note in call_notes:
            audio_url = self._find_audio_url(note.get("params") or {})
            call_id = self._extract_call_id(note, lead_id, audio_url)
            duration = self._extract_call_duration_seconds(note)

            # HAR BIR qo'ng'iroq qayd etiladi — javobsizlari ham. Ilgari
            # yozuvsiz qo'ng'iroq shu yerda tashlanardi va telefon
            # ko'tarmaydigan sotuvchi statistikada umuman ko'rinmasdi.
            if write and event_log:
                params = note.get("params") or {}
                await event_log.record(
                    call_id=call_id,
                    lead_id=lead_id,
                    duration_seconds=duration,
                    has_recording=bool(audio_url),
                    manager_id=responsible_user_id,
                    manager_name=manager_name,
                    direction=str(note.get("note_type") or ""),
                    phone=caller_phone or self._extract_phone_from_note(note),
                    call_status=(
                        params.get("call_status") if isinstance(params, dict) else None
                    ),
                )

            if not audio_url:
                # Yozuv yo'q — tahlil qilib bo'lmaydi, lekin hodisa
                # yuqorida allaqachon qayd etildi.
                continue
            if self._note_has_analysis_for_call(notes or [], call_id):
                logger.info("[CALL] Lead note already contains analysis marker: lead_id=%s call_id=%s", lead_id, call_id)
                continue
            if await self._is_call_processed(call_id):
                logger.info("[CALL] Already processed: lead_id=%s call_id=%s", lead_id, call_id)
                continue

            if min_call_duration_seconds and duration and duration < min_call_duration_seconds:
                logger.info(
                    "[CALL] Skipping short call: lead_id=%s call_id=%s duration=%ss min=%ss",
                    lead_id,
                    call_id,
                    duration,
                    min_call_duration_seconds,
                )
                continue
            if max_calls_per_lead and attempted >= max_calls_per_lead:
                logger.info("[CALL] Max calls per lead reached: lead_id=%s max=%s", lead_id, max_calls_per_lead)
                break
            attempted += 1

            phone = caller_phone or self._extract_phone_from_note(note)
            fetch_result = await self._fetch_audio_bytes(audio_url)
            if not fetch_result:
                continue

            audio_bytes, mime_type = fetch_result
            size_mb = len(audio_bytes) / (1024 * 1024)
            if size_mb > self.max_audio_mb:
                logger.warning(
                    "[CALL] Audio too large: %.1f MB lead_id=%s call_id=%s",
                    size_mb,
                    lead_id,
                    call_id,
                )
                continue

            # --- METASELL SALESCOACH 24/7 AUTOMATION ---
            try:
                from src.services.core.salescoach_sync import get_salescoach_sync
                salescoach = get_salescoach_sync()
                if salescoach.enabled:
                    # Asynchronous upload so it doesn't block AmoCRM webhook
                    asyncio.create_task(
                        salescoach.upload_voice(
                            audio_bytes=audio_bytes,
                            customer_phone=phone,
                            content_type=mime_type,
                            ext=mime_type.split("/")[-1] if "/" in mime_type else "ogg",
                        )
                    )
            except Exception as exc:
                logger.warning(
                    "[CALL] Failed to queue audio for SalesCoach AI: %s",
                    exc
                )
            # ---------------------------------------------

            transcript = await self._transcribe_inline(audio_bytes, mime_type)
            if not transcript:
                continue

            # Jismoniy imkoniyat tekshiruvi: transkripsiya so'z soni
            # qo'ng'iroq davomiyligiga sig'masa — bu STT to'qigan matn
            # (real misol: 47s qo'ng'iroqqa ~250 so'zlik "suhbat")
            if _transcript_impossible_for_duration(transcript, duration):
                logger.warning(
                    "[CALL] Transkripsiya davomiylikka sig'maydi — hallucination deb rad etildi: "
                    "lead_id=%s call_id=%s duration=%ss words=%s",
                    lead_id,
                    call_id,
                    duration,
                    len(transcript.split()),
                )
                continue

            analysis = await self.analyze_transcript(transcript, duration)
            category = _normalise_category(analysis.get("category"))
            client_mood = _normalise_mood(analysis.get("client_mood"))
            summary = str(analysis.get("summary") or "").strip() or _clip(transcript, 350)
            next_steps = str(analysis.get("next_steps") or "N/A").strip() or "N/A"

            note1 = self._build_amocrm_note(
                analysis=analysis,
                transcript_snippet=transcript if include_transcript else "",
                caller_phone=phone,
                call_id=call_id,
                duration_seconds=duration,
            )
            note2 = self._build_client_profile_note(
                analysis=analysis,
                phone=phone,
                call_id=call_id,
                duration_seconds=duration,
            )
            note_texts = [note1, note2]

            if write:
                # Telegram approval flow — agar approval_service ulangan bo'lsa
                approval_service = getattr(self, "approval_service", None)
                if approval_service:
                    lead_name = str(lead_id)
                    try:
                        lead_info = await _maybe_await(self.amocrm.get_lead(lead_id))
                        if lead_info:
                            lead_name = lead_info.get("name") or str(lead_id)
                    except Exception as exc:
                        logger.error("[CALL] Failed to fetch lead name for %s: %s", lead_id, exc)

                    # DB'ga darhol yozish — restart'dan keyin ham deduplication ishlaydi.
                    # task_id yo'q bo'lganda None, qayta yozilishi mumkin emas.
                    await self._log_call_analysis(
                        call_id=call_id,
                        lead_id=lead_id,
                        category=category,
                        summary=summary,
                        client_mood=client_mood,
                        next_steps=next_steps,
                        transcript=transcript,
                        audio_url=audio_url,
                        caller_phone=phone,
                        task_id=None,
                        analysis=analysis,
                        duration_seconds=duration,
                        manager_id=responsible_user_id,
                        manager_name=manager_name,
                    )

                    try:
                        await _maybe_await(self.amocrm.add_lead_tag(lead_id, category))
                    except Exception as exc:
                        logger.error("[CALL] Failed to add tag to lead %s: %s", lead_id, exc)

                    await self._create_follow_up_task(
                        lead_id=lead_id,
                        category=category,
                        summary=summary,
                        client_mood=client_mood,
                        next_steps=next_steps,
                        responsible_user_id=responsible_user_id,
                        agreed_datetime=analysis.get("kelishilgan_vaqt"),
                    )

                    try:
                        await approval_service.send_for_approval(
                            lead_id=lead_id,
                            lead_name=lead_name,
                            phone=phone,
                            call_id=call_id,
                            analysis=analysis,
                            note_texts=note_texts,
                            call_duration=duration,
                        )
                    except Exception as exc:
                        logger.error("[CALL] Failed to send approval for lead %s: %s", lead_id, exc)
                else:
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
                        lead_id=lead_id,
                        category=category,
                        summary=summary,
                        client_mood=client_mood,
                        next_steps=next_steps,
                        responsible_user_id=responsible_user_id,
                        agreed_datetime=analysis.get("kelishilgan_vaqt"),
                    )

                    await self._log_call_analysis(
                        call_id=call_id,
                        lead_id=lead_id,
                        category=category,
                        summary=summary,
                        client_mood=client_mood,
                        next_steps=next_steps,
                        transcript=transcript,
                        audio_url=audio_url,
                        caller_phone=phone,
                        task_id=task_id,
                        analysis=analysis,
                        duration_seconds=duration,
                        manager_id=responsible_user_id,
                        manager_name=manager_name,
                    )

                    await self._notify_telegram_call_analysis(
                        lead_id=lead_id,
                        call_id=call_id,
                        category=category,
                        summary=summary,
                        client_mood=client_mood,
                        next_steps=next_steps,
                        duration_seconds=duration,
                        manager_name=manager_name,
                        caller_phone=phone,
                        analysis=analysis,
                        task_id=task_id,
                    )
            else:
                logger.info(
                    "[CALL] Dry-run analyzed: lead_id=%s call_id=%s category=%s summary=%s",
                    lead_id,
                    call_id,
                    category,
                    _clip(summary, 120),
                )

            processed += 1
            if write and event_log:
                await event_log.mark_analyzed(call_id)
            if one_analysis_per_lead:
                break
            await asyncio.sleep(0.5)

        return processed

    @staticmethod
    def _lead_has_analysis(notes: List[Dict[str, Any]]) -> bool:
        return any(ANALYSIS_MARKER in str((note.get("params") or {}).get("text") or "") for note in notes)

    @staticmethod
    def _note_has_analysis_for_call(notes: List[Dict[str, Any]], call_id: str) -> bool:
        if not call_id:
            return False
        return any(
            ANALYSIS_MARKER in str((note.get("params") or {}).get("text") or "")
            and f"Call ID: {call_id}" in str((note.get("params") or {}).get("text") or "")
            for note in notes
        )

    def _looks_like_call_note(self, note: Dict[str, Any]) -> bool:
        note_type = str(note.get("note_type") or "").lower()
        if note_type in _CALL_NOTE_TYPES:
            return True
        return self._find_audio_url(note.get("params") or {}, strict=True) is not None

    def _extract_call_id(self, note: Dict[str, Any], lead_id: int, audio_url: str) -> str:
        params = note.get("params") or {}
        for key in ("uniq", "call_id", "record_id", "recording_id", "phone_call_id"):
            value = params.get(key) if isinstance(params, dict) else None
            if value:
                return str(value)
        if note.get("id"):
            return str(note["id"])
        digest = hashlib.sha1(
            f"{lead_id}:{audio_url}".encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()[:16]
        return f"lead-{lead_id}-{digest}"

    @staticmethod
    def _extract_call_duration_seconds(note: Dict[str, Any]) -> int:
        params = note.get("params") or {}
        if not isinstance(params, dict):
            return 0
        for key in ("duration", "duration_seconds", "duration_sec", "call_duration"):
            value = params.get(key)
            if value is None:
                continue
            try:
                return max(0, int(float(value)))
            except (TypeError, ValueError):
                continue
        return 0

    def _extract_phone_from_note(self, note: Dict[str, Any]) -> str:
        params = note.get("params") or {}
        if not isinstance(params, dict):
            return ""
        for key in ("phone", "caller_phone", "source_phone", "from", "to"):
            value = params.get(key)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _extract_lead_phone(lead: Dict[str, Any]) -> str:
        try:
            contacts = lead.get("_embedded", {}).get("contacts", []) or lead.get("contacts", [])
            for contact in contacts:
                for field in contact.get("custom_fields_values") or []:
                    if str(field.get("field_code", "")).upper() == "PHONE":
                        values = field.get("values") or []
                        if values:
                            return str(values[0].get("value", ""))
        except Exception as exc:
            logger.error("[CALL] Failed to extract lead phone: %s", exc)
        return ""
