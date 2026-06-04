import asyncio
import hashlib
import io
import inspect
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests as _requests

from src.database import Database
from src.services.core.amocrm_sync import AmoCRMSync

logger = logging.getLogger(__name__)

ANALYSIS_MARKER = "AI_CALL_ANALYSIS"
CATEGORIES = ["Shaxsiy", "Oila", "Jamoa", "Mijoz", "Boshqa"]
MOODS = ["Ijobiy", "Neytral", "Salbiy", "Noaniq"]

_CALL_NOTE_TYPES = {
    "call_in",
    "call_out",
    "call",
    "amocrm_phone_call",
    "phone_call",
    "voip_call",
}

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


_CLIENT_LABELS = re.compile(r"^(mijoz|xaridor|client)\s*:", re.IGNORECASE)
_AGENT_LABELS = re.compile(r"^(sotuvchi|menejer|manager|agent|xodim|oisha)\s*:", re.IGNORECASE)


def _compute_talk_ratio(transcript: str) -> tuple[int, int]:
    """Return (client_pct, agent_pct) based on character counts per speaker."""
    client_chars = 0
    agent_chars = 0
    for line in (transcript or "").splitlines():
        line = line.strip()
        if not line:
            continue
        colon_pos = line.find(":")
        if colon_pos < 1:
            continue
        label = line[:colon_pos].strip()
        text = line[colon_pos + 1:].strip()
        if _CLIENT_LABELS.match(label + ":"):
            client_chars += len(text)
        elif _AGENT_LABELS.match(label + ":"):
            agent_chars += len(text)

    total = client_chars + agent_chars
    if total == 0:
        return 0, 0
    return round(client_chars * 100 / total), round(agent_chars * 100 / total)


