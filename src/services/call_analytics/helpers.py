import inspect
import json
import structlog
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


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
_talk_ratio_verdict = talk_ratio_verdict
_detect_pauses = detect_pauses
_format_timestamp = format_timestamp
_has_timestamps = has_timestamps
_strip_timestamps = strip_timestamps


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

# Whisper's training data is saturated with YouTube — on silence/noise it
# regularly hallucinates subtitle-credit boilerplate instead of erroring.
# These substrings are specific enough that a real Uzbek/Russian sales call
# transcript would essentially never contain them.
_STT_HALLUCINATION_SUBSTRINGS = (
    "субтитры",
    "subtitles",
    "subtitr",
    "subtitles by",
    "amara.org",
    "dimatorzok",
    "translated by",
    "opensubtitles",
    "thanks for watching",
    "thank you for watching",
    "like and subscribe",
)


def _looks_like_stt_hallucination(text: str) -> bool:
    """Juda qisqa yoki ma'lum hallucination iboralariga mos matnni
    ishonchsiz deb belgilaydi — real qo'ng'iroq suhbati bunday bo'lmaydi."""
    if not text:
        return True
    normalised = text.strip().strip(".!?").lower()
    if not normalised or len(normalised) < 4:
        return True
    if normalised in _STT_HALLUCINATION_PHRASES:
        return True
    if any(marker in normalised for marker in _STT_HALLUCINATION_SUBSTRINGS):
        return True
    # Repetitive single word hallucination loop check (e.g. "ha ha ha ha ha")
    words = normalised.split()
    if len(words) >= 4 and len(set(words)) == 1:
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



__all__ = [
    "GeminiQuotaCooldownError",
    "ANALYSIS_MARKER",
    "CATEGORIES",
    "MOODS",
    "_WEEKDAY_UZ",
    "_AGREED_TIME_MAX_DAYS_AHEAD",
    "_CALL_NOTE_TYPES",
    "NO_SPEECH_SENTINEL",
    "_AUDIO_MIME_MAP",
    "_AUDIO_URL_RE",
    "_URL_RE",
    "_maybe_await",
    "_detect_mime",
    "_compute_talk_ratio",
    "_looks_like_stt_hallucination",
    "_transcript_impossible_for_duration",
    "_rubric_applies",
    "_parse_agreed_datetime",
    "_clip",
    "_parse_breakdown_time",
    "_extract_amocrm_task_id",
    "_extract_json_object",
    "_normalise_category",
    "_normalise_mood",
    "_speaker_split",
    "_talk_ratio_verdict",
    "_detect_pauses",
    "_format_timestamp",
    "_has_timestamps",
    "_strip_timestamps",
]
