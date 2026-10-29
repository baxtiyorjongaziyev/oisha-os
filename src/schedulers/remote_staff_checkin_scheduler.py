"""Remote staff hourly check-in scheduler.

Periodically asks remote staff (e.g. @RayxonJonbranding) in the Sales group
(-1003854308552, topic 115) about recent conversations and current tasks,
augmenting questions with real telephony facts from MoiZvonki when available.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.settings import settings
from src.time_utils import get_local_now

logger = logging.getLogger("RemoteStaffCheckin")

SALES_GROUP_ID = -1003854308552
SALES_REPORT_TOPIC_ID = 115

DEFAULT_REP_NAME = "Rayxon"
DEFAULT_REP_TG = "@RayxonJonbranding"
DEFAULT_REP_EMAILS = ["rayxona@jonbranding.uz", "xayrullayevna006@gmail.com"]

MIN_CHECKIN_INTERVAL_SECONDS = 45 * 60  # 45 daqiqa minimal oraliq
STATE_FILE = "data/checkin_state.json"


def get_checkin_state(db_path: str = "data/bot.db", state_file: str = STATE_FILE) -> dict:
    """Retrieve persistent check-in deduplication state from JSON file and kv_settings."""
    state = {"last_hour_key": "", "last_sent_ts": 0, "last_text_hash": ""}

    # 1. Read from fast persistent JSON file
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                state["last_hour_key"] = data.get("last_hour_key", "")
                state["last_sent_ts"] = int(data.get("last_sent_ts", 0))
                state["last_text_hash"] = data.get("last_text_hash", "")
                if state["last_hour_key"]:
                    return state
        except Exception as exc:
            logger.debug("[CHECKIN] Error reading state_file: %s", exc)

    # 2. Check kv_settings if state file empty
    try:
        conn = sqlite3.connect(db_path, timeout=3.0)
        c = conn.cursor()
        c.execute(
            "SELECT key, value FROM kv_settings WHERE key IN ("
            "'CHECKIN_LAST_HOUR_KEY', 'CHECKIN_LAST_SENT_TS', 'CHECKIN_LAST_TEXT_HASH')"
        )
        for k, v in c.fetchall():
            if k == "CHECKIN_LAST_HOUR_KEY":
                state["last_hour_key"] = str(v or "")
            elif k == "CHECKIN_LAST_SENT_TS":
                try:
                    state["last_sent_ts"] = int(float(v or 0))
                except (ValueError, TypeError):
                    pass
            elif k == "CHECKIN_LAST_TEXT_HASH":
                state["last_text_hash"] = str(v or "")
        conn.close()
    except Exception as exc:
        logger.debug("[CHECKIN] Error reading kv_settings checkin state: %s", exc)

    return state


def save_checkin_dispatch(
    hour_key: str,
    sent_ts: int,
    text_hash: str,
    db_path: str = "data/bot.db",
    state_file: str = STATE_FILE,
) -> None:
    """Save persistent check-in dispatch state to both JSON file and DB."""
    # 1. Write to state file first (always succeeds atomically)
    try:
        os.makedirs(os.path.dirname(state_file) or ".", exist_ok=True)
        tmp_file = f"{state_file}.tmp"
        payload = {
            "last_hour_key": hour_key,
            "last_sent_ts": sent_ts,
            "last_text_hash": text_hash,
            "updated_at": datetime.now().isoformat(),
        }
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp_file, state_file)
    except Exception as exc:
        logger.warning("[CHECKIN] Error writing state file: %s", exc)

    # 2. Write to DB as backup
    try:
        now_iso = datetime.now().isoformat()
        conn = sqlite3.connect(db_path, timeout=5.0)
        c = conn.cursor()
        c.execute(
            """
            INSERT OR REPLACE INTO kv_settings (key, value, updated_at)
            VALUES
                ('CHECKIN_LAST_HOUR_KEY', ?, ?),
                ('CHECKIN_LAST_SENT_TS', ?, ?),
                ('CHECKIN_LAST_TEXT_HASH', ?, ?)
            """,
            (hour_key, now_iso, str(sent_ts), now_iso, text_hash, now_iso),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.debug("[CHECKIN] DB save backup notice: %s", exc)


def can_dispatch_checkin(
    now: datetime,
    text: str,
    force: bool = False,
    db_path: str = "data/bot.db",
    state_file: str = STATE_FILE,
) -> tuple[bool, str]:
    """Check deduplication rules to guarantee: bitta narsani ketma-ket ikki marta yubormasin."""
    if force:
        return True, "forced"

    hour_key = now.strftime("%Y-%m-%d-%H")
    text_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    state = get_checkin_state(db_path=db_path, state_file=state_file)

    # 1. Bir soat ichida qayta yubormaslik
    if state["last_hour_key"] == hour_key:
        return False, f"already_sent_this_hour_{hour_key}"

    # 2. Kamida 45 daqiqa cooldown
    elapsed = int(now.timestamp()) - state["last_sent_ts"]
    if 0 <= elapsed < MIN_CHECKIN_INTERVAL_SECONDS:
        return False, f"cooldown_active_{elapsed}s_of_{MIN_CHECKIN_INTERVAL_SECONDS}s"

    # 3. Aynan bir xil matnni takrorlamaslik
    if state["last_text_hash"] and state["last_text_hash"] == text_hash:
        return False, "duplicate_identical_content"

    return True, "ok"


def is_enabled() -> bool:
    val = os.getenv("REMOTE_STAFF_CHECKIN_ENABLED", "1").strip().lower()
    return val in {"1", "true", "yes", "on"}


def get_target_destination() -> tuple[int, Optional[int]]:
    raw_grp = os.getenv("REMOTE_CHECKIN_GROUP_ID")
    group_id = int(raw_grp) if raw_grp else (getattr(settings, "CRM_SALES_REPORT_GROUP_ID", None) or SALES_GROUP_ID)

    raw_topic = os.getenv("REMOTE_CHECKIN_TOPIC_ID")
    if raw_topic is not None:
        topic_id = int(raw_topic) if raw_topic.strip() else None
    else:
        topic_id = getattr(settings, "CRM_SALES_REPORT_TOPIC_ID", SALES_REPORT_TOPIC_ID)

    return group_id, topic_id


def is_work_hour(now: datetime) -> bool:
    """Check if current time is within business hours (10:00 - 19:00, Mon-Sat)."""
    if now.weekday() == 6:  # Sunday
        return False
    return 10 <= now.hour <= 19


def format_phone(phone: str) -> str:
    cleaned = "".join(ch for ch in str(phone or "") if ch.isdigit() or ch == "+")
    if not cleaned:
        return str(phone or "")
    digits = cleaned.lstrip("+")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return f"+998 ({digits[3:5]}) {digits[5:8]}-{digits[8:10]}-{digits[10:12]}"
    return phone


def format_duration(seconds: int) -> str:
    seconds = int(seconds or 0)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h} soat {m} daqiqa"
    if m:
        return f"{m} daqiqa" if s == 0 else f"{m} daqiqa {s} soniya"
    return f"{s} soniya"


def build_checkin_message(
    seller_name: str,
    tg_handle: str,
    now: datetime,
    activity: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a natural, human ROP message based on real MoiZvonki telephony data."""
    try:
        from src.services.core.sales_staff_copilot import get_known_staff_user_id
        known_id = get_known_staff_user_id(tg_handle)
        if known_id:
            handle = f'<a href="tg://user?id={known_id}">@{tg_handle.lstrip("@")}</a>'
        else:
            handle = tg_handle if tg_handle.startswith("@") else f"@{tg_handle}"
    except Exception:
        handle = tg_handle if tg_handle.startswith("@") else f"@{tg_handle}"

    if not activity or activity.get("total", 0) == 0:
        return (
            f"Assalomu alaykum {seller_name} ({handle})!\n\n"
            f"Oxirgi soatda telefoniyada yangi qo'ng'iroq ko'rinmadi. "
            f"Hozir qaysi mijoz yoki vazifa ustida ishlayapsiz? "
            f"Biror masala bo'yicha yordam yoki yo'nalish kerak bo'lyaptimi?"
        )

    total = activity.get("total", 0)
    answered = activity.get("answered", 0)
    solid = activity.get("solid", 0)
    total_talk = activity.get("total_talk_sec", 0)
    answered_clients = activity.get("answered_clients", [])

    client_snippets = []
    for c in answered_clients[:3]:
        num_str = format_phone(c.get("number", ""))
        name = c.get("name")
        who = f"{name} ({num_str})" if name and name != num_str else num_str
        dur = format_duration(c.get("duration", 0))
        if dur and dur != "0 soniya":
            client_snippets.append(f"{who} — {dur}")
        else:
            client_snippets.append(who)

    clients_text = ", ".join(client_snippets)

    if answered > 0 and solid > 0:
        return (
            f"Assalomu alaykum {seller_name} ({handle})!\n\n"
            f"MoiZvonkidan ko'rdim, oxirgi soatda {total} ta raqam terilib, "
            f"{answered} ta mijoz bilan sifatli gaplashibsiz ({clients_text}; jami {format_duration(total_talk)}).\n\n"
            f"Ushbu suhbatlar bo'yicha qanday kelishuvga erishildi, qaysilari bilan keyingi qadam belgilandi? "
            f"Hozir qaysi lid ustida ishlayapsiz?"
        )

    if answered > 0 and solid == 0:
        msg = (
            f"Assalomu alaykum {seller_name} ({handle})!\n\n"
            f"Oxirgi bir soatda {total} ta raqam tergansiz, shundan {answered} tasi ko'tarilibdi"
        )
        if clients_text:
            msg += f" ({clients_text})"
        msg += (
            f", lekin suhbatlar juda qisqa bo'libdi.\n\n"
            f"Bu mijozlar bilan nima bo'ldi, taklifga qiziqish bormi yoki rad etishdimi? "
            f"Hozir qaysi lidlar ustida ishlayapsiz va qanday yordam kerak?"
        )
        return msg

    return (
        f"Assalomu alaykum {seller_name} ({handle})!\n\n"
        f"Oxirgi soatda {total} ta raqam terilganini ko'rdim, afsuski hech biri ko'tarmabdi.\n\n"
        f"Ko'tarmaganlarga boshqa vaqtda qayta terish uchun AmoCRM'da vazifa qo'ydingizmi? "
        f"Hozir qaysi lidlar yoki yozishmalar ustida ishlayapsiz?"
    )


