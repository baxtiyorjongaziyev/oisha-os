import asyncio
import hashlib
import io
import inspect
import json
import structlog
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests as _requests

from src.database import Database
from src.services.core.crm.amocrm_sync import AmoCRMSync
from src.services.core.stt_service import STTService
from src.services.core.call_analyses_schema import ensure_call_analysis_schema
from src.services.core.call_events import CallEventLog
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

logger = structlog.get_logger()

ANALYSIS_MARKER = "AI_CALL_ANALYSIS"
CATEGORIES = ["Shaxsiy", "Oila", "Jamoa", "Mijoz", "Boshqa"]
MOODS = ["Ijobiy", "Neytral", "Salbiy", "Noaniq"]
_WEEKDAY_UZ = [
    "Dushanba", "Seshanba", "Chorshanba", "Payshanba",
    "Juma", "Shanba", "Yakshanba",
]

# Kelishilgan vaqt shu oraliqdan tashqarida bo'lsa (o'tmishda yoki
# hallucination'ga o'xshab juda uzoq kelajakda), ishonchsiz deb rad etiladi.
_AGREED_TIME_MAX_DAYS_AHEAD = 60

_CALL_NOTE_TYPES = {
    "call_in",
    "call_out",
    "call",
    "amocrm_phone_call",
    "phone_call",
    "voip_call",
}

NO_SPEECH_SENTINEL = "[SUHBAT_ANIQLANMADI]"

_AUDIO_MIME_MAP = {
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".opus": "audio/ogg",
    ".webm": "audio/webm",
    ".amr": "audio/amr",
}

_AUDIO_URL_RE = re.compile(
    r"https?://[^\s\"'<>]+(?:mp3|mp4|m4a|ogg|wav|flac|aac|opus|webm|amr)(?:\?[^\s\"'<>]+)?",
    re.IGNORECASE,
)


class GeminiQuotaCooldownError(RuntimeError):
    """Raised when Gemini calls are intentionally paused after a quota error."""

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _detect_mime(url: str, content_type: Optional[str] = None) -> str:
    if content_type:
        ct = content_type.split(";", 1)[0].strip().lower()
        if ct.startswith("audio/") or ct in {"video/mp4", "video/webm"}:
            return ct

    path = url.split("?", 1)[0].lower()
    for ext, mime in _AUDIO_MIME_MAP.items():
        if path.endswith(ext):
            return mime
    return "audio/mpeg"


# So'zlovchi yorliqlari va nisbat mantiqi `services.utils.transcript` da —
# `quality_analyzer` ham aynan shu funksiyani ishlatadi.
_speaker_split = speaker_split


def _compute_talk_ratio(transcript: str) -> tuple[int, int]:
    """Back-compat wrapper: (client_pct, agent_pct) only."""
    client_pct, agent_pct, _ = _speaker_split(transcript)
    return client_pct, agent_pct


# Whisper-turkum ASR modellari sukunat/shovqinda ko'pincha shu qisqa,
# ma'nosiz iboralarni "eshitib" qaytaradi (yaxshi hujjatlashtirilgan
# hallucination artifaktlari). Gemini'ning maxsus sentinel'idan farqli
# o'laroq, bu — barcha STT provayderlariga (free_ai_router, OpenAI
# fallback) qo'llaniladigan umumiy himoya.
_STT_HALLUCINATION_PHRASES = {
    "you", "thank you", "thanks for watching", "thank you for watching",
    "bye", "goodbye", "subscribe", "silence", "music", "[music]",
    "rahmat", "xayr",
}


def _looks_like_stt_hallucination(text: str) -> bool:
    """Juda qisqa yoki ma'lum hallucination iboralariga mos matnni
    ishonchsiz deb belgilaydi — real qo'ng'iroq suhbati bunday bo'lmaydi."""
    if not text:
        return True
    normalised = text.strip().strip(".!?").lower()
    if normalised in _STT_HALLUCINATION_PHRASES:
        return True
    # Check for Gemini generic hallucinated dialogues
    cleaned = re.sub(r'\[\d{2}:\d{2}\]|a:|b:', '', normalised).strip()
    if len(cleaned.split()) < 15 and ('salom' in cleaned or 'qandaysiz' in cleaned or 'yaxshi' in cleaned):
        return True
    # Real ikki tomonlama suhbat deyarli hech qachon bir necha so'zdan
    # qisqa bo'lmaydi.
    if len(normalised) < 12:
        return True
    return False


def _transcript_impossible_for_duration(transcript: str, duration_seconds: int) -> bool:
    """Transkripsiya qo'ng'iroq davomiyligiga jismonan sig'maydimi?

    Real misol: 47 soniyalik qo'ng'iroq uchun Gemini ~250 so'zlik ravon
    "suhbat" to'qib bergan — uni ovoz chiqarib o'qish 2-3 daqiqa oladi.
    Tez nutq ~2.5 so'z/soniya; biz saxiy 4 so'z/soniya chegarasini
    olamiz — undan oshsa, matn haqiqiy audio'dan kelmagani aniq.
    """
    if not transcript or not duration_seconds or duration_seconds <= 0:
        return False
    # Vaqt belgisi ([00:03]) so'z emas — tozalamasak so'z soni shishadi va
    # haqiqiy transkripsiya "hallucination" deb rad etiladi.
    word_count = len(strip_timestamps(transcript).split())
    # Juda qisqa matnlarda nisbat shovqinli bo'ladi — 30 so'zgacha tekshirmaymiz
    if word_count <= 30:
        return False
    return word_count > duration_seconds * 4


_talk_ratio_verdict = talk_ratio_verdict


# Savdo rubrikasi mazmunli bo'lishi uchun minimal suhbat hajmi.
# Undan qisqa qo'ng'iroqda 6 bosqichning hech biri sodir bo'lolmaydi —
# 0/100 ko'rsatish sotuvchini asossiz ayblash bo'ladi.
_RUBRIC_MIN_WORDS = 40


def _rubric_applies(category: str, transcript: str) -> bool:
    """Jon Branding sotuv rubrikasi shu qo'ng'iroqqa taalluqlimi?"""
    if category != "Mijoz":
        return False
    # Vaqt belgilarisiz sanaymiz — aks holda qisqa suhbat uzun ko'rinadi.
    return len(strip_timestamps(transcript or "").split()) >= _RUBRIC_MIN_WORDS


def _parse_agreed_datetime(raw: Any, reference_now: Optional[datetime] = None) -> Optional[datetime]:
    """Suhbatda kelishilgan sana/vaqtni (AI "YYYY-MM-DD HH:MM" deb qaytargan)
    xavfsiz parse qiladi. Noto'g'ri format, o'tmish yoki hallucination'ga
    o'xshab juda uzoq kelajak (60 kundan ortiq) bo'lsa — None qaytaradi,
    chunki bunday holatlarda standart follow-up muddatiga tushish kerak."""
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text or text.lower() in {"null", "none", "yo'q", "yoq", "n/a", "na", "-"}:
        return None

    reference = reference_now or get_local_now()
    tz = get_local_timezone()
    parsed: Optional[datetime] = None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)

    if parsed <= reference:
        return None
    if parsed > reference + timedelta(days=_AGREED_TIME_MAX_DAYS_AHEAD):
        return None
    return parsed


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)].rstrip() + "\n...[qisqartirildi]"


def _parse_breakdown_time(raw: Any, duration_seconds: int = 0) -> Optional[str]:
    """LLM qaytargan uzilish vaqtini tekshiradi -> "mm:ss" yoki None.

    Ishonchsiz qiymatni rad etamiz: qo'ng'iroq davomiyligidan tashqaridagi
    lahza — LLM to'qigan raqam. Noto'g'ri lahzani ko'rsatish rahbarni
    yozuvning bo'sh joyiga yuboradi va butun funksiyaga ishonchni yo'qotadi.
    """
    if raw in (None, "", "null", "N/A"):
        return None
    match = re.match(r"^\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s*$", str(raw))
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    total = int(minutes) * 60 + int(seconds)
    if hours:
        total += int(hours) * 3600
    if duration_seconds and total > duration_seconds + 5:
        return None
    return format_timestamp(total)


def _extract_amocrm_task_id(result: Any) -> str:
    """Best-effort extraction for amoCRM task create responses."""
    if not result:
        return ""
    if isinstance(result, dict):
        direct = result.get("id")
        if direct:
            return str(direct)
        embedded = result.get("_embedded") or {}
        tasks = embedded.get("tasks") if isinstance(embedded, dict) else None
        if isinstance(tasks, list) and tasks:
            first = tasks[0] or {}
            if isinstance(first, dict) and first.get("id"):
                return str(first["id"])
    task_id = getattr(result, "id", None)
    return str(task_id) if task_id else ""


