"""
AI-powered Task Extraction from Conversation Flow.
Avtomatik vazifa aniqlash suhbat matnidan.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ExtractedTask:
    """Aniqlangan vazifa ma'lumotlari."""
    title: str
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: TaskPriority = TaskPriority.NORMAL
    assignee_hint: Optional[str] = None  # Kim bajarishi kerak (sender/recipient)
    confidence: float = 0.0  # 0-1, qancha ishonch
    source_text: str = ""  # Asl xabar matni


class TaskExtractor:
    """AI-powered task extraction from natural language."""

    # Vazifa ko'rsatkich kalit so'zlari
    TASK_INDICATORS = {
        "uz": [
            # Buyruq shakli
            r"\b(bajar|yoz|yubor|qo'sh|o'chir|yangila|tekshir|qidir|top|ol|ber|ayt|gapir|javob|javob_ber)\b",
            # Kelajakda bajarilish kerak
            r"\b(kelajakda|ertaga|keyin|so'ng|keyinchalik|hozircha)\b.*\b(bajar|yoz|yubor|qo'sh|o'chir|yangila|tekshir)\b",
            # Vaqt belgilari
            r"\b(bugun|ertaga|hafta|oy|kun|soat|daqiqa)\b.*\b(ichida|gacha|oldin)\b",
            # Majburiyat
            r"\b(kerak|lozim|shart|majbur|mejbur)\b",
            # Rejalashtirish
            r"\b(reja|plan|vazifa|topshiriq|ishi|ish)\b",
            # Ogohlantirish
            r"\b(eslat|xatirla|unutma|unutmas)\b",
        ],
        "ru": [
            r"\b(сделай|напиши|отправь|добавь|удали|обнови|проверь|найди|возьми|дай|скажи|ответь)\b",
            r"\b(завтра|потом|позже|позднее|в_будущем)\b.*\b(сделай|напиши|отправь|добавь|удали|обнови|проверь)\b",
            r"\b(сегодня|завтра|неделя|месяц|день|час|минута)\b.*\b(внутри|до|перед)\b",
            r"\b(нужно|надо|обязательно|необходимо)\b",
            r"\b(план|задача|задание|работа|дело)\b",
            r"\b(напомни|напоминай|не_забудь)\b",
        ],
        "en": [
            r"\b(do|write|send|add|remove|update|check|find|get|give|tell|reply|respond)\b",
            r"\b(tomorrow|later|soon|eventually)\b.*\b(do|write|send|add|remove|update|check)\b",
            r"\b(today|tomorrow|week|month|day|hour|minute)\b.*\b(within|by|before)\b",
            r"\b(need|must|have_to|required|necessary)\b",
            r"\b(plan|task|task|work|job)\b",
            r"\b(remind|remind_me|don't_forget)\b",
        ],
    }

    # Vazifa emaslik ko'rsatkichlari (false positive kamaytirish)
    NON_TASK_INDICATORS = {
        "uz": [
            r"\b(salom|assalom| Salom|hayr|xayr|rahmat|raxmat)\b",
            r"\b(ha|yo'q|ok|okey|oke)\b",
            r"\b(nima|qanday|qayer|qachon|kim)\b.*\?",  # Savollar
            r"^(ha|yo'q|ok)$",
        ],
        "ru": [
            r"\b(привет|пока|спасибо|хорошо|да|нет)\b",
            r"\b(что|как|где|когда|кто)\b.*\?",
        ],
        "en": [
            r"\b(hi|hello|bye|thanks|ok|okay)\b",
            r"\b(what|how|where|when|who)\b.*\?",
        ],
    }

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Patternlarni compile qilish."""
        self.task_patterns = {}
        self.non_task_patterns = {}
        for lang, patterns in self.TASK_INDICATORS.items():
            self.task_patterns[lang] = [re.compile(p, re.IGNORECASE) for p in patterns]
        for lang, patterns in self.NON_TASK_INDICATORS.items():
            self.non_task_patterns[lang] = [re.compile(p, re.IGNORECASE) for p in patterns]

    def _detect_language(self, text: str) -> str:
        """Oddiy til aniqlash."""
        uz_chars = set("ўғҳқң")
        ru_chars = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя")
        text_lower = text.lower()
        uz_count = sum(1 for c in text_lower if c in uz_chars)
        ru_count = sum(1 for c in text_lower if c in ru_chars)
        if uz_count > ru_count:
            return "uz"
        elif ru_count > uz_count:
            return "ru"
        return "en"

    def _is_non_task(self, text: str, lang: str) -> bool:
        """Vazifa emasligini tekshirish."""
        for pattern in self.non_task_patterns.get(lang, []):
            if pattern.search(text):
                return True
        return False

    def _calculate_confidence(self, text: str, lang: str, has_time: bool, has_action: bool) -> float:
        """Ishonch darajasini hisoblash (0-1)."""
        confidence = 0.0
        if has_action:
            confidence += 0.4
        if has_time:
            confidence += 0.3
        # Uzunlik
        if len(text.split()) > 5:
            confidence += 0.1
        if len(text.split()) > 10:
            confidence += 0.1
        # Majburiyat so'zlari
        obligation_words = {"kerak", "lozim", "shart", "majbur", "нужно", "надо", "must", "need"}
        if any(w in text.lower() for w in obligation_words):
            confidence += 0.1
        return min(confidence, 1.0)

    def _extract_time(self, text: str) -> Optional[datetime]:
        """Matndan vaqtni aniqlash."""
        now = datetime.now()
        text_lower = text.lower()

        # Bugun
        if "bugun" in text or "сегодня" in text or "today" in text:
            return datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

        # Ertaga
        if "ertaga" in text or "завтра" in text or "tomorrow" in text:
            return (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)

        # Hafta
        if "hafta" in text or "неделя" in text or "week" in text:
            return (datetime.now() + timedelta(weeks=1)).replace(hour=10, minute=0, second=0, microsecond=0)

        # Oy
        if "oy" in text or "месяц" in text or "month" in text:
            return (datetime.now() + timedelta(days=30)).replace(hour=10, minute=0, second=0, microsecond=0)

        # Soat/daqiqa
        time_patterns = [
            r"(\d{1,2})[:\.](\d{2})",  # 14:30
            r"(\d{1,2})\s*(soat|час|hour)",  # 14 soat
            r"(\d{1,2})\s*(daqiqa|минут|minute)",  # 30 daqiqa
        ]
        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                if ":" in match.group(0) or "." in match.group(0):
                    hour = int(match.group(1))
                    minute = int(match.group(2))
                else:
                    hour = int(match.group(1))
                    minute = 0
                return datetime.now().replace(hour=min(hour, 23), minute=min(minute, 59), second=0, microsecond=0)

        return None

    def _extract_priority(self, text: str) -> TaskPriority:
        """Ustuvorlikni aniqlash."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["shoshilinch", "tezkor", "darhol", "urgence", "urgent", "asap", "asap"]):
            return TaskPriority.URGENT
        if any(w in text_lower for w in ["muhim", "important", "важн"]):
            return TaskPriority.HIGH
        if any(w in text_lower for w in ["oddiy", "oddiygina", "simple", "просто"]):
            return TaskPriority.LOW
        return TaskPriority.NORMAL

    def extract_tasks(self, text: str, sender_id: int = None, recipient_id: int = None) -> List[ExtractedTask]:
        """Matndan vazifalarni ajratib olish."""
        if not text or len(text.strip()) < 3:
            return []

        lang = self._detect_language(text)

        # Vazifa emasligini tekshirish
        if self._is_non_task(text, lang):
            return []

        tasks = []

        # 1. To'g'ri buyruq shakli: "Vazifa nomi | 25.12 14:00 | Tavsif"
        if "|" in text:
            parts = text.split("|")
            title = parts[0].strip()
            due_at = None
            if len(parts) > 1:
                due_at = self._extract_time(parts[1])
            description = parts[2].strip() if len(parts) > 2 else None
            tasks.append(ExtractedTask(
                title=title,
                description=description,
                due_at=due_at,
                priority=self._extract_priority(text),
                confidence=0.9,
                source_text=text,
            ))

        # 2. Tabiiy til: "Ertaga 14:00 da mijoz bilan uchrashuv kerak"
        # Action + Time pattern
        action_patterns = [
            r"(bajar|yoz|yubor|qo'sh|o'chir|yangila|tekshir|qidir|top|ol|ber|ayt|gapir|javob)\s+(.+?)(?:\s+(bugun|ertaga|hafta|oy|soat|daqiqa|ichida|gacha|oldin))?",
            r"(сделай|напиши|отправь|добавь|удали|обнови|проверь|найди)\s+(.+?)(?:\s+(сегодня|завтра|неделя|месяц|час|минут|внутри|до))?",
            r"(do|write|send|add|remove|update|check|find)\s+(.+?)(?:\s+(today|tomorrow|week|month|hour|minute|within|by))?",
        ]

        has_action = False
        has_time = False
        for pattern in self.task_patterns.get(self._detect_language(text), []):
            if pattern.search(text):
                has_action = True
                break

        due_at = self._extract_time(text)
        if due_at:
            has_time = True

        confidence = self._calculate_confidence(text, self._detect_language(text), has_time, has_action)

        if confidence > 0.3:  # Minimal threshold
            # Title ni matndan ajratish (birinchi gap)
            sentences = re.split(r'[.!?]', text)
            title = sentences[0].strip()[:100] if sentences else text[:100]

            tasks.append(ExtractedTask(
                title=title,
                description=text if len(text) > len(title) else None,
                due_at=due_at,
                priority=self._extract_priority(text),
                confidence=confidence,
                source_text=text,
            ))

        return tasks


