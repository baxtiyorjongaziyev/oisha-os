"""Scheduler for AI Promises Tracker (24/7 Cloud Brain Synthesizer)."""
import asyncio
import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Optional

from src.database import get_db
from src.services.utils.free_ai_router import FreeAIProviderRouter
from src.settings import settings
from src.utils.git_sync import push_vault_to_remote

logger = logging.getLogger(__name__)

# Bir xil vazifalar ro'yxati uchun digest qayta yuborilmasin (restartdan keyin ham).
STATE_FILE = Path("data/brain_digest_state.txt")

# Test/demo yozuvlar — real ish emas, tahlilga kirmaydi. Sarlavha + tavsif
# bo'yicha qisman moslik: bazadagi matn biroz farq qilsa ham ushlanadi.
DEMO_TASK_PATTERNS = (
    re.compile(r"\bbuyurtmachi a\b"),
    re.compile(r"\bdastur xatolarini tuzatish\b"),
    re.compile(r"\bsotuvchilar uchun qo'llanma\b"),
)
_APOSTROPHES = str.maketrans({c: "'" for c in "\u2018\u2019\u02bb\u02bc`"})


def _is_demo_task(title: Optional[str], description: Optional[str]) -> bool:
    text = f"{title or ''} {description or ''}".lower().translate(_APOSTROPHES)
    text = " ".join(text.split())
    return any(p.search(text) for p in DEMO_TASK_PATTERNS)


def _digest_enabled() -> bool:
    return os.getenv("ENABLE_BRAIN_DIGEST", "1").strip().lower() not in ("0", "false", "no", "off")


def _data_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _load_last_hash() -> str:
    try:
        return STATE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _save_last_hash(value: str) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(value, encoding="utf-8")
    except OSError as e:
        logger.warning(f"[BRAIN_SYNTH] Could not persist digest hash: {e}")

PROMPT = """
Sen Oisha-OS uchun AI "Ikkinchi Miya" (Second Brain) tahlilchisisan.
Quyidagi so'nggi vazifalar, faoliyatlar va muloqot loglarini tahlil qil.
Maqsading — Ikkinchi Miyaning 5 asosiy yo'nalishi bo'yicha foydali xulosalar chiqarish.

Javobni albatta O'ZBEK TILIDA yoz. Inglizcha so'z va iboralardan foydalanma.

Natijani AYNAN quyidagi 5 bo'lim bilan markdown ro'yxat shaklida ber:

### 1. 🔄 Kontekst almashinuvi (Muhim qarorlar va keyingi qadamlar)
- Faol loyihalar bo'yicha aniq keyingi qadamni ajratib ber, shunda foydalanuvchi darhol ishni davom ettira oladi.

### 2. 💡 Kontent g'oyalari (Fikrlar va iqtiboslar)
- Aytilgan qiziqarli fikrlar, iqtiboslar yoki marketing/kontent g'oyalarini ajratib ber.

### 3. 📜 SOP va agent qoidalari
- Foydalanuvchi aytgan yashirin qoidalar, ko'rsatmalar yoki ish jarayonlarini ajratib ber. Ular doimiy SOP (standart ish tartibi) ga aylanadi.

### 4. 🤝 Shaxsiy CRM (Va'dalar kuzatuvchisi)
- Aniq odamlar bilan bog'liq bajarilmagan va'dalar yoki kelishuvlarni ajratib ber.

### 5. 🧩 Naqsh aniqlash (Bog'lanishlar)
- Turli vazifalar yoki muammolar orasidagi oshkora bo'lmagan bog'lanishlarni top. A qanday qilib B bilan bog'liq?

Agar biror bo'limda tegishli ma'lumot bo'lmasa, shunday yoz: "Ma'lumot yo'q."

Ma'lumotlar:
{data}
"""


async def _fetch_recent_data() -> str:
    try:
        db = get_db()
        conn = await db.get_connection()
        cursor = await conn.execute(
            "SELECT title, description FROM tasks WHERE status='Pending' ORDER BY created_at DESC LIMIT 20"
        )
        rows = await cursor.fetchall()
        data = "\n".join(
            f"Task: {r[0]} - {r[1]}"
            for r in rows
            if (r[0] or r[1]) and not _is_demo_task(r[0], r[1])
        )
        return data.strip()
    except Exception as e:
        logger.error(f"[BRAIN_SYNTH] Error fetching data: {e}")
        return ""


async def _generate_insights(data: str) -> Optional[str]:
    if not data:
        return None

    try:
        router = FreeAIProviderRouter()
        result = await router.generate_text(
            prompt=PROMPT.format(data=data),
            max_tokens=1500,
            temperature=0.3,
        )
        content = (result.text or "").strip()
        return content if content else None
    except Exception as e:
        logger.warning(f"[BRAIN_SYNTH] AI synthesis failed: {e}")
        return None


async def run_brain_synthesizer_cycle(bot_client, target_chat_id: int):
    """Fetches data, runs analysis, and sends digest to Telegram (fail-closed)."""
    if not _digest_enabled():
        logger.info("[BRAIN_SYNTH] Disabled via ENABLE_BRAIN_DIGEST. Skipping digest.")
        return

    logger.info("[BRAIN_SYNTH] Starting synthesis cycle...")
    data = await _fetch_recent_data()
    if not data:
        logger.info("[BRAIN_SYNTH] No pending tasks to synthesize. Skipping digest.")
        return

    data_hash = _data_hash(data)
    if data_hash == _load_last_hash():
        logger.info("[BRAIN_SYNTH] Pending tasks unchanged since last digest. Skipping digest.")
        return

    insights = await _generate_insights(data)
    if not insights:
        logger.info("[BRAIN_SYNTH] No insights generated (providers unavailable or empty). Skipping digest.")
        return

    if "Ma'lumot yo'q" in insights and insights.count("Ma'lumot yo'q") >= 4:
        logger.info("[BRAIN_SYNTH] Insufficient new insights across pillars. Skipping digest.")
        return

    message = f"🧠 <b>Second Brain Evolution Digest</b>\n\n{insights}"

    try:
        if hasattr(bot_client, "send_message"):
            await bot_client.send_message(
                target_chat_id,
                message,
                parse_mode="HTML"
            )
            logger.info("[BRAIN_SYNTH] Digest sent successfully.")
            _save_last_hash(data_hash)
            if getattr(settings, "VAULT_PATH", None):
                await push_vault_to_remote(settings.VAULT_PATH)
    except Exception as e:
        logger.error(f"[BRAIN_SYNTH] Failed to send digest: {e}")


async def brain_synthesizer_loop(bot_client, target_chat_id: int):
    """Async loop that runs every 6 hours to synthesize data."""
    await asyncio.sleep(180)  # Boot delay
    logger.info("[BRAIN_SYNTH] 24/7 Synthesizer loop started.")

    while True:
        try:
            await run_brain_synthesizer_cycle(bot_client, target_chat_id)
        except Exception as e:
            logger.error(f"[BRAIN_SYNTH] Error in loop: {e}")

        # Har 6 soatda aylanadi (21600 soniya)
        await asyncio.sleep(21600)