def _extract_json_object(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("empty Gemini response")
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def _normalise_category(value: Any) -> str:
    text = str(value or "").strip()
    for category in CATEGORIES:
        if text.lower() == category.lower():
            return category
    return "Boshqa"


def _normalise_mood(value: Any) -> str:
    text = str(value or "").strip().lower()
    mapping = {
        "positive": "Ijobiy",
        "ijobiy": "Ijobiy",
        "good": "Ijobiy",
        "happy": "Ijobiy",
        "neutral": "Neytral",
        "neytral": "Neytral",
        "negative": "Salbiy",
        "salbiy": "Salbiy",
        "bad": "Salbiy",
        "unknown": "Noaniq",
        "noaniq": "Noaniq",
        "unclear": "Noaniq",
    }
    return mapping.get(text, "Noaniq")


class CallAnalyzer:
    """
    AmoCRM call recording analyzer.

    The pipeline intentionally keeps audio in memory:
    AmoCRM note -> audio URL -> Gemini STT -> Uzbek transcript -> summary/tag/note.
    """

    _gemini_blocked_until = 0.0
    _GEMINI_COOLDOWN_KEY = "call_analyzer:gemini_blocked_until"

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

    @classmethod
    def _gemini_cooldown_remaining(cls) -> int:
        return max(0, int(cls._gemini_blocked_until - time.time()))

    @classmethod
    def _gemini_cooling_down(cls) -> bool:
        return cls._gemini_cooldown_remaining() > 0

    def _pause_gemini_for_quota(self) -> None:
        type(self)._gemini_blocked_until = (
            time.time() + self.gemini_cooldown_seconds
        )

    @staticmethod
    def _is_gemini_quota_error(error: Exception) -> bool:
        from src.services.utils.gemini_fallback import is_quota_error

        return is_quota_error(error)

    def _defer_calls_without_fallback(self) -> bool:
        return self._gemini_cooling_down() and not self.openai_client

    async def _load_persisted_cooldown(self) -> None:
        if self._cooldown_loaded:
            return
        self._cooldown_loaded = True
        get_state = getattr(self.db, "get_state", None)
        if not callable(get_state):
            return
        try:
            blocked_until = float(
                await _maybe_await(get_state(self._GEMINI_COOLDOWN_KEY, "0")) or 0
            )
            type(self)._gemini_blocked_until = max(
                type(self)._gemini_blocked_until,
                blocked_until,
            )
        except Exception as exc:
            logger.debug("[CALL] Gemini cooldown state load skipped: %s", exc)

    async def _persist_gemini_cooldown(self) -> None:
        set_state = getattr(self.db, "set_state", None)
        if not callable(set_state):
            return
        try:
            await _maybe_await(
                set_state(
                    self._GEMINI_COOLDOWN_KEY,
                    str(type(self)._gemini_blocked_until),
                )
            )
        except Exception as exc:
            logger.debug("[CALL] Gemini cooldown state write skipped: %s", exc)

    def _get_openai_api_key(self) -> str:
        value = os.getenv("OPENAI_API_KEY", "").strip()
        if value.lower().startswith("sk-place") or "placeholder" in value.lower():
            return ""
        if value:
            return value
        setting = getattr(self._settings, "OPENAI_API_KEY", None)
        if not setting:
            return ""
        try:
            value = (setting.get_secret_value() or "").strip()
        except Exception as exc:
            logger.warning("[CALL] Exception while reading OPENAI_API_KEY: %s", exc)
            value = str(setting or "").strip()
        if value.lower().startswith("sk-place") or "placeholder" in value.lower():
            return ""
        return value

    async def _is_call_processed(self, call_id: str) -> bool:
        """Return True when this AmoCRM call was already analyzed."""
        if not call_id or not self.db:
            return False
        try:
            conn = await self.db.get_connection()
            execute_result = conn.execute(
                "SELECT 1 FROM call_analyses WHERE call_id = ?", (call_id,)
            )
            if hasattr(execute_result, "__aenter__"):
                async with execute_result as cur:
                    return (await _maybe_await(cur.fetchone())) is not None

            cur = await _maybe_await(execute_result)
            return (await _maybe_await(cur.fetchone())) is not None
        except Exception as exc:
            logger.warning("[CALL] DB processed check failed for %s: %s", call_id, exc)
            return False

    async def _resolve_manager_name(self, responsible_user_id: Optional[int]) -> str:
        """AmoCRM mas'ul foydalanuvchi ID'sidan menejer ismi.

        Ism bo'lmasa murabbiylik qatlami qo'ng'iroqni hech kimga bog'lay
        olmaydi — shuning uchun ID bo'lsa ham hech bo'lmasa uni yozamiz.
        """
        if not responsible_user_id:
            return ""
        try:
            name = await _maybe_await(
                self.amocrm.get_user_name(int(responsible_user_id))
            )
        except Exception as exc:
            logger.warning(
                "[CALL] Menejer ismi olinmadi (user_id=%s): %s", responsible_user_id, exc
            )
            return ""
        return str(name or "").strip()

    async def _log_call_analysis(
        self,
        call_id: str,
        lead_id: int,
        category: str,
        summary: str,
        client_mood: str,
        next_steps: str,
        transcript: str,
        audio_url: str,
        caller_phone: str = "",
        task_id: str = "",
        analysis: Optional[Dict[str, Any]] = None,
        duration_seconds: int = 0,
        manager_id: Optional[int] = None,
        manager_name: str = "",
    ) -> None:
        """Tahlilni bazaga yozadi — BALLAR bilan birga.

        Ilgari bu yerga faqat matnli ustunlar tushardi; rubrik ballari
        AmoCRM notasida qolib ketardi va `sales_quality_coach` bo'sh
        ma'lumot ustida ishlardi. Endi murabbiylik qatlami o'qiydigan
        barcha ustunlar saqlanadi.
        """
        if not self.db:
            return

        await ensure_call_analysis_schema(self.db)

        analysis = analysis or {}
        rubrik = analysis.get("rubrik_baholar") or {}
        outcome = normalise_outcome(analysis.get("natija"))
        overall_score = int(analysis.get("sifat_bahosi") or 0)

        def _dump(value: Any) -> str:
            try:
                return json.dumps(value or [], ensure_ascii=False)
            except (TypeError, ValueError):
                return "[]"

        try:
            conn = await self.db.get_connection()
            now = datetime.now(timezone.utc).isoformat()
            task_created_at = now if task_id else None
            await _maybe_await(
                conn.execute(
                    """
                    INSERT OR IGNORE INTO call_analyses
                        (call_id, lead_id, category, summary, client_mood,
                         next_steps, transcript, audio_url, caller_phone,
                         task_id, task_created_at, analyzed_at, created_at, source,
                         manager_id, manager_name, duration_seconds, overall_score,
                         scores, strengths, weaknesses, objections, outcome,
                         converted, client_interest_level,
                         breakdown_at, breakdown_reason,
                         longest_pause_seconds, pauses)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?)
                    """,
                    (
                        call_id,
                        lead_id,
                        category,
                        summary,
                        client_mood,
                        next_steps,
                        transcript,
                        audio_url,
                        caller_phone,
                        task_id,
                        task_created_at,
                        now,
                        now,
                        "amocrm",
                        int(manager_id) if manager_id else None,
                        manager_name,
                        max(int(duration_seconds or 0), 0),
                        overall_score,
                        _dump(rubrik) if rubrik else "{}",
                        _dump(analysis.get("kuchli_tomonlar")),
                        _dump(analysis.get("zaif_tomonlar")),
                        _dump(analysis.get("etirozlar")),
                        outcome,
                        1 if outcome_converted(outcome) else 0,
                        int(analysis.get("lead_bahosi") or 0),
                        analysis.get("uzilish_vaqti"),
                        str(analysis.get("uzilish_sababi") or ""),
                        float(analysis.get("eng_uzun_pauza") or 0.0),
                        _dump(analysis.get("pauzalar")),
                    ),
                )
            )
            await _maybe_await(conn.commit())
            logger.info(
                "[CALL] DB log saved: lead_id=%s call_id=%s ball=%s natija=%s menejer=%s",
                lead_id,
                call_id,
                overall_score,
                outcome,
                manager_name or "?",
            )
        except Exception as exc:
            logger.error("[CALL] DB log failed for %s: %s", call_id, exc)

    def _login_moizvonki(self):
        email = getattr(self._settings, "MOIZVONKI_EMAIL", None)
        password = getattr(self._settings, "MOIZVONKI_PASSWORD", None)
        if not email or not password:
            logger.warning("[CALL] Moizvonki credentials not configured")
            return None

        session = _requests.Session()
        login_url = f"https://{self.amocrm.subdomain}.moizvonki.ru/accounts/login/"
        try:
            r = session.get(login_url, timeout=30)
            csrf_token = session.cookies.get("csrftoken")
            csrf_mid = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']', r.text)
            csrf_val = csrf_mid.group(1) if csrf_mid else csrf_token

            login_data = {
                "csrfmiddlewaretoken": csrf_val,
                "username": email,
                "password": password.get_secret_value() if hasattr(password, "get_secret_value") else password,
                "foreign_pc": "on"
            }
            headers = {
                "Referer": login_url,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            r_post = session.post(login_url, data=login_data, headers=headers, timeout=30)
            if r_post.status_code == 200 and "sessionid" in session.cookies:
                logger.info("[CALL] Moizvonki login successful")
                return session
            else:
                logger.error("[CALL] Moizvonki login failed: status=%s cookies=%s", r_post.status_code, session.cookies.get_dict())
                return None
        except Exception as exc:
            logger.error("[CALL] Moizvonki login exception: %s", exc)
            return None

    async def _fetch_audio_bytes(self, url: str) -> Optional[Tuple[bytes, str]]:
        """Download an AmoCRM recording into memory."""
        # Check if URL belongs to Moizvonki and needs session authentication
        is_moizvonki = "moizvonki.ru" in url or "moizvonki" in url
        
        headers_auth = {}
        get_headers = getattr(self.amocrm, "_get_headers", None)
        if callable(get_headers):
            try:
                headers_auth = get_headers() or {}
            except Exception as exc:
                logger.error("[CALL] Exception fetching AmoCRM headers: %s", exc)
                headers_auth = {}

        def _get(headers: Dict[str, str], session: Optional[_requests.Session] = None):
            if is_moizvonki and session:
                return session.get(url, timeout=90, stream=False)
            return _requests.get(url, headers=headers, timeout=90, stream=False)

        try:
            resp = None
            if is_moizvonki:
                if not self._moizvonki_session:
                    self._moizvonki_session = self._login_moizvonki()
                if self._moizvonki_session:
                    resp = await asyncio.to_thread(_get, {}, self._moizvonki_session)
                    # If session expired, try re-login once
                    if resp and (resp.status_code != 200 or len(resp.content) == 60027):
                        logger.info("[CALL] Moizvonki session expired or dummy received, retrying login")
                        self._moizvonki_session = self._login_moizvonki()
                        if self._moizvonki_session:
                            resp = await asyncio.to_thread(_get, {}, self._moizvonki_session)

            if not resp or resp.status_code != 200:
                resp = await asyncio.to_thread(_get, headers_auth)
                if resp.status_code != 200:
                    resp = await asyncio.to_thread(_get, {})

            if resp.status_code == 200 and resp.content:
                if len(resp.content) == 60027:
                    logger.warning("[CALL] Audio fetch returned Moizvonki dummy audio (60027 bytes). Rejecting. url=%s", url)
                    return None
                
                content_type = (resp.headers.get("Content-Type") or "").lower()
                prefix = resp.content[:64].lstrip()
                if (
                    not content_type.startswith(("audio/", "video/"))
                    and (prefix.startswith(b"{") or prefix.startswith(b"<"))
                ):
                    logger.warning(
                        "[CALL] Recording URL returned non-audio payload: content_type=%s url=%s",
                        content_type,
                        url,
                    )
                    return None
                mime = _detect_mime(url, resp.headers.get("Content-Type"))
                return resp.content, mime

            logger.warning("[CALL] Audio fetch failed: http=%s url=%s", getattr(resp, 'status_code', 'None'), url)
            return None
        except Exception as exc:
            logger.error("[CALL] Audio fetch exception for %s: %s", url, exc)
            return None

    async def _gemini_generate_content(self, *, contents: Any, config: Any = None) -> Any:
        if not self.genai_client:
            raise RuntimeError("Gemini client is not configured")
        await self._load_persisted_cooldown()
        if self._gemini_cooling_down():
            raise GeminiQuotaCooldownError("Gemini quota cooldown is active")

        try:
            from src.services.utils.gemini_fallback import generate_content_with_fallback

            response, _ = await generate_content_with_fallback(
                self.genai_client,
                primary_model=self.model_name,
                contents=contents,
                config=config,
                env_name="GEMINI_CALL_FALLBACK_MODELS",
                log_prefix="[CALL]",
            )
            return response
        except Exception as exc:
            if self._is_gemini_quota_error(exc):
                self._pause_gemini_for_quota()
                await self._persist_gemini_cooldown()
                logger.warning(
                    "[CALL] Gemini quota exhausted; pausing calls for %ss.",
                    self.gemini_cooldown_seconds,
                )
                raise GeminiQuotaCooldownError(
                    "Gemini quota cooldown started"
                )

    async def _transcribe_inline(self, audio_bytes: bytes, mime_type: str) -> Optional[str]:
        """Transcribe audio using STTService, fallback to Gemini, then OpenAI."""
        # Removed duplicate import; STTService is imported at module level
        from google.genai import types

        # 1. Try STTService
        try:
            stt_service = STTService()
            result = await stt_service.transcribe(audio_bytes, mime_type)
            if result and result.transcript:
                return result.transcript
        except Exception as exc:
            logger.warning("[CALL] STTService failed: %s", exc)

        # 2. Try Gemini fallback
        prompt = (
            "Siz professional qo'ng'iroq transkripsiya mutaxassisisiz. "
            "Audio yozuvni eshiting va suhbatni O'zbek lotinida yozing.\n\n"
            "QOIDALAR:\n"
            "- Faqat audio faylda HAQIQATDA eshitilgan gaplarni yozing.\n"
            "- Agar tushunarli nutq bo'lmasa, qaytaring: {NO_SPEECH_SENTINEL}\n"
            "- Har bir gapni [mm:ss] vaqt belgisi bilan boshlang.\n"
            "- A: va B: deb ajrating."
        )
        try:
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            response = await self._gemini_generate_content(
                contents=[prompt, audio_part],
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=8192),
            )
            text = (getattr(response, "text", None) or "").strip()
            if text and NO_SPEECH_SENTINEL not in text:
                return text
        except Exception as exc:
            logger.error("[CALL] Gemini STT fallback failed: %s", exc)

        # 3. Final fallback to OpenAI
        return await self._transcribe_openai(audio_bytes, mime_type)

    async def _transcribe_openai(
        self, audio_bytes: bytes, mime_type: str
    ) -> Optional[str]:
        """Fallback STT via OpenAI when Gemini audio quota is unavailable."""
        if not bool(getattr(self._settings, "ENABLE_PAID_AI_FALLBACK", False)):
            return None
        if not self.openai_client:
            return None

        extension = {
            "audio/mpeg": "mp3",
            "audio/mp4": "m4a",
            "audio/ogg": "ogg",
            "audio/wav": "wav",
            "audio/flac": "flac",
            "audio/aac": "aac",
            "audio/webm": "webm",
            "audio/amr": "amr",
        }.get(mime_type, "mp3")
        file_obj = io.BytesIO(audio_bytes)
        file_obj.name = f"amocrm-call.{extension}"
        model = getattr(self._settings, "OPENAI_TRANSCRIBE_MODEL", "whisper-1")

        def _create():
            return self.openai_client.audio.transcriptions.create(
                model=model,
                file=file_obj,
                language="uz",
                prompt=(
                    "Telefon qo'ng'irog'i. Suhbatni imkon qadar O'zbek lotinida "
                    "transkripsiya qiling. Ismlar, narxlar va vazifalarni saqlang."
                ),
                response_format="text",
            )

        try:
            response = await asyncio.to_thread(_create)
            text = response if isinstance(response, str) else getattr(response, "text", "")
            text = (text or "").strip()
            if text and _looks_like_stt_hallucination(text):
                logger.info("[CALL] OpenAI Whisper: shubhali/hallucination-o'xshash natija rad etildi: %r", text[:60])
                return None
            if text:
                logger.info("[CALL] OpenAI STT fallback done: %s chars", len(text))
                return text
            return None
        except Exception as exc:
            logger.error("[CALL] OpenAI STT fallback failed: %s", exc)
            return None

    async def analyze_transcript(
        self, transcript: str, duration_seconds: int = 0
    ) -> Dict[str, Any]:
        """Classify, summarize, and extract next steps from a transcript."""
        if not transcript:
            return self._fallback_analysis(transcript)

        try:
            from google.genai import types

            client_pct, agent_pct, attributed = _speaker_split(transcript)
            ratio_line = (
                f"  Mijoz: {client_pct}%  |  Sotuvchi: {agent_pct}%\n"
                if attributed
                else "  Aniqlanmadi — transkripsiyada rollar belgilanmagan.\n"
            )
            now_local = get_local_now()
            prompt = (
                "Quyidagi telefon suhbati transkripsiyasini professional savdo tahlilchisi sifatida tahlil qiling.\n\n"
                f"HOZIRGI SANA VA VAQT (Toshkent): {now_local.strftime('%Y-%m-%d %H:%M')} "
                f"({_WEEKDAY_UZ[now_local.weekday()]})\n"
                "Transkripsiyada nisbiy vaqt aytilsa (\"ertaga\", \"peshin\", \"kelasi hafta\", "
                "\"dushanba\"), shu hozirgi sanaga nisbatan hisoblang.\n\n"
                "TOIFALAR (faqat bittasini tanlang):\n"
                "- Shaxsiy: shaxsiy, biznesga aloqasi yo'q suhbat.\n"
                "- Oila: oila a'zolari, uy ishlari, bolalar yoki qarindoshlar haqida.\n"
                "- Jamoa: xodimlar, ichki ishlar, vazifa, deadline, operatsion muhokama.\n"
                "- Mijoz: brending, dizayn, SMM, sayt, loyiha, narx, savdo yoki mijoz muzokarasi.\n"
                "- Boshqa: aralash, spam yoki yuqoridagilarga aniq kirmaydigan qo'ng'iroq.\n\n"
                "GAPIRISH NISBATI (hisoblangan):\n"
                f"{ratio_line}"
                f"  Ideal: mijoz ≥{IDEAL_CLIENT_TALK_PCT}%.\n\n"
                f"{rubric_prompt_uz()}\n"
                f"{outcome_prompt_uz()}\n"
                "Rubrik faqat Mijoz toifasiga taalluqli. Agar toifa Mijoz emas "
                "(Shaxsiy, Oila, Jamoa, Boshqa) bo'lsa — rubrik_baholar uchun "
                "umumiy muloqot sifatiga qarab baholang.\n\n"
                "Javobni faqat JSON formatida qaytaring:\n"
                "{\n"
                '  "summary": "2-4 gapda O\'zbekcha xulosa",\n'
                '  "category": "Shaxsiy|Oila|Jamoa|Mijoz|Boshqa",\n'
                '  "client_mood": "Ijobiy|Neytral|Salbiy|Noaniq",\n'
                '  "next_steps": "Keyingi aniq qadamlar yoki N/A",\n'
                '  "kelishilgan_vaqt": "Agar suhbatda aniq kun/soat kelishilgan bo\'lsa '
                '(masalan \'ertaga soat 15da\', \'dushanba peshin\'), uni YYYY-MM-DD HH:MM '
                'formatida yozing (hozirgi sanaga nisbatan hisoblab). Aniq vaqt aytilmagan '
                'bo\'lsa — null.",\n'
                f'  "client_talk_pct": {client_pct},\n'
                f'  "agent_talk_pct": {agent_pct},\n'
                '  "lead_bahosi": <0-100: lead potensiali — qiziqish, byudjet, qaror qabul qilish>,\n'
                '  "suhbat_oilasi": "Ehtiyoj aniqlash|Yechim taqdimoti|Narx muhokamasi|Follow-up|Shartnoma|Boshqa",\n'
                '  "suhbat_domeni": "Savdo|Mijoz xizmati|Loyiha muhokamasi|Texnik|Boshqa",\n'
                '  "baholash_rejimi": "Savdo playbook boyicha baholanadi|Xizmat standarti|Loyiha boshqaruvi|Boshqa",\n'
                '  "biznes_mosligi": "Biznesga mos|Qisman mos|Mos emas",\n'
                '  "servis_yonalishi": "Brending|Dizayn|SMM|Sayt|Biznes transformatsiya|Reklama|Boshqa",\n'
                '  "mijoz_lavozimi": "lavozim yoki N/A",\n'
                '  "mijoz_kompaniya": "kompaniya nomi yoki N/A",\n'
                '  "qaror_qabul_qiluvchi": "Ha|Yoq|Noaniq",\n'
                '  "joylashuv": "shahar/viloyat yoki N/A",\n'
                '  "mijoz_malumotlari": ["mijoz haqida muhim ma\'lumot 1", "muhim ma\'lumot 2"],\n'
                '  "natija": "yuqoridagi natija kalitlaridan bittasi",\n'
                '  "uzilish_vaqti": "Agar suhbat biror lahzada BUZILGAN bo\'lsa '
                '(mijoz qiziqishdan qolgan, e\'tiroz javobsiz qolgan, savdo uzilgan) '
                '— o\'sha gapning vaqt belgisini \"mm:ss\" formatida yozing. '
                'Suhbat yaxshi ketgan yoki lahzani aniqlab bo\'lmasa — null.",\n'
                '  "uzilish_sababi": "Uzilish lahzasida AYNAN nima noto\'g\'ri ketdi '
                '(masalan: \"Ehtiyoj aniqlanmadi\", \"E\'tirozga javob berilmadi\"). '
                'uzilish_vaqti null bo\'lsa — null.",\n'
                '  "kuchli_tomonlar": ["menejer aynan nimani YAXSHI qildi (1-3 ta, aniq)"],\n'
                '  "zaif_tomonlar": ["menejer nimani o\'tkazib yubordi yoki xato qildi '
                '(1-3 ta, aniq va tuzatib bo\'ladigan)"],\n'
                '  "etirozlar": ["mijoz bildirgan e\'tirozlar, masalan \'qimmat\'"],\n'
                '  "rubrik_baholar": {\n'
                '    "salomlashish": {"ball": <0-100>},\n'
                '    "ehtiyojlar": {"ball": <0-100>},\n'
                '    "qiymat": {"ball": <0-100>},\n'
                '    "etirozlar": {"ball": <0-100>},\n'
                '    "yakunlash": {"ball": <0-100>},\n'
                '    "muloqot_sifati": {"ball": <0-100>}\n'
                '  }\n'
                "}\n\n"
                f"Transkripsiya:\n{transcript}"
            )
            response = await self._gemini_generate_content(
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            data = _extract_json_object(getattr(response, "text", "") or "")
            return self._normalise_analysis(data, transcript, duration_seconds)
        except GeminiQuotaCooldownError:
            logger.info("[CALL] Gemini transcript analysis skipped during quota cooldown.")
            openai_analysis = await self._analyze_transcript_openai(
                transcript, duration_seconds
            )
            if openai_analysis:
                return openai_analysis
            return self._fallback_analysis(transcript)
        except Exception as exc:
            logger.error("[CALL] Transcript analysis failed: %s", exc)
            openai_analysis = await self._analyze_transcript_openai(
                transcript, duration_seconds
            )
            if openai_analysis:
                return openai_analysis
            return self._fallback_analysis(transcript)

    async def _analyze_transcript_openai(
        self, transcript: str, duration_seconds: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Fallback JSON analysis via OpenAI text model."""
        if not self.openai_client:
            return None

        model = getattr(self._settings, "OPENAI_TEXT_MODEL", "gpt-4o-mini")
        system = (
            "Siz O'zbek tilida ishlaydigan amoCRM qo'ng'iroq tahlilchisisiz. "
            "Faqat JSON qaytaring."
        )
        now_local = get_local_now()
        user = (
            "Telefon suhbati transkripsiyasini tahlil qiling.\n"
            f"Hozirgi sana va vaqt (Toshkent): {now_local.strftime('%Y-%m-%d %H:%M')}\n"
            "Toifalar: Shaxsiy, Oila, Jamoa, Mijoz, Boshqa.\n"
            "Kayfiyat: Ijobiy, Neytral, Salbiy, Noaniq.\n"
            "JSON schema: summary, category, client_mood, next_steps, "
            "kelishilgan_vaqt (suhbatda aniq kun/soat kelishilgan bo'lsa "
            "\"YYYY-MM-DD HH:MM\" formatida, aks holda null).\n\n"
            f"Transkripsiya:\n{transcript}"
        )

        def _create():
            return self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )

        try:
            response = await asyncio.to_thread(_create)
            raw = response.choices[0].message.content if response.choices else ""
            data = _extract_json_object(raw or "")
            return self._normalise_analysis(data, transcript, duration_seconds)
        except Exception as exc:
            logger.error("[CALL] OpenAI analysis fallback failed: %s", exc)
            return None

    def _normalise_analysis(
        self, data: Dict[str, Any], transcript: str, duration_seconds: int = 0
    ) -> Dict[str, Any]:
        summary = str(data.get("summary") or "").strip()
        next_steps = str(data.get("next_steps") or "N/A").strip() or "N/A"
        agreed_datetime = _parse_agreed_datetime(data.get("kelishilgan_vaqt"))
        computed_client, computed_agent, attributed = _speaker_split(transcript)
        client_pct = int(data.get("client_talk_pct") or computed_client)
        agent_pct = int(data.get("agent_talk_pct") or computed_agent)

        def _clamp_score(val: Any) -> int:
            try:
                return max(0, min(100, int(val)))
            except (TypeError, ValueError):
                return 0

        mijoz_info = data.get("mijoz_malumotlari") or []
        if isinstance(mijoz_info, str):
            mijoz_info = [mijoz_info]

        def _str_list(value: Any, limit: int = 5) -> List[str]:
            if isinstance(value, str):
                value = [value] if value.strip() else []
            if not isinstance(value, list):
                return []
            items = [str(item).strip() for item in value if str(item).strip()]
            return items[:limit]

        # Uzilish lahzasi — "mijoz qaysi soniyada yo'qoldi".
        #
        # MUHIM: transkripsiya bepul STT yo'lidan (Groq/Cloudflare) kelgan
        # bo'lsa, unda vaqt belgisi YO'Q — o'sha router prompt qabul
        # qilmaydi. Bunday matnda LLM lahzani bilolmaydi, faqat TAXMIN
        # qiladi. Noto'g'ri "01:42" rahbarni yozuvning bo'sh joyiga
        # yuboradi va butun funksiyaga ishonchni yo'qotadi — shuning uchun
        # asos bo'lmasa, umuman ko'rsatmaymiz.
        transcript_is_timed = has_timestamps(transcript)
        breakdown_at = (
            _parse_breakdown_time(data.get("uzilish_vaqti"), duration_seconds)
            if transcript_is_timed
            else None
        )
        if not transcript_is_timed and data.get("uzilish_vaqti"):
            logger.info(
                "[CALL] Uzilish lahzasi rad etildi — transkripsiyada vaqt "
                "belgisi yo'q (bepul STT yo'li)."
            )
        breakdown_reason = str(data.get("uzilish_sababi") or "").strip()
        if not breakdown_at:
            # Vaqtsiz sabab rahbarga foydasiz — ikkalasi birga yashaydi.
            breakdown_reason = ""

        # Pauzalar DETERMINISTIK hisoblanadi (LLM'dan so'ralmaydi): vaqt
        # belgilari bor, demak buni o'lchash mumkin va LLM to'qishi shart emas.
        pauses = [
            {
                "vaqt": p.timestamp,
                "davomiyligi": p.gap_seconds,
                "kimdan_keyin": p.after_speaker,
            }
            for p in detect_pauses(transcript, MAX_ACCEPTABLE_PAUSE_SECONDS)
        ]

        kuchli = _str_list(data.get("kuchli_tomonlar"))
        zaif = _str_list(data.get("zaif_tomonlar"))
        etirozlar = _str_list(data.get("etirozlar"))
        natija = normalise_outcome(data.get("natija"))

        # --- Rubrik baholar ---
        rubrik_raw = data.get("rubrik_baholar") or {}
        if rubrik_raw and isinstance(rubrik_raw, dict):
            def _stage(key: str) -> int:
                s = rubrik_raw.get(key, {})
                return _clamp_score(s.get("ball", 0) if isinstance(s, dict) else s)
            # Og'irliklar rasmiy playbook'dan — bu yerda qayta yozilmaydi.
            rubrik_baholar = {stage: _stage(stage) for stage in STAGE_WEIGHTS}
            total_weight = sum(STAGE_WEIGHTS.values())
            sifat_raw = (
                sum(rubrik_baholar[s] * w for s, w in STAGE_WEIGHTS.items())
                / total_weight
            )
            sifat_bahosi = _clamp_score(round(sifat_raw))
        else:
            sifat_bahosi = _clamp_score(data.get("sifat_bahosi", 0))
            rubrik_baholar = {
                "salomlashish": 0, "ehtiyojlar": 0, "qiymat": 0,
                "etirozlar": 0, "yakunlash": 0, "muloqot_sifati": 0,
            }

        category = _normalise_category(data.get("category"))
        rubrik_amal_qiladi = _rubric_applies(category, transcript)
        if not rubrik_amal_qiladi:
            sifat_bahosi = 0
            rubrik_baholar = dict.fromkeys(rubrik_baholar, 0)
            # Savdo suhbati emas — konversiya statistikasiga kirmasligi kerak,
            # aks holda "Jamoa"/"Oila" qo'ng'iroqlari sotuvchi konversiyasini
            # sun'iy ravishda pasaytiradi.
            natija = OUTCOME_UNKNOWN
            # "Mijoz yo'qolgan lahza" — savdo tushunchasi. Savdo suhbati
            # bo'lmasa mazmunsiz. Pauzalar esa obyektiv o'lchov, qoladi.
            breakdown_at = None
            breakdown_reason = ""

        return {
            "summary": summary or _clip(transcript, 350),
            "category": category,
            "client_mood": _normalise_mood(data.get("client_mood")),
            "next_steps": next_steps,
            "kelishilgan_vaqt": agreed_datetime,
            "client_talk_pct": client_pct,
            "agent_talk_pct": agent_pct,
            "talk_ratio_verdict": _talk_ratio_verdict(client_pct, attributed),
            "talk_ratio_attributed": attributed,
            "rubrik_amal_qiladi": rubrik_amal_qiladi,
            # MetaSell-like extended fields
            "sifat_bahosi": sifat_bahosi,
            "lead_bahosi": _clamp_score(data.get("lead_bahosi", 0)),
            "suhbat_oilasi": str(data.get("suhbat_oilasi") or "Boshqa"),
            "suhbat_domeni": str(data.get("suhbat_domeni") or "Boshqa"),
            "baholash_rejimi": str(data.get("baholash_rejimi") or "Savdo playbook boyicha baholanadi"),
            "biznes_mosligi": str(data.get("biznes_mosligi") or "Noaniq"),
            "servis_yonalishi": str(data.get("servis_yonalishi") or "Boshqa"),
            "mijoz_lavozimi": str(data.get("mijoz_lavozimi") or "N/A"),
            "mijoz_kompaniya": str(data.get("mijoz_kompaniya") or "N/A"),
            "qaror_qabul_qiluvchi": str(data.get("qaror_qabul_qiluvchi") or "Noaniq"),
            "joylashuv": str(data.get("joylashuv") or "N/A"),
            "mijoz_malumotlari": list(mijoz_info),
            "rubrik_baholar": rubrik_baholar,
            # Murabbiylik qatlami (sales_quality_coach, metasell_conversion)
            # aynan shu maydonlarni o'qiydi.
            "natija": natija,
            "konversiya": outcome_converted(natija),
            "uzilish_vaqti": breakdown_at,
            "uzilish_sababi": breakdown_reason,
            "pauzalar": pauses,
            "eng_uzun_pauza": max((p["davomiyligi"] for p in pauses), default=0.0),
            "kuchli_tomonlar": kuchli,
            "zaif_tomonlar": zaif,
            "etirozlar": etirozlar,
        }

    def _fallback_analysis(self, transcript: str) -> Dict[str, Any]:
        lowered = (transcript or "").lower()
        client_words = (
            "brend",
            "branding",
            "logo",
            "dizayn",
            "smm",
            "sayt",
            "narx",
            "to'lov",
            "tolov",
            "commercial",
            "tijorat",
            "taklif",
            "mijoz",
            "loyiha",
        )
        family_words = (
            "ona",
            "dada",
            "opa",
            "aka",
            "farzand",
            "bola",
            "uyga",
            "oila",
            "qarindosh",
        )
        team_words = (
            "jamoa",
            "xodim",
            "menejer",
            "dizayner",
            "copywriter",
            "vazifa",
            "deadline",
            "task",
            "brief",
        )

        if any(word in lowered for word in client_words):
            category = "Mijoz"
        elif any(word in lowered for word in team_words):
            category = "Jamoa"
        elif any(word in lowered for word in family_words):
            category = "Oila"
        elif lowered.strip():
            category = "Shaxsiy"
        else:
            category = "Boshqa"

        client_pct, agent_pct, attributed = _speaker_split(transcript)
        fallback_pauses = [
            {
                "vaqt": p.timestamp,
                "davomiyligi": p.gap_seconds,
                "kimdan_keyin": p.after_speaker,
            }
            for p in detect_pauses(transcript, MAX_ACCEPTABLE_PAUSE_SECONDS)
        ]
        return {
            "summary": _clip(transcript or "Tahlil uchun transkripsiya topilmadi.", 350),
            "category": category,
            "client_mood": "Noaniq",
            "next_steps": "N/A",
            "kelishilgan_vaqt": None,
            "client_talk_pct": client_pct,
            "agent_talk_pct": agent_pct,
            "talk_ratio_verdict": _talk_ratio_verdict(client_pct, attributed),
            "talk_ratio_attributed": attributed,
            # Fallback = LLM ishlamadi; hech narsa baholanmagan.
            "rubrik_amal_qiladi": False,
            "sifat_bahosi": 0,
            "lead_bahosi": 0,
            "suhbat_oilasi": "Boshqa",
            "suhbat_domeni": "Boshqa",
            "baholash_rejimi": "Savdo playbook boyicha baholanadi",
            "biznes_mosligi": "Noaniq",
            "servis_yonalishi": "Boshqa",
            "mijoz_lavozimi": "N/A",
            "mijoz_kompaniya": "N/A",
            "qaror_qabul_qiluvchi": "Noaniq",
            "joylashuv": "N/A",
            "mijoz_malumotlari": [],
            "rubrik_baholar": {
                "salomlashish": 0, "ehtiyojlar": 0, "qiymat": 0,
                "etirozlar": 0, "yakunlash": 0, "muloqot_sifati": 0,
            },
            # Baholanmagan qo'ng'iroq konversiya statistikasiga kirmaydi.
            "natija": OUTCOME_UNKNOWN,
            "konversiya": False,
            "uzilish_vaqti": None,
            "uzilish_sababi": "",
            # Pauza LLM'ga bog'liq emas — fallback'da ham o'lchanadi.
            "pauzalar": fallback_pauses,
            "eng_uzun_pauza": max(
                (p["davomiyligi"] for p in fallback_pauses), default=0.0
            ),
            "kuchli_tomonlar": [],
            "zaif_tomonlar": [],
            "etirozlar": [],
        }

    @staticmethod
    def _score_bar(score: int) -> str:
        """10-block score bar: filled=█, empty=░. E.g. 85/100 → ████████░░ 85/100"""
        filled = round(max(0, min(100, score)) / 10)
        return "█" * filled + "░" * (10 - filled) + f" {score}/100"

    def _build_amocrm_note(
        self,
        analysis: Dict[str, Any],
        transcript_snippet: str = "",
        caller_phone: str = "",
        call_id: str = "",
        duration_seconds: int = 0,
        # legacy keyword args kept for back-compat (ignored, taken from analysis)
        category: str = "",
        summary: str = "",
        client_mood: str = "",
        next_steps: str = "",
        client_talk_pct: int = 0,
        agent_talk_pct: int = 0,
        talk_ratio_verdict: str = "",
    ) -> str:
        """MetaSell Note 1 — Oisha AI tahlil natijasi."""
        _summary = str(analysis.get("summary") or summary or "").strip()
        _category = str(analysis.get("category") or category or "Boshqa")
        _mood = str(analysis.get("client_mood") or client_mood or "Noaniq")
        _next = str(analysis.get("next_steps") or next_steps or "N/A").strip() or "N/A"
        _client_pct = int(analysis.get("client_talk_pct") or client_talk_pct or 0)
        _agent_pct = int(analysis.get("agent_talk_pct") or agent_talk_pct or 0)
        _talk_verdict = str(analysis.get("talk_ratio_verdict") or talk_ratio_verdict or "")
        sifat = int(analysis.get("sifat_bahosi") or 0)
        lead_b = int(analysis.get("lead_bahosi") or 0)
        suhbat_oilasi = str(analysis.get("suhbat_oilasi") or "Boshqa")
        suhbat_domeni = str(analysis.get("suhbat_domeni") or "Boshqa")
        baholash = str(analysis.get("baholash_rejimi") or "Savdo playbook boyicha baholanadi")
        mosligi = str(analysis.get("biznes_mosligi") or "Noaniq")
        servis = str(analysis.get("servis_yonalishi") or "Boshqa")

        rubrik = analysis.get("rubrik_baholar") or {}
        r_salom = int(rubrik.get("salomlashish") or 0)
        r_ehti = int(rubrik.get("ehtiyojlar") or 0)
        r_qiy = int(rubrik.get("qiymat") or 0)
        r_etir = int(rubrik.get("etirozlar") or 0)
        r_yak = int(rubrik.get("yakunlash") or 0)
        r_mul = int(rubrik.get("muloqot_sifati") or 0)

        rubrik_amal_qiladi = bool(analysis.get("rubrik_amal_qiladi", True))
        attributed = bool(analysis.get("talk_ratio_attributed", True))

        lines = [
            f"[{ANALYSIS_MARKER}] Oisha AI tahlil natijasi",
            "",
            _summary,
            "",
        ]

        if rubrik_amal_qiladi:
            lines += [
                f"Sifat bahosi:  {self._score_bar(sifat)}",
                f"Lead bahosi:   {self._score_bar(lead_b)}",
            ]
        else:
            lines.append("Baholanmadi — savdo suhbati emas yoki suhbat juda qisqa")

        lines += [
            f"Suhbat oilasi: {suhbat_oilasi}",
            f"Suhbat domeni: {suhbat_domeni}",
            f"Baholash rejimi: {baholash}",
            f"Biznes mosligi: {mosligi}",
            f"Servis yo'nalishi: {servis}",
            f"Kayfiyat: {_mood}",
        ]

        if rubrik_amal_qiladi:
            lines += [
                "",
                "──── JON BRANDING RUBRIK (6 bosqich) ────",
                f"1. Salomlashish:    {self._score_bar(r_salom)}",
                f"2. Ehtiyojlar:      {self._score_bar(r_ehti)}",
                f"3. Qiymat:          {self._score_bar(r_qiy)}",
                f"4. E'tirozlar (×2): {self._score_bar(r_etir)}",
                f"5. Yakunlash  (×2): {self._score_bar(r_yak)}",
                f"6. Muloqot sifati:  {self._score_bar(r_mul)}",
            ]

        if rubrik_amal_qiladi:
            outcome = normalise_outcome(analysis.get("natija"))
            lines += [
                "",
                f"Natija: {OUTCOME_LABELS_UZ.get(outcome, 'Aniqlanmadi')}"
                + ("  ✅ konversiya" if outcome_converted(outcome) else ""),
            ]

            breakdown_at = analysis.get("uzilish_vaqti")
            breakdown_reason = str(analysis.get("uzilish_sababi") or "").strip()
            if breakdown_at:
                lines += [
                    "",
                    f"🔴 MIJOZ YO'QOLGAN LAHZA: {breakdown_at}"
                    + (f" — {breakdown_reason}" if breakdown_reason else ""),
                ]

            pauses = analysis.get("pauzalar") or []
            if pauses:
                longest = max(pauses, key=lambda p: p.get("davomiyligi", 0))
                lines.append(
                    f"⏸ Keraksiz pauza: {len(pauses)} ta "
                    f"(eng uzuni {longest.get('vaqt')} da "
                    f"{longest.get('davomiyligi')}s)"
                )

            kuchli = [str(x) for x in (analysis.get("kuchli_tomonlar") or [])]
            zaif = [str(x) for x in (analysis.get("zaif_tomonlar") or [])]
            if kuchli or zaif:
                lines.append("")
                lines.append("──── MURABBIY IZOHI ────")
                for item in kuchli[:3]:
                    lines.append(f"✅ {item}")
                for item in zaif[:3]:
                    lines.append(f"⚠️ {item}")

        lines += [
            "",
            f"Keyingi qadam: {_next}",
        ]
        if attributed:
            lines.append(
                f"Gapirish nisbati: Mijoz {_client_pct}% | Sotuvchi {_agent_pct}%"
            )
        elif _client_pct or _agent_pct:
            lines.append(
                f"So'zlovchilar nisbati: {_client_pct}% / {_agent_pct}% "
                "(rollar noma'lum)"
            )
        if _talk_verdict:
            lines.append(_talk_verdict)

        if transcript_snippet:
            snippet = _clip(transcript_snippet, self.max_transcript_note_chars)
            lines += ["", "Transkripsiya (O'zbek):", snippet]

        return "\n".join(lines).strip()

    def _build_client_profile_note(
        self,
        analysis: Dict[str, Any],
        phone: str = "",
        call_id: str = "",
        duration_seconds: int = 0,
    ) -> str:
        """MetaSell Note 2 — Oisha AI: Mijoz profili."""
        lavozim = str(analysis.get("mijoz_lavozimi") or "N/A")
        kompaniya = str(analysis.get("mijoz_kompaniya") or "N/A")
        qaror = str(analysis.get("qaror_qabul_qiluvchi") or "Noaniq")
        joylashuv = str(analysis.get("joylashuv") or "N/A")
        malumotlar = analysis.get("mijoz_malumotlari") or []
        if isinstance(malumotlar, str):
            malumotlar = [malumotlar]

        lines = [
            f"[{ANALYSIS_MARKER}] Oisha AI: Mijoz profili",
            "",
            f"Lavozimi: {lavozim}",
            f"Kompaniya: {kompaniya}",
            f"Qaror qabul qiluvchi: {qaror}",
            f"Joylashuv: {joylashuv}",
        ]
        if malumotlar:
            lines.append("")
            lines.append("Ma'lumotlar:")
            for item in malumotlar[:10]:
                lines.append(f"• {item}")

        meta_parts = []
        if phone:
            meta_parts.append(f"Qo'ng'iroq: {phone}")
        if duration_seconds:
            meta_parts.append(f"Davomiylik: {duration_seconds}s")
        if call_id:
            meta_parts.append(f"ID: {call_id}")
        if meta_parts:
            lines.append("")
            lines.append(" | ".join(meta_parts))

        return "\n".join(lines).strip()

    def _should_create_task(self, next_steps: str) -> bool:
        if not self.create_tasks:
            return False
        text = (next_steps or "").strip()
        if not text:
            return False
        return text.lower() not in {
            "n/a",
            "na",
            "yo'q",
            "yoq",
            "mavjud emas",
            "kerak emas",
            "noaniq",
            "-",
        }

    def _build_task_text(
        self,
        category: str,
        summary: str,
        client_mood: str,
        next_steps: str,
        agreed_datetime: Optional[datetime] = None,
    ) -> str:
        text = f"Oisha follow-up: {next_steps}\n\n"
        if agreed_datetime is not None:
            text += (
                f"⏰ Kelishilgan vaqt: {agreed_datetime.strftime('%d.%m.%Y %H:%M')} "
                f"({_WEEKDAY_UZ[agreed_datetime.weekday()]})\n\n"
            )
        text += (
            f"Qo'ng'iroq xulosasi: {summary}\n"
            f"Toifa: {category}. Kayfiyat: {client_mood}."
        )
        return _clip(text, 900)

    async def _create_follow_up_task(
        self,
        lead_id: int,
        category: str,
        summary: str,
        client_mood: str,
        next_steps: str,
        responsible_user_id: Optional[int] = None,
        agreed_datetime: Optional[datetime] = None,
    ) -> str:
        if not self._should_create_task(next_steps):
            return ""

        create_task = getattr(self.amocrm, "create_task", None)
        if not callable(create_task):
            logger.warning("[CALL] AmoCRM client has no create_task method")
            return ""

        if agreed_datetime is not None:
            complete_till = int(agreed_datetime.astimezone(timezone.utc).timestamp())
            logger.info(
                "[CALL] Vazifa suhbatda kelishilgan vaqtga qo'yildi: %s",
                agreed_datetime.isoformat(),
            )
        else:
            complete_till = int(
                (datetime.now(timezone.utc) + timedelta(hours=self.task_due_hours)).timestamp()
            )
        task_text = self._build_task_text(
            category=category,
            summary=summary,
            client_mood=client_mood,
            next_steps=next_steps,
            agreed_datetime=agreed_datetime,
        )

        try:
            result = await _maybe_await(
                create_task(
                    lead_id,
                    task_text,
                    complete_till,
                    responsible_user_id=responsible_user_id,
                )
            )
            if result:
                task_id = _extract_amocrm_task_id(result)
                logger.info(
                    "[CALL] Follow-up task created for lead %s task_id=%s",
                    lead_id,
                    task_id or "unknown",
                )
                return task_id or "created"
            logger.warning("[CALL] Follow-up task was not created for lead %s", lead_id)
            return ""
        except Exception as exc:
            logger.error("[CALL] Failed to create follow-up task for lead %s: %s", lead_id, exc)
            return ""

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

            stt_service = STTService()
            transcript, _ = await stt_service.transcribe(audio_bytes, mime_type)
            if not transcript:
                continue
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

    # ------------------------------------------------------------------
    # Tarixiy backfill — eski yozuvlarni ham eshitib chiqish
    # ------------------------------------------------------------------

    _BACKFILL_PAGE_KEY = "call_analyzer:backfill_next_page"
    _BACKFILL_DONE_KEY = "call_analyzer:backfill_completed_at"

    async def _read_state(self, key: str, default: str = "") -> str:
        get_state = getattr(self.db, "get_state", None) if self.db else None
        if not callable(get_state):
            return default
        try:
            return str(await _maybe_await(get_state(key, default)) or default)
        except Exception as exc:
            logger.warning("[BACKFILL] '%s' holatini o'qib bo'lmadi: %s", key, exc)
            return default

    async def _write_state(self, key: str, value: str) -> None:
        set_state = getattr(self.db, "set_state", None) if self.db else None
        if not callable(set_state):
            return
        try:
            await _maybe_await(set_state(key, value))
        except Exception as exc:
            logger.warning("[BACKFILL] '%s' holatini yozib bo'lmadi: %s", key, exc)

    async def _fetch_leads_page(self, page: int, per_page: int = 250) -> List[Dict[str, Any]]:
        """Bitimlarning bitta sahifasi.

        `get_leads_detailed` 50 ta bilan cheklangan va sahifalashni
        qo'llab-quvvatlamaydi — u har doim BIRINCHI sahifani qaytaradi,
        shuning uchun tarixga chuqur kirish uchun yaramaydi.
        """
        url = f"{self.amocrm.base_url}/api/v4/leads"
        params = {"limit": max(1, min(int(per_page), 250)), "page": int(page), "with": "contacts"}
        try:
            response = await _maybe_await(
                self.amocrm._request_with_auth(
                    _requests.get, url, params=params, timeout=30
                )
            )
        except Exception as exc:
            logger.error("[BACKFILL] %s-sahifa so'rovi yiqildi: %s", page, exc)
            return []

        status = getattr(response, "status_code", 0)
        if status == 204:
            return []
        if status != 200:
            logger.error("[BACKFILL] %s-sahifa HTTP %s", page, status)
            return []
        try:
            return (response.json().get("_embedded") or {}).get("leads") or []
        except Exception as exc:
            logger.error("[BACKFILL] %s-sahifa JSON xatosi: %s", page, exc)
            return []

    async def backfill_call_recordings(
        self,
        limit: int = 50,
        *,
        write: bool = True,
        include_transcript: bool = True,
        max_pages_per_run: int = 20,
        min_call_duration_seconds: int = 0,
    ) -> Dict[str, Any]:
        """Eski qo'ng'iroq yozuvlarini tahlil qiladi (tarixiy backfill).

        `analyze_recent_calls` faqat eng oxirgi bitimlarni ko'radi. Bu esa
        tarix bo'ylab SAHIFAMA-SAHIFA yuradi va qayerda to'xtaganini
        bazada saqlaydi, ya'ni bir necha marta ishga tushirilsa tarixni
        bosqichma-bosqich yopadi.

        Chegara — Gemini kvotasi: `limit` shu YUGURISHDA tahlil qilinadigan
        maksimal qo'ng'iroq soni. Kvota tugasa, sikl darhol to'xtaydi va
        joriy sahifa saqlanadi — keyingi yugurish o'sha yerdan davom etadi.

        Takroriy tahlil bo'lmaydi: `_is_call_processed` va AmoCRM notasidagi
        marker allaqachon tahlil qilingan qo'ng'iroqni o'tkazib yuboradi.
        """
        await self._load_persisted_cooldown()
        stats: Dict[str, Any] = {
            "leads_scanned": 0,
            "calls_processed": 0,
            "pages_read": 0,
            "start_page": 1,
            "next_page": 1,
            "completed": False,
            "stopped_reason": "",
        }

        if self._defer_calls_without_fallback():
            stats["stopped_reason"] = "gemini_quota_cooldown"
            logger.info(
                "[BACKFILL] Gemini kvotasi sovutishda (%ss) — backfill kechiktirildi.",
                self._gemini_cooldown_remaining(),
            )
            return stats

        try:
            page = max(1, int(await self._read_state(self._BACKFILL_PAGE_KEY, "1") or 1))
        except (TypeError, ValueError):
            page = 1
        stats["start_page"] = page
        stats["next_page"] = page

        target = max(1, int(limit))
        for _ in range(max(1, int(max_pages_per_run))):
            if stats["calls_processed"] >= target:
                stats["stopped_reason"] = "limit_reached"
                break
            if self._defer_calls_without_fallback():
                stats["stopped_reason"] = "gemini_quota_cooldown"
                break

            leads = await self._fetch_leads_page(page)
            stats["pages_read"] += 1
            if not leads:
                # Tarix tugadi — keyingi yugurish boshidan boshlanadi va
                # oradan qo'shilgan yangi bitimlarni ham qamrab oladi.
                stats["completed"] = True
                stats["stopped_reason"] = stats["stopped_reason"] or "history_exhausted"
                page = 1
                await self._write_state(self._BACKFILL_DONE_KEY, get_local_now().isoformat())
                break

            for lead in leads:
                if stats["calls_processed"] >= target:
                    stats["stopped_reason"] = "limit_reached"
                    break
                if self._defer_calls_without_fallback():
                    stats["stopped_reason"] = "gemini_quota_cooldown"
                    break
                lead_id = lead.get("id")
                if not lead_id:
                    continue
                stats["leads_scanned"] += 1
                try:
                    stats["calls_processed"] += await self.process_call_recordings_for_lead(
                        int(lead_id),
                        caller_phone=self._extract_lead_phone(lead),
                        responsible_user_id=lead.get("responsible_user_id"),
                        write=write,
                        include_transcript=include_transcript,
                        min_call_duration_seconds=min_call_duration_seconds,
                    )
                except Exception as exc:
                    # Bitta bitim yiqilsa butun backfill to'xtamasligi kerak.
                    logger.error("[BACKFILL] lead_id=%s yiqildi: %s", lead_id, exc)

            if stats["stopped_reason"] in {"limit_reached", "gemini_quota_cooldown"}:
                break
            page += 1

        stats["next_page"] = page
        await self._write_state(self._BACKFILL_PAGE_KEY, str(page))
        logger.info("[BACKFILL] Yakun: %s", stats)
        return stats

    async def analyze_recent_contact_calls(
        self,
        limit: int = 50,
        write: bool = True,
        include_transcript: bool = True,
        min_call_duration_seconds: int = 0,
    ) -> Dict[str, Any]:
        """Analyze contact-level recordings only when they map to one linked lead."""
        await self._load_persisted_cooldown()
        getter = getattr(self.amocrm, "get_recent_contact_call_notes", None)
        linked_leads_getter = getattr(self.amocrm, "get_contact_linked_leads", None)
        if not callable(getter) or not callable(linked_leads_getter):
            return {
                "contact_calls_discovered": 0,
                "contact_calls_resolved": 0,
                "contact_calls_unlinked": 0,
                "contact_calls_ambiguous": 0,
                "contact_calls_processed": 0,
            }

        notes = await _maybe_await(getter(limit=limit))
        stats = {
            "contact_calls_discovered": len(notes or []),
            "contact_calls_resolved": 0,
            "contact_calls_unlinked": 0,
            "contact_calls_ambiguous": 0,
            "contact_calls_processed": 0,
        }
        for note in notes or []:
            if self._defer_calls_without_fallback():
                logger.info(
                    "[CALL] Gemini quota cooldown active; deferring remaining contact recordings."
                )
                break
            if not self._find_audio_url(note.get("params") or {}):
                continue
            contact_id = note.get("entity_id")
            if not contact_id:
                stats["contact_calls_unlinked"] += 1
                continue
            linked_leads = await _maybe_await(linked_leads_getter(int(contact_id)))
            if len(linked_leads) != 1:
                key = (
                    "contact_calls_unlinked"
                    if not linked_leads
                    else "contact_calls_ambiguous"
                )
                stats[key] += 1
                continue
            lead = linked_leads[0]
            lead_id = lead.get("id")
            if not lead_id:
                stats["contact_calls_unlinked"] += 1
                continue
            stats["contact_calls_resolved"] += 1
            stats["contact_calls_processed"] += await self.process_call_recordings_for_lead(
                int(lead_id),
                caller_phone=self._extract_phone_from_note(note),
                responsible_user_id=lead.get("responsible_user_id")
                or note.get("responsible_user_id"),
                write=write,
                include_transcript=include_transcript,
                max_calls_per_lead=1,
                min_call_duration_seconds=min_call_duration_seconds,
                call_notes_override=[note],
            )
        return stats

    async def analyze_recent_calls(
        self,
        limit: int = 20,
        write: bool = True,
        include_transcript: bool = True,
        one_analysis_per_lead: bool = False,
        max_calls_per_lead: int = 0,
        min_call_duration_seconds: int = 0,
    ) -> Dict[str, Any]:
        """Scan recent AmoCRM leads and analyze their attached call recordings."""
        await self._load_persisted_cooldown()
        if self._defer_calls_without_fallback():
            logger.info(
                "[CALL] Gemini quota cooldown active; deferring recording scan for %ss.",
                self._gemini_cooldown_remaining(),
            )
            return {
                "leads_scanned": 0,
                "calls_processed": 0,
                "contact_calls_discovered": 0,
                "contact_calls_resolved": 0,
                "contact_calls_unlinked": 0,
                "contact_calls_ambiguous": 0,
                "contact_calls_processed": 0,
            }

        try:
            leads = await _maybe_await(self.amocrm.get_leads_detailed(limit=limit))
        except Exception as exc:
            logger.error("[CALL] Failed to fetch leads: %s", exc)
            return {"leads_scanned": 0, "calls_processed": 0}

        scanned = 0
        processed = 0
        for lead in leads or []:
            if self._defer_calls_without_fallback():
                logger.info(
                    "[CALL] Gemini quota cooldown active; deferring remaining lead recordings."
                )
                break
            lead_id = lead.get("id")
            if not lead_id:
                continue
            scanned += 1
            phone = self._extract_lead_phone(lead)
            phone_getter = getattr(self.amocrm, "get_primary_contact_phone", None)
            if not phone and callable(phone_getter):
                phone = await _maybe_await(phone_getter(lead))
            try:
                processed += await self.process_call_recordings_for_lead(
                    int(lead_id),
                    caller_phone=phone,
                    responsible_user_id=lead.get("responsible_user_id"),
                    write=write,
                    include_transcript=include_transcript,
                    one_analysis_per_lead=one_analysis_per_lead,
                    max_calls_per_lead=max_calls_per_lead,
                    min_call_duration_seconds=min_call_duration_seconds,
                )
            except Exception as exc:
                logger.error("[CALL] Lead processing failed: lead_id=%s error=%s", lead_id, exc)

        contact_stats = await self.analyze_recent_contact_calls(
            limit=min(max(int(limit), 1), 250),
            write=write,
            include_transcript=include_transcript,
            min_call_duration_seconds=min_call_duration_seconds,
        )
        processed += contact_stats["contact_calls_processed"]
        return {
            "leads_scanned": scanned,
            "calls_processed": processed,
            **contact_stats,
        }

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

    def _find_audio_url(self, payload: Any, strict: bool = False) -> Optional[str]:
        """Find a recording URL inside a note's params.

        strict=True only accepts URLs with a real audio/video file
        extension (_AUDIO_URL_RE). strict=False also falls back to
        generic keys like "link"/"url", which is useful for locating the
        actual recording URL inside a note we already *know* is a call
        (note_type in _CALL_NOTE_TYPES) but is too loose to use for
        *classifying* a note as a call in the first place — those generic
        keys also show up on unrelated notes (e.g. a Telegram invite link),
        which previously caused non-call notes to be misdetected as calls
        and downloaded as HTML instead of audio.
        """
        candidates: List[str] = []

        def walk(value: Any, key: str = "") -> None:
            if isinstance(value, dict):
                for child_key, child_value in value.items():
                    walk(child_value, str(child_key).lower())
                return
            if isinstance(value, list):
                for item in value:
                    walk(item, key)
                return
            if not isinstance(value, str):
                return

            text = value.strip()
            if not text:
                return
            audio_match = _AUDIO_URL_RE.search(text)
            if audio_match:
                candidates.append(audio_match.group(0))
                return
            if strict:
                return
            if key in {
                "link",
                "record",
                "record_url",
                "recording_url",
                "audio_url",
                "file_url",
                "url",
            }:
                url_match = _URL_RE.search(text)
                if url_match:
                    candidates.append(url_match.group(0))

        walk(payload)
        return candidates[0] if candidates else None

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