class TaskAutoCreator:
    """Avtomatik vazifa yaratish servisi."""

    def __init__(self, db, task_extractor: TaskExtractor):
        self.db = db
        self.extractor = task_extractor

    async def process_message(self, event, msg_controller, sender_id: int, sender_name: str, message_text: str) -> List[int]:
        """Xabarni tahlil qilish va vazifalar yaratish."""
        tasks = self.extractor.extract_tasks(message_text)
        created_ids = []

        for task in tasks:
            if task.confidence < 0.5:  # Faqat ishonchli vazifalar
                continue

            # Vazifa yaratish
            from src.services.crm_integration import get_task_service
            from src.context import app_ctx

            task_service = get_task_service(app_ctx.db)
            due_at = task.due_at

            result = await get_task_service(app_ctx.db).create_task(
                user_id=sender_id,
                title=task.title,
                due_at=due_at,
                description=task.description,
                priority=task.priority.value,
            )

            if result.get("success"):
                task_id = result["task_id"]
                created_ids.append(task_id)
                logger.info(f"[TASK_AUTO] Created task {task_id}: {task.title} for user {sender_id}")

        return created_ids


def get_task_extractor() -> TaskExtractor:
    """TaskExtractor singleton."""
    if not hasattr(get_task_extractor, "_instance"):
        get_task_extractor._instance = TaskExtractor()
    return get_task_extractor._instance


def get_task_auto_creator(db) -> TaskAutoCreator:
    """TaskAutoCreator singleton."""
    if not hasattr(get_task_auto_creator, "_instance"):
        get_task_auto_creator._instance = TaskAutoCreator(db, get_task_extractor())
    return get_task_auto_creator._instance