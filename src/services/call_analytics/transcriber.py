import os
import re
import io
import time
import asyncio
from typing import Any, Dict, List, Optional, Tuple
import structlog
import requests as _requests
from src.services.core.stt_service import STTService
from src.services.call_analytics.helpers import *

logger = structlog.get_logger()

class CallTranscriberMixin:
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
        if not self._gemini_cooling_down():
            return False
        if self.openai_client:
            return False
        if self.free_ai_router.available("groq") or self.free_ai_router.available("cloudflare"):
            return False
        return True

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
                if _looks_like_stt_hallucination(result.transcript):
                    logger.info(
                        "[CALL] STTService transcript rejected as likely "
                        "hallucination: %r",
                        result.transcript[:80],
                    )
                else:
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
