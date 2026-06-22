"""
UserbotLearner — Telethon userbot orqali barcha mavjud ma'lumotlarni o'qib,
SelfLearningEngine'ga uzatadi. Oisha o'zini o'zi doimiy o'qitib boradi.

Scan davri:
  - Birinchi ishga tushganda: oxirgi 7 kunlik xabarlar
  - Keyingi sikllar: faqat oxirgi scan'dan keyin kelgan yangi xabarlar
  - Har 2 soatda bir marta ishga tushadi

Filtr:
  - Faqat 2+ kishilik suhbatlar (DM va guruhlar)
  - Minimal 3 ta xabar va 50 ta belgi bo'lgan bloklar
  - Bir siklda maksimal 30 ta suhbat bloki (Gemini rate limit)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from src.time_utils import get_local_now

if TYPE_CHECKING:
    from telethon import TelegramClient
    from src.services.core.self_learning import SelfLearningEngine
    from src.services.core.oisha_memory import OishaMemory
    from src.database import Database

logger = logging.getLogger(__name__)

_MAX_CONVS_PER_CYCLE = 30
_MSG_WINDOW_HOURS = 2
_INITIAL_LOOKBACK_DAYS = 7
_MIN_MSG_COUNT = 3
_MIN_CONV_LEN = 50
_SCAN_INTERVAL_HOURS = 2


class UserbotLearner:
    """Userbot'dagi barcha dialoglarni skanlab, SelfLearningEngine'ga o'rgatadi."""

    def __init__(
        self,
        db: "Database",
        learning_engine: "SelfLearningEngine",
        memory: Optional["OishaMemory"] = None,
    ):
        self.db = db
        self.learning = learning_engine
        self.memory = memory

    async def ensure_tables(self):
        async with await self.db.get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS userbot_scan_state (
                    dialog_id INTEGER PRIMARY KEY,
                    dialog_name TEXT,
                    last_message_id INTEGER DEFAULT 0,
                    last_scanned_at TEXT
                )
            """)
            await conn.commit()

    async def scan_and_learn(self, client: "TelegramClient") -> dict:
        """Barcha dialoglarni skanlab darslar chiqaradi. Natijani dict qaytaradi."""
        total_convs = 0
        total_lessons = 0
        dialogs_scanned = 0

        try:
            dialogs = await client.get_dialogs(limit=200)
        except Exception as exc:
            logger.warning("[LEARN] Dialoglarni olishda xato: %s", exc)
            return {"dialogs": 0, "conversations": 0, "lessons": 0}

        for dialog in dialogs:
            if total_convs >= _MAX_CONVS_PER_CYCLE:
                break

            if _should_skip_dialog(dialog):
                continue

            try:
                lessons_count = await self._process_dialog(client, dialog)
                if lessons_count > 0:
                    total_lessons += lessons_count
                total_convs += 1
                dialogs_scanned += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("[LEARN] Dialog %s xato: %s", getattr(dialog, "name", "?"), exc)

            await asyncio.sleep(0.5)

        logger.info(
            "[LEARN] Scan tugadi: %d dialog, %d suhbat, %d dars",
            dialogs_scanned, total_convs, total_lessons,
        )
        return {"dialogs": dialogs_scanned, "conversations": total_convs, "lessons": total_lessons}

    async def _process_dialog(self, client: "TelegramClient", dialog) -> int:
        """Bitta dialog'ni qayta ishlab, darslar chiqaradi."""
        dialog_id = dialog.id
        dialog_name = getattr(dialog, "name", "") or str(dialog_id)

        last_msg_id = await self._get_last_msg_id(dialog_id)
        cutoff = datetime.utcnow() - timedelta(days=_INITIAL_LOOKBACK_DAYS)

        messages = []
        try:
            async for msg in client.iter_messages(dialog, limit=150, min_id=last_msg_id):
                if msg.date and msg.date.replace(tzinfo=None) < cutoff and last_msg_id == 0:
                    break
                if msg.text and msg.text.strip():
                    sender = await _get_sender_name(msg)
                    messages.append((msg.id, msg.date, sender, msg.text.strip()))
        except Exception as exc:
            logger.debug("[LEARN] iter_messages xato (%s): %s", dialog_name, exc)
            return 0

        if not messages:
            return 0

        messages.sort(key=lambda x: x[1])

        conv_blocks = _group_into_conversations(messages)

        total_lessons = 0
        for block in conv_blocks:
            if len(block) < _MIN_MSG_COUNT:
                continue
            text = "\n".join(f"{sender}: {msg}" for _, _, sender, msg in block)
            if len(text) < _MIN_CONV_LEN:
                continue

            client_type = _infer_client_type(dialog)
            lessons = await self.learning.extract_lessons(
                conversation=text,
                client_type=client_type,
                outcome="unknown",
                manager_name="",
                chat_id=dialog_id,
            )
            total_lessons += len(lessons)

            if self.memory:
                await self.memory.learn_from_conversation(
                    conversation=text,
                    entity_type=client_type,
                    entity_name=dialog_name,
                    source="userbot_scan",
                )

            await asyncio.sleep(1.5)

        if messages:
            max_id = max(m[0] for m in messages)
            await self._save_scan_state(dialog_id, dialog_name, max_id)

        return total_lessons

    async def _get_last_msg_id(self, dialog_id: int) -> int:
        async with await self.db.get_connection() as conn:
            row = await conn.execute(
                "SELECT last_message_id FROM userbot_scan_state WHERE dialog_id = ?",
                (dialog_id,),
            )
            result = await row.fetchone()
            return result[0] if result else 0

    async def _save_scan_state(self, dialog_id: int, dialog_name: str, last_id: int):
        now = get_local_now().isoformat()
        async with await self.db.get_connection() as conn:
            await conn.execute(
                """INSERT INTO userbot_scan_state (dialog_id, dialog_name, last_message_id, last_scanned_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(dialog_id) DO UPDATE SET
                     last_message_id = excluded.last_message_id,
                     last_scanned_at = excluded.last_scanned_at,
                     dialog_name = excluded.dialog_name""",
                (dialog_id, dialog_name, last_id, now),
            )
            await conn.commit()


