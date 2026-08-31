"""
Airtable deadlines monitor and notifications.
"""
from __future__ import annotations

import datetime
import logging
import os
from typing import Any, Dict, List, Optional

from aiogram import Bot
import src.config as config
from src.database import Database
from src.services.core.agent_loop import AgentTask
from src.services.core.tool_adapters import (
    build_default_tool_registry,
    send_group_message_with_fallback,
)
from src.services.proactive.formatters import (
    _mention,
    _run_notification_agent,
    _safe_text,
)
from src.services.proactive.reminders import _execute_telegram_notification
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

_deadline_sent_keys: set = set()
_DEADLINE_CLAIM_DIR = "data/job_claims"


def _resolve(attr_name, default_val):
    import sys
    pw = sys.modules.get("src.services.core.proactive_worker")
    if pw is not None:
        return getattr(pw, attr_name, default_val)
    return default_val


def _prune_stale_claims(max_age_days: int = 2) -> None:
    import time
    claim_dir = _resolve("_DEADLINE_CLAIM_DIR", _DEADLINE_CLAIM_DIR)
    cutoff = time.time() - max_age_days * 86400
    try:
        for name in os.listdir(claim_dir):
            path = os.path.join(claim_dir, name)
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
    except OSError:
        return


def _claim_on_disk(claim_key: str) -> bool:
    claim_dir = _resolve("_DEADLINE_CLAIM_DIR", _DEADLINE_CLAIM_DIR)
    try:
        os.makedirs(claim_dir, exist_ok=True)
        path = os.path.join(claim_dir, claim_key + ".lock")
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        _prune_stale_claims()
        return True
    except FileExistsError:
        return False
    except OSError as exc:
        logger.warning(
            "[PROACTIVE] Disk claim xatosi (%s) — DB/xotiraga fallback", exc
        )
        return True


def _release_on_disk(claim_key: str) -> None:
    claim_dir = _resolve("_DEADLINE_CLAIM_DIR", _DEADLINE_CLAIM_DIR)
    path = os.path.join(claim_dir, claim_key + ".lock")
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        return