def _talk_ratio_verdict(client_pct: int) -> str:
    """Human-readable verdict for the talk ratio."""
    if client_pct >= 55:
        return f"✅ Yaxshi — mijoz {client_pct}% gapirdi (ideal: ≥55%)"
    if client_pct >= 40:
        return f"⚠️ O'rtacha — mijoz {client_pct}% gapirdi (ideal: ≥55%)"
    return f"🔴 Zaif — sotuvchi haddan ko'p gapirdi, mijoz faqat {client_pct}% gapirdi"


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)].rstrip() + "\n...[qisqartirildi]"


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
        self.gemini_cooldown_seconds = int(
            os.getenv("GEMINI_CALL_COOLDOWN_SECONDS", "900")
        )
        self._cooldown_loaded = False

        self.genai_client = gemini_client
        if self.genai_client is None:
            api_key = ""
            try:
                api_key = settings.GEMINI_API_KEY.get_secret_value()
            except Exception:
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
        except Exception:
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
    ) -> None:
        if not self.db:
            return
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
                         task_id, task_created_at, analyzed_at, created_at, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ),
                )
            )
            await _maybe_await(conn.commit())
            logger.info("[CALL] DB log saved: lead_id=%s call_id=%s", lead_id, call_id)
        except Exception as exc:
            logger.error("[CALL] DB log failed for %s: %s", call_id, exc)

    async def _fetch_audio_bytes(self, url: str) -> Optional[Tuple[bytes, str]]:
        """Download an AmoCRM recording into memory."""
        headers_auth = {}
        get_headers = getattr(self.amocrm, "_get_headers", None)
        if callable(get_headers):
            try:
                headers_auth = get_headers() or {}
            except Exception:
                headers_auth = {}

        def _get(headers: Dict[str, str]):
            return _requests.get(url, headers=headers, timeout=90, stream=False)

        try:
            resp = await asyncio.to_thread(_get, headers_auth)
            if resp.status_code != 200:
                resp = await asyncio.to_thread(_get, {})

            if resp.status_code == 200 and resp.content:
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

            logger.warning("[CALL] Audio fetch failed: http=%s url=%s", resp.status_code, url)
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
                ) from exc
            raise

    async def _transcribe_inline(self, audio_bytes: bytes, mime_type: str) -> Optional[str]:
        """Transcribe and translate the call recording into Uzbek Latin text."""
        from google.genai import types

        prompt = (
            "Siz professional qo'ng'iroq transkripsiya mutaxassisisiz. "
            "Audio yozuvni eshiting va suhbatni O'zbek lotinida yozing.\n\n"
            "Qoidalar:\n"
            "- Ikki tomon gaplarini A: va B: qilib ajrating.\n"
            "- Ruscha yoki boshqa tilda gapirilgan bo'lsa, mazmunini O'zbek lotiniga tarjima qilib yozing.\n"
            "- Ism, telefon, narx, muddat va vazifalarni aniq saqlang.\n"
            "- Eshitilmagan joylarni [...] deb belgilang.\n"
            "- Faqat transkripsiya matnini qaytaring."
        )

        try:
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            response = await self._gemini_generate_content(
                contents=[prompt, audio_part],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=8192,
                ),
            )
            text = (getattr(response, "text", None) or "").strip()
            if text:
                logger.info("[CALL] STT done: %s chars", len(text))
                return text
            logger.warning("[CALL] STT returned an empty response")
            return await self._transcribe_openai(audio_bytes, mime_type)
        except GeminiQuotaCooldownError:
            logger.info("[CALL] Gemini STT skipped during quota cooldown.")
            return await self._transcribe_openai(audio_bytes, mime_type)
        except Exception as exc:
            logger.error("[CALL] STT failed: %s", exc)
            return await self._transcribe_openai(audio_bytes, mime_type)

    async def _transcribe_openai(
        self, audio_bytes: bytes, mime_type: str
    ) -> Optional[str]:
        """Fallback STT via OpenAI when Gemini audio quota is unavailable."""
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
            if text:
                logger.info("[CALL] OpenAI STT fallback done: %s chars", len(text))
                return text
            return None
        except Exception as exc:
            logger.error("[CALL] OpenAI STT fallback failed: %s", exc)
            return None

    async def analyze_transcript(self, transcript: str) -> Dict[str, Any]:
        """Classify, summarize, and extract next steps from a transcript."""
        if not transcript:
            return self._fallback_analysis(transcript)

        try:
            from google.genai import types

            client_pct, agent_pct = _compute_talk_ratio(transcript)
            prompt = (
                "Quyidagi telefon suhbati transkripsiyasini tahlil qiling.\n\n"
                "TOIFALAR (faqat bittasini tanlang):\n"
                "- Shaxsiy: shaxsiy, biznesga aloqasi yo'q suhbat.\n"
                "- Oila: oila a'zolari, uy ishlari, bolalar yoki qarindoshlar haqida.\n"
                "- Jamoa: xodimlar, ichki ishlar, vazifa, deadline, operatsion muhokama.\n"
                "- Mijoz: brending, dizayn, SMM, sayt, loyiha, narx, savdo yoki mijoz muzokarasi.\n"
                "- Boshqa: aralash, spam yoki yuqoridagilarga aniq kirmaydigan qo'ng'iroq.\n\n"
                "GAPIRISH NISBATI (hisoblangan):\n"
                f"  Mijoz: {client_pct}%  |  Sotuvchi: {agent_pct}%\n"
                "  Ideal: mijoz ≥55%, sotuvchi ≤45%.\n\n"
                "Javobni faqat JSON formatida qaytaring:\n"
                "{\n"
                '  "summary": "2-4 gapda O\'zbekcha xulosa",\n'
                '  "category": "Shaxsiy|Oila|Jamoa|Mijoz|Boshqa",\n'
                '  "client_mood": "Ijobiy|Neytral|Salbiy|Noaniq",\n'
                '  "next_steps": "Keyingi aniq qadamlar yoki N/A",\n'
                f'  "client_talk_pct": {client_pct},\n'
                f'  "agent_talk_pct": {agent_pct}\n'
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
            return self._normalise_analysis(data, transcript)
        except GeminiQuotaCooldownError:
            logger.info("[CALL] Gemini transcript analysis skipped during quota cooldown.")
            openai_analysis = await self._analyze_transcript_openai(transcript)
            if openai_analysis:
                return openai_analysis
            return self._fallback_analysis(transcript)
        except Exception as exc:
            logger.error("[CALL] Transcript analysis failed: %s", exc)
            openai_analysis = await self._analyze_transcript_openai(transcript)
            if openai_analysis:
                return openai_analysis
            return self._fallback_analysis(transcript)

    async def _analyze_transcript_openai(self, transcript: str) -> Optional[Dict[str, Any]]:
        """Fallback JSON analysis via OpenAI text model."""
        if not self.openai_client:
            return None

        model = getattr(self._settings, "OPENAI_TEXT_MODEL", "gpt-4o-mini")
        system = (
            "Siz O'zbek tilida ishlaydigan amoCRM qo'ng'iroq tahlilchisisiz. "
            "Faqat JSON qaytaring."
        )
        user = (
            "Telefon suhbati transkripsiyasini tahlil qiling.\n"
            "Toifalar: Shaxsiy, Oila, Jamoa, Mijoz, Boshqa.\n"
            "Kayfiyat: Ijobiy, Neytral, Salbiy, Noaniq.\n"
            "JSON schema: summary, category, client_mood, next_steps.\n\n"
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
            return self._normalise_analysis(data, transcript)
        except Exception as exc:
            logger.error("[CALL] OpenAI analysis fallback failed: %s", exc)
            return None

    def _normalise_analysis(
        self, data: Dict[str, Any], transcript: str
    ) -> Dict[str, Any]:
        summary = str(data.get("summary") or "").strip()
        next_steps = str(data.get("next_steps") or "N/A").strip() or "N/A"
        # Prefer pre-computed values; fall back to re-computing from transcript
        computed_client, computed_agent = _compute_talk_ratio(transcript)
        client_pct = int(data.get("client_talk_pct") or computed_client)
        agent_pct = int(data.get("agent_talk_pct") or computed_agent)
        return {
            "summary": summary or _clip(transcript, 350),
            "category": _normalise_category(data.get("category")),
            "client_mood": _normalise_mood(data.get("client_mood")),
            "next_steps": next_steps,
            "client_talk_pct": client_pct,
            "agent_talk_pct": agent_pct,
            "talk_ratio_verdict": _talk_ratio_verdict(client_pct),
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

        client_pct, agent_pct = _compute_talk_ratio(transcript)
        return {
            "summary": _clip(transcript or "Tahlil uchun transkripsiya topilmadi.", 350),
            "category": category,
            "client_mood": "Noaniq",
            "next_steps": "N/A",
            "client_talk_pct": client_pct,
            "agent_talk_pct": agent_pct,
            "talk_ratio_verdict": _talk_ratio_verdict(client_pct),
        }

    def _build_amocrm_note(
        self,
        category: str,
        summary: str,
        client_mood: str,
        next_steps: str,
        transcript_snippet: str,
        caller_phone: str = "",
        call_id: str = "",
        duration_seconds: int = 0,
        client_talk_pct: int = 0,
        agent_talk_pct: int = 0,
        talk_ratio_verdict: str = "",
    ) -> str:
        phone_line = f"\nQo'ng'iroq raqami: {caller_phone}" if caller_phone else ""
        call_line = f"\nCall ID: {call_id}" if call_id else ""
        duration_line = f"\nDavomiylik: {duration_seconds}s" if duration_seconds else ""
        ratio_line = ""
        if client_talk_pct or agent_talk_pct:
            ratio_line = (
                f"\nGapirish nisbati: Mijoz {client_talk_pct}% | Sotuvchi {agent_talk_pct}%"
                f"\n{talk_ratio_verdict}"
            )
        transcript = _clip(transcript_snippet, self.max_transcript_note_chars)
        return (
            f"[{ANALYSIS_MARKER}] Oisha-OS: Qo'ng'iroq tahlili\n"
            f"Toifa: {category}\n"
            f"Kayfiyat: {client_mood}"
            f"{phone_line}"
            f"{call_line}"
            f"{duration_line}"
            f"{ratio_line}\n\n"
            f"Xulosa:\n{summary}\n\n"
            f"Keyingi qadam:\n{next_steps}\n\n"
            f"Transkripsiya (O'zbek):\n{transcript}"
        ).strip()

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
    ) -> str:
        text = (
            f"Oisha follow-up: {next_steps}\n\n"
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
    ) -> str:
        if not self._should_create_task(next_steps):
            return ""

        create_task = getattr(self.amocrm, "create_task", None)
        if not callable(create_task):
            logger.warning("[CALL] AmoCRM client has no create_task method")
            return ""

        complete_till = int(
            (datetime.now(timezone.utc) + timedelta(hours=self.task_due_hours)).timestamp()
        )
        task_text = self._build_task_text(
            category=category,
            summary=summary,
            client_mood=client_mood,
            next_steps=next_steps,
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
        for note in call_notes:
            audio_url = self._find_audio_url(note.get("params") or {})
            if not audio_url:
                continue

            call_id = self._extract_call_id(note, lead_id, audio_url)
            if self._note_has_analysis_for_call(notes or [], call_id):
                logger.info("[CALL] Lead note already contains analysis marker: lead_id=%s call_id=%s", lead_id, call_id)
                continue
            if await self._is_call_processed(call_id):
                logger.info("[CALL] Already processed: lead_id=%s call_id=%s", lead_id, call_id)
                continue

            duration = self._extract_call_duration_seconds(note)
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

            transcript = await self._transcribe_inline(audio_bytes, mime_type)
            if not transcript:
                continue

            analysis = await self.analyze_transcript(transcript)
            category = _normalise_category(analysis.get("category"))
            client_mood = _normalise_mood(analysis.get("client_mood"))
            summary = str(analysis.get("summary") or "").strip() or _clip(transcript, 350)
            next_steps = str(analysis.get("next_steps") or "N/A").strip() or "N/A"

            note_text = self._build_amocrm_note(
                category=category,
                summary=summary,
                client_mood=client_mood,
                next_steps=next_steps,
                transcript_snippet=transcript if include_transcript else "",
                caller_phone=phone,
                call_id=call_id,
                duration_seconds=duration,
                client_talk_pct=analysis.get("client_talk_pct", 0),
                agent_talk_pct=analysis.get("agent_talk_pct", 0),
                talk_ratio_verdict=analysis.get("talk_ratio_verdict", ""),
            )

            if write:
                try:
                    await asyncio.to_thread(self.amocrm.add_lead_note, lead_id, note_text)
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
            if one_analysis_per_lead:
                break
            await asyncio.sleep(0.5)

        return processed

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
        return self._find_audio_url(note.get("params") or {}) is not None

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

    def _find_audio_url(self, payload: Any) -> Optional[str]:
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
        except Exception:
            pass
        return ""