def fetch_recent_calls_for_rep(
    rep_emails: List[str],
    start_ts: int,
    end_ts: int,
) -> Optional[Dict[str, Any]]:
    email = os.environ.get("MOIZVONKI_EMAIL", "")
    api_key = os.environ.get("MOIZVONKI_API_KEY", "")
    domain = os.environ.get("MOIZVONKI_DOMAIN", "")
    if not email or not api_key:
        return None

    try:
        from scripts.daily_sales_calls_report import fetch_calls
        calls = fetch_calls(email, api_key, start_ts, end_ts, domain)
        rep_emails_lower = {e.lower() for e in rep_emails}
        rep_calls = [
            c for c in calls
            if (c.get("user_account") or "").lower() in rep_emails_lower
        ]
        total = len(rep_calls)
        answered_calls = [c for c in rep_calls if int(c.get("answered") or 0) == 1]
        answered = len(answered_calls)
        missed = total - answered
        solid = sum(1 for c in answered_calls if int(c.get("duration") or 0) >= 180)
        talk_sec = sum(int(c.get("duration") or 0) for c in answered_calls)

        answered_clients = [
            {
                "number": c.get("client_number") or "",
                "name": c.get("client_name") or "",
                "duration": int(c.get("duration") or 0),
            }
            for c in answered_calls
        ]

        return {
            "total": total,
            "answered": answered,
            "missed": missed,
            "solid": solid,
            "total_talk_sec": talk_sec,
            "answered_clients": answered_clients,
        }
    except Exception as exc:
        logger.debug("[CHECKIN] Telephony fetch non-blocking fallback: %s", exc)
        return None