async def check_airtable_deadlines():
    """Airtable 24 soatlik deadline monitoringi.

    Kuniga faqat 2 marta (10:00 va 15:00 Toshkent) yuboriladi.
    Dedup uch qavatli va **yuborishdan oldin** band qilinadi:
      1) soat filtri, 2) in-memory set, 3) DB'da atomik claim.
    Claim yuborishdan oldin olinadi — shuning uchun parallel scheduler'lar
    (src/scheduler.py va src/schedulers/background_monitor.py) yoki qayta
    ishga tushgan process bir xil xabarni takrorlay olmaydi. Yuborish
    muvaffaqiyatsiz bo'lsa, claim bekor qilinadi va keyingi urinishda qayta
    tekshiriladi.
    """
    from src.services.core.airtable_sync import AirtableSync  # type: ignore
    import src.config as config

    get_now_fn = _resolve('get_local_now', get_local_now)
    now = get_now_fn()
    today = now.strftime("%Y-%m-%d")
    target_hours = [10, 15]

    # 1) Strict hour filter. Minute oynasi OLIB TASHLANDI: agar loop 10:00–10:10
    # orasida bir necha marta ishlasa, oyna har run'da qayta yuborishга ruxsat
    # berardi. Endi butun soat davomida bitta claim yetarli.
    if now.hour not in target_hours:
        return  # Silent skip — no log spam

    # Bitta kunlik kalit (soat emas). 10:00 va 15:00 ni ajratmaymiz — kuniga
    # bitta deadline hisoboti kifoya. Ikki oynali kalit ("_{now.hour}") ikki
    # scheduler + restart bilan birga takror yuborishning asosiy sababi edi.
    job_key = f"airtable_deadline_alert_{today}"

    # 2) In-memory dedup (fastest, no I/O)
    mem_key = f"{job_key}_{today}"
    if mem_key in _resolve('_deadline_sent_keys', _deadline_sent_keys):
        return

    # 3) Disk claim — bitta hostdagi restartlar uchun (DB ishlamasa ham himoya)
    if not _claim_on_disk(mem_key):
        _resolve('_deadline_sent_keys', _deadline_sent_keys).add(mem_key)
        return

    # 4) DB claim (atomik, ko'p host / parallel loop'lardan himoya qiladi).
    # Bu YAGONA ishonchli qatlam — mem set va disk lock Cloud Run'da har
    # instance uchun alohida, shuning uchun ko'p-instance holatida himoya qilmaydi.
    db = None
    claimed_in_db = False
    try:
        db_cls = _resolve('Database', Database)
        db = db_cls()
        # Oldindan tekshir: agar bugun allaqachon yuborilgan bo'lsa, umuman kirmaymiz.
        if hasattr(db, "is_job_run") and await db.is_job_run(job_key, today):
            _resolve('_deadline_sent_keys', _deadline_sent_keys).add(mem_key)
            return
        claimed_in_db = await db.claim_job_run(job_key, today)
        if not claimed_in_db:
            # Boshqa process allaqachon band qilgan / yuborgan
            _resolve('_deadline_sent_keys', _deadline_sent_keys).add(mem_key)
            return
    except Exception as e:
        logger.warning(f"[PROACTIVE] DB claim failed: {e}")
        db = None

    # Claim olindi — memory'ni ham darhol belgilaymiz (yuborishdan OLDIN),
    # aks holda xatolik yuz bersa loop har iteratsiyada qayta yuboradi.
    _resolve('_deadline_sent_keys', _deadline_sent_keys).add(mem_key)

    logger.info("Project deadline check started...")

    async def _release() -> None:
        """Qayta urinish uchun claim'ni bo'shatish.

        DIQQAT: faqat xabar HALI YUBORILMAGAN bo'lsa chaqirilsin (Airtable
        fetch xatosi, token yo'q, va h.k.). Xabar yuborilgandan keyin
        release qilish 5-daqiqalik loop'da takror yuborishga olib keladi —
        27.08 dagi 12 martalik spam aynan shundan edi.
        """
        _resolve('_deadline_sent_keys', _deadline_sent_keys).discard(mem_key)
        _release_on_disk(mem_key)
        if db is not None and claimed_in_db:
            try:
                await db.release_job_run(job_key, today)
            except Exception:
                logger.error("Exception handled in %s", __name__, exc_info=True)

    try:
        sync = AirtableSync()
        upcoming = sync.get_upcoming_deadlines(hours=24)
    except Exception as e:
        logger.error(f"[PROACTIVE] Airtable fetch failed: {e}")
        await _release()
        return

    if not upcoming:
        # No deadlines — claim saqlanadi, bugun qayta tekshirilmaydi
        return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = (
        getattr(config, "PROJECTS_GROUP_ID", None)
        or getattr(config, "WOW_SERVICE_GROUP_ID", None)
        or getattr(config, "TEAM_GROUP_ID", None)
    )
    thread_id = (
        getattr(config, "PROJECTS_TOPIC_ID", None)
        or getattr(config, "WOW_SERVICE_TOPIC_ID", None)
        or getattr(config, "TOPIC_TASKS_ID", None)
    )
    if not (bot_token and group_id):
        await _release()
        return

    bot_cls = _resolve('Bot', Bot)
    bot = bot_cls(token=bot_token)

    msg = "⏳ **URGENT PROJECT DEADLINE (24h)**\n\nQuyidagi topshiriqlar muddati tugashiga 1 kun qoldi:\n"
    for p in upcoming[:5]:
        fields = p.get("fields", {})
        p_name = AirtableSync._get_field(fields, "project_name")
        if not p_name or p_name == "Noma'lum":
            p_name = fields.get("Loyiha ID") or fields.get("AmoCRM_ID") or p.get("id") or "Nomsiz"
        stage = AirtableSync._get_field(fields, "stage") or "—"
        deadline = AirtableSync._get_field(fields, "deadline") or "—"
        msg += f"- {p_name} (Bosqich: {stage}, Muddat: {deadline})\n"

    _send_fn = _resolve(
        "send_group_message_with_fallback", send_group_message_with_fallback
    )
    try:
        res = _send_fn(
            bot,
            chat_id=group_id,
            text=msg,
            thread_id=thread_id,
            parse_mode="Markdown",
            allow_userbot_fallback=False,
        )
        if hasattr(res, "__await__"):
            await res
    except Exception as e:
        # Yuborish HAQIQATAN muvaffaqiyatsiz — claim'ni bo'shatib, keyingi
        # oynada qayta urinishga ruxsat beramiz.
        logger.error(f"[XATO] Airtable deadline alert (yuborilmadi): {e}")
        await _release()
        return

    # Bu yerga yetdik = xabar yuborildi. Claim MULOZIM SAQLANADI.
    # Yuborishdan keyingi hech qanday xatolik (log, formatlash, va h.k.)
    # release'ga sabab bo'lmasin.
    try:
        logger.info(f"[PROACTIVE] {len(upcoming)} ta loyiha deadline'i yaqin — xabar yuborildi.")
    except Exception:
        pass



