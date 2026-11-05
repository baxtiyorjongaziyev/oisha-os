"""Telegram Real-Time Assistant Advisor for Oisha-OS.

Audits incoming client messages, questions, and follow-up requests in Baxtiyorjon's Telegram,
generates actionable 1-2-3 step instructions for business assistant Shahnoza (@jonbranding_assistant),
delivers notifications via @jonairobot, and records recommendations in the Obsidian Second Brain.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Shahnoza's identifiers
SHAHNOZA_USER_ID = 8802892610
SHAHNOZA_USERNAME = "jonbranding_assistant"

# Owner's identifiers
OWNER_USER_ID = 150074828

# Calendar proposal settings
try:
    LOCAL_TZ = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Tashkent"))
except Exception:  # pragma: no cover - tzdata yoʼq muhitlar uchun
    LOCAL_TZ = timezone(timedelta(hours=5))

DEFAULT_MEETING_DURATION = timedelta(hours=1)

_WEEKDAY_INDEX = {
    "dushanba": 0,
    "seshanba": 1,
    "chorshanba": 2,
    "payshanba": 3,
    "juma": 4,
    "shanba": 5,
    "yakshanba": 6,
}

_WEEKDAY_LABELS = {
    0: "dushanba",
    1: "seshanba",
    2: "chorshanba",
    3: "payshanba",
    4: "juma",
    5: "shanba",
    6: "yakshanba",
}

_MONTH_INDEX = {
    "yanvar": 1,
    "fevral": 2,
    "mart": 3,
    "aprel": 4,
    "may": 5,
    "iyun": 6,
    "iyul": 7,
    "avgust": 8,
    "sentabr": 9,
    "sentyabr": 9,
    "oktabr": 10,
    "oktyabr": 10,
    "noyabr": 11,
    "dekabr": 12,
}

_TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\b")
_TEXT_DATE_RE = re.compile(
    r"\b(\d{1,2})\s*[-–]?\s*(" + "|".join(_MONTH_INDEX) + r")\b"
)

_MEETING_KEYWORDS = (
    "uchrashuv",
    "uchrashamiz",
    "uchrashamizmi",
    "uchrashdik",
    "koʼrishamiz",
    "korishamiz",
    "koʼrishdik",
    "kelishdik",
    "kelishamiz",
    "offline",
    "ofisda",
    "zoom",
    "meet",
    "sessiya",
    "qoʼngʼiroq",
    "qongiroq",
    "gaplashamiz",
    "gaplashdik",
    "kelaman",
    "keladi",
    "keladilar",
)

_APOSTROPHES = ("\u2018", "\u2019", "\u02bb", "\u02bc", "`", "\u00b4")


def _normalize_text(text: str) -> str:
    lowered = (text or "").lower()
    for mark in _APOSTROPHES:
        lowered = lowered.replace(mark, "'")
    return lowered


# Kalit soʼzlar unicode apostrof bilan yozilgani uchun normalizatsiya qilinadi
_MEETING_KEYWORDS_NORMALIZED = tuple(_normalize_text(word) for word in _MEETING_KEYWORDS)


def _coerce_reference(reference: Optional[datetime]) -> datetime:
    if reference is None:
        return datetime.now(LOCAL_TZ)
    if reference.tzinfo is None:
        return reference.replace(tzinfo=LOCAL_TZ)
    return reference.astimezone(LOCAL_TZ)


def _resolve_date(normalized: str, now: datetime) -> Optional[datetime]:
    """Xabar matnidan sanani topadi. Topilmasa None qaytaradi."""
    # 1. 07.11 yoki 07.11.2026 koʼrinishidagi aniq sana
    numeric = _NUMERIC_DATE_RE.search(normalized)
    if numeric:
        day = int(numeric.group(1))
        month = int(numeric.group(2))
        year_raw = numeric.group(3)
        year = now.year
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        try:
            candidate = datetime(year, month, day, tzinfo=LOCAL_TZ)
        except ValueError:
            candidate = None
        if candidate is not None:
            if candidate.date() < now.date() and not year_raw:
                try:
                    candidate = candidate.replace(year=year + 1)
                except ValueError:
                    candidate = None
            if candidate is not None:
                return candidate

    # 2. 7 noyabr koʼrinishidagi matnli sana
    text_date = _TEXT_DATE_RE.search(normalized)
    if text_date:
        day = int(text_date.group(1))
        month = _MONTH_INDEX[text_date.group(2)]
        year = now.year
        try:
            candidate = datetime(year, month, day, tzinfo=LOCAL_TZ)
        except ValueError:
            candidate = None
        if candidate is not None:
            if candidate.date() < now.date():
                try:
                    candidate = candidate.replace(year=year + 1)
                except ValueError:
                    candidate = None
            if candidate is not None:
                return candidate

    # 3. Nisbiy kunlar
    if "indinga" in normalized or "indin" in normalized:
        return now + timedelta(days=2)
    if "ertaga" in normalized:
        return now + timedelta(days=1)
    if "bugun" in normalized:
        return now

    # 4. Hafta kuni nomi (eng yaqin keladigan kun)
    for name, target_index in _WEEKDAY_INDEX.items():
        if re.search(rf"\b{name}\b", normalized):
            days_ahead = (target_index - now.weekday()) % 7
            return now + timedelta(days=days_ahead)

    return None


def detect_calendar_appointment(
    text: str,
    reference: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Uchrashuv kelishuvi (sana + vaqt) borligini aniqlaydi.

    Kalendar taklifini shakllantirish uchun yetarli maʼlumot boʼlsa dict qaytaradi,
    aks holda None.
    """
    if not text or len(text.strip()) < 3:
        return None

    normalized = _normalize_text(text)
    if not any(keyword in normalized for keyword in _MEETING_KEYWORDS_NORMALIZED):
        return None

    time_match = _TIME_RE.search(normalized)
    if not time_match:
        return None

    now = _coerce_reference(reference)
    day = _resolve_date(normalized, now)
    if day is None:
        return None

    hour = int(time_match.group(1))
    minute = int(time_match.group(2))
    start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=LOCAL_TZ)

    if start <= now:
        return None

    end = start + DEFAULT_MEETING_DURATION
    return {
        "start": start,
        "end": end,
        "start_iso": start.isoformat(),
        "end_iso": end.isoformat(),
        "when_label": (
            f"{_WEEKDAY_LABELS[start.weekday()]}, "
            f"{start.strftime('%d.%m.%Y')} {start.strftime('%H:%M')}"
        ),
    }