def _group_into_conversations(
    messages: list,
    window_hours: int = _MSG_WINDOW_HOURS,
) -> list[list]:
    """Xabarlarni vaqt oynasi bo'yicha suhbat bloklarga ajratadi."""
    if not messages:
        return []

    blocks: list[list] = []
    current: list = [messages[0]]

    for msg in messages[1:]:
        prev_time = current[-1][1]
        curr_time = msg[1]
        delta = (curr_time.replace(tzinfo=None) - prev_time.replace(tzinfo=None)).total_seconds()
        if delta > window_hours * 3600:
            blocks.append(current)
            current = [msg]
        else:
            current.append(msg)

    if current:
        blocks.append(current)

    return blocks


def _should_skip_dialog(dialog) -> bool:
    """Bot, broadcast channel va servis dialoglarini o'tkazib yuboradi."""
    try:
        from telethon.tl.types import User, Channel
        entity = getattr(dialog, "entity", None)
        if entity is None:
            return True
        if isinstance(entity, User) and getattr(entity, "bot", False):
            return True
        if isinstance(entity, Channel) and getattr(entity, "broadcast", False):
            return True
        if getattr(dialog, "name", "") in ("Telegram", ""):
            return True
    except Exception:
        pass
    return False


def _infer_client_type(dialog) -> str:
    """Dialog turini aniqlaydi: dm | group | channel."""
    from telethon.tl.types import User, Chat, Channel
    entity = getattr(dialog, "entity", None)
    if isinstance(entity, User):
        return "dm"
    if isinstance(entity, Chat):
        return "group"
    if isinstance(entity, Channel):
        return "channel" if getattr(entity, "broadcast", False) else "supergroup"
    return "unknown"


async def _get_sender_name(msg) -> str:
    try:
        sender = await msg.get_sender()
        if sender is None:
            return "Unknown"
        first = getattr(sender, "first_name", "") or ""
        username = getattr(sender, "username", "") or ""
        return first or username or str(getattr(sender, "id", "Unknown"))
    except Exception:
        return "Unknown"