async def send_remote_checkin(
    bot_runtime: Any,
    *,
    now_fn=get_local_now,
    seller_name: str = DEFAULT_REP_NAME,
    tg_handle: str = DEFAULT_REP_TG,
    rep_emails: Optional[List[str]] = None,
    force: bool = False,
) -> bool:
    if not is_enabled() and not force:
        return False

    now = now_fn()
    if not is_work_hour(now) and not force:
        logger.info("[CHECKIN] Outside work hours (%02d:%02d), skipping.", now.hour, now.minute)
        return False

    chat_id, topic_id = get_target_destination()
    if not chat_id or bot_runtime is None:
        logger.warning("[CHECKIN] Missing destination chat or bot_runtime.")
        return False

    emails = rep_emails or DEFAULT_REP_EMAILS
    end_ts = int(now.timestamp())
    start_ts = end_ts - 3600
    calls_info = await asyncio.to_thread(fetch_recent_calls_for_rep, emails, start_ts, end_ts)

    try:
        from src.services.core.sales_staff_copilot import auto_resolve_staff_id
        from src.context import app_ctx
        if getattr(app_ctx, "client", None):
            await auto_resolve_staff_id(client=app_ctx.client, username=tg_handle)
    except Exception as exc:
        logger.debug("[CHECKIN] Proactive staff id resolve notice: %s", exc)

    text = build_checkin_message(seller_name, tg_handle, now, calls_info)

    # Persistent deduplication check
    can_send, reason = can_dispatch_checkin(now, text, force=force)
    if not can_send:
        logger.info("[CHECKIN] Skipping checkin dispatch: reason=%s", reason)
        return False

    try:
        if topic_id:
            await bot_runtime.send_message(
                chat_id, text, parse_mode="HTML", message_thread_id=topic_id
            )
        else:
            await bot_runtime.send_message(chat_id, text, parse_mode="HTML")

        # Persist dispatch state
        hour_key = now.strftime("%Y-%m-%d-%H")
        text_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        save_checkin_dispatch(hour_key, int(now.timestamp()), text_hash)

        logger.info("[CHECKIN] Dispatched hourly check-in for %s to chat=%s topic=%s", tg_handle, chat_id, topic_id)
        return True
    except Exception as exc:
        logger.error("[CHECKIN] Failed to dispatch check-in: %s", exc)
        return False


async def remote_staff_checkin_loop(bot_runtime: Any) -> None:
    """Loop running every hour at :00 during business hours (10:00 - 19:00)."""
    await asyncio.sleep(5)
    logger.info("[CHECKIN] remote_staff_checkin_loop started (waiting for :00 mark).")

    while True:
        try:
            now = get_local_now()
            if is_work_hour(now) and now.minute == 0:
                await send_remote_checkin(bot_runtime, now_fn=get_local_now)
        except Exception:
            logger.exception("[CHECKIN] loop iteration error")
        await asyncio.sleep(30)