VAULT_PATHS = [
    r"C:\Users\baxti\Documents\JonBranding Second Brain",
    r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault",
    "/home/ubuntu/obsidian-vault",
]


def _get_active_vault_path() -> Optional[Path]:
    for p in VAULT_PATHS:
        path = Path(p)
        if path.exists() and (path / "20-Areas").exists():
            return path
    env_vault = os.getenv("VAULT_PATH")
    if env_vault and Path(env_vault).exists():
        return Path(env_vault)
    return None


class TelegramAssistantAdvisor:
    """Audits Telegram conversations and provides real-time recommendations to assistant Shahnoza."""

    def __init__(self, vault_path: Optional[Path] = None, assistant_id: int = SHAHNOZA_USER_ID) -> None:
        self.vault_path = vault_path or _get_active_vault_path()
        self.assistant_id = assistant_id
        self._processed_msg_ids: Set[str] = set()

    def analyze_chat_for_assistant(
        self,
        chat_id: int,
        chat_title: str,
        messages: List[Dict[str, Any]],
        owner_id: int = OWNER_USER_ID,
        reference_dt: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyzes a conversation and extracts an actionable recommendation for Shahnoza."""
        if not messages:
            return None

        last_msg = messages[-1]
        msg_id = str(last_msg.get("id", ""))
        unique_key = f"{chat_id}_{msg_id}"

        if unique_key in self._processed_msg_ids:
            return None

        sender = last_msg.get("sender", "Mijoz")
        text = last_msg.get("text", "").strip()
        sender_id = last_msg.get("sender_id")

        if len(text) < 3:
            return None

        # Uchrashuv kelishuvi boʼlsa, xabar egasidan boʼlsa ham kalendar taklifi beriladi
        appointment = detect_calendar_appointment(text, reference=reference_dt)

        # Ignore messages sent by Baxtiyorjon or Shahnoza herself (calendar kelishuvi bundan mustasno)
        if sender_id in (owner_id, self.assistant_id) and appointment is None:
            return None

        # Categorize action trigger
        action_needed = False
        action_type = "Umumiy soʼrov"
        recommendation = ""

        lower_text = text.lower()
        if appointment:
            action_needed = True
            action_type = "Uchrashuv / Kalendar"
            recommendation = (
                f"Kelishilgan uchrashuv: {appointment['when_label']} — \"{text[:120]}\". "
                "Baxtiyorjon Gaziyev kalendariga kiritib qoʻyaymi, deb soʻrab tasdiq oling. "
                "Tasdiqlansa, /api/calendar/events orqali qoʻshing."
            )
        elif any(k in lower_text for k in ["narx", "qancha", "narxi", "qimmat", "tolov", "toʻlov", "byudjet"]):
            action_needed = True
            action_type = "Narx / Byudjet so'rovi"
            recommendation = (
                f"Mijozga ({chat_title}) xizmatlar tarifi va portfolio namunasini yuboring. "
                "Byudjetini aniqlab, qisqa briefing o'tkazing."
            )
        elif any(k in lower_text for k in ["qachon", "tayyor", "status", "qayerda", "fayl", "logo", "maketi", "korgan"]):
            action_needed = True
            action_type = "Loyiha statusi / Fayl so'rovi"
            recommendation = (
                f"Mijoz ({chat_title}) ish jarayonini so'ramoqda. Dizayn guruhidan statusni oling va "
                "mijozga bugungi muddatni ma'lum qiling."
            )
        elif any(k in lower_text for k in ["korish", "ko'rish", "uchrash", "zoom", "gaplash", "qongiroq", "qo'ng'iroq"]):
            action_needed = True
            action_type = "Uchrashuv / Qo'ng'iroq"
            recommendation = (
                f"Mijoz ({chat_title}) suhbatlashmoqchi. Baxtiyorjonning bo'sh vaqtiga qarab 15 daqiqalik "
                "strategik sessiya yoki qo'ng'iroq vaqtini belgilang."
            )
        elif any(k in lower_text for k in ["rahmat", "boladi", "bo'ladi", "tasdiq", "ma'qul", "start"]):
            action_needed = True
            action_type = "Tasdiqlash / Keyingi bosqich"
            recommendation = (
                f"Mijoz ({chat_title}) ijobiy javob berdi. Shartnoma yoki avans to'lovi uchun rekvizitlarni tayyorlang."
            )
        elif "?" in text or len(text.split()) >= 4:
            # Unanswered question
            action_needed = True
            action_type = "Javob talab qiluvchi savol"
            recommendation = (
                f"Mijozning ({chat_title}) savoliga aniqlik kiriting va zarur bo'lsa Baxtiyorjonga xabar bering."
            )

        if not action_needed:
            return None

        self._processed_msg_ids.add(unique_key)
        task: Dict[str, Any] = {
            "chat_id": chat_id,
            "chat_title": chat_title,
            "sender": sender,
            "text": text,
            "action_type": action_type,
            "recommendation": recommendation,
            "date": last_msg.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
        }
        if appointment:
            task["calendar"] = {
                "start_iso": appointment["start_iso"],
                "end_iso": appointment["end_iso"],
                "when_label": appointment["when_label"],
            }
        return task

    def format_telegram_alert(self, task: Dict[str, Any]) -> str:
        """Formats an executive Uzbek notification for Shahnoza."""
        calendar_block = ""
        calendar = task.get("calendar")
        if calendar:
            calendar_block = (
                f"📅 <b>Kalendar:</b> {calendar['when_label']}\n"
                f"❓ <b>Savol:</b> Baxtiyorjon Gaziyev kalendariga kiritib qoʻyaymi?\n\n"
            )
        return (
            f"⚡ <b>Yangi Tavsiya (Shaxsiy Yordamchi Shahnoza uchun)</b>\n\n"
            f"👤 <b>Mijoz / Chat:</b> {task['chat_title']}\n"
            f"📌 <b>Yo'nalish:</b> {task['action_type']}\n"
            f"💬 <b>Mijoz xabari:</b> <i>\"{task['text'][:150]}\"</i>\n\n"
            f"{calendar_block}"
            f"🎯 <b>Qilinishi kerak bo'lgan vazifa:</b>\n"
            f"👉 {task['recommendation']}\n\n"
            f"⏱ <i>Real-time Telegram Audit</i>"
        )

    def record_in_obsidian(self, tasks: List[Dict[str, Any]]) -> bool:
        """Appends generated assistant tasks to 20-Areas/Yordamchi Vazifalari.md."""
        if not self.vault_path or not tasks:
            return False

        areas_dir = self.vault_path / "20-Areas"
        areas_dir.mkdir(parents=True, exist_ok=True)
        file_path = areas_dir / "Yordamchi Vazifalari.md"

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        new_lines = [f"\n### ⚡ Audit: {now_str}"]
        for t in tasks:
            new_lines.append(f"- [ ] **{t['chat_title']}** ({t['action_type']}): {t['recommendation']}")
            calendar = t.get("calendar")
            if calendar:
                new_lines.append(
                    f"  - Kalendar taklifi: **{calendar['when_label']}** "
                    f"(`{calendar['start_iso']}` → `{calendar['end_iso']}`)"
                )
            new_lines.append(f"  > _\"{t['text'][:100]}\"_")

        content_to_append = "\n".join(new_lines) + "\n"

        if file_path.exists():
            existing = file_path.read_text(encoding="utf-8")
            file_path.write_text(existing + content_to_append, encoding="utf-8")
        else:
            header = f"""---
title: Shaxsiy Yordamchi Vazifalari va Tavsiyalar
type: area
status: active
updated: "{now_str}"
tags:
  - assistant
  - tasks
  - jonbranding
sources:
  - "[[Telegram Live Ekosistemasi]]"
---

# Shaxsiy Yordamchi (Shahnoza) Vazifalar Oqimi

Telegramdagi mijozlar so'rovlari asosida AI tomonidan real-time shakllantirilgan tavsiyalar va operativ vazifalar.
"""
            file_path.write_text(header + content_to_append, encoding="utf-8")

        logger.info("[ASSISTANT_ADVISOR] Appended %d tasks to Yordamchi Vazifalari.md", len(tasks))
        return True
