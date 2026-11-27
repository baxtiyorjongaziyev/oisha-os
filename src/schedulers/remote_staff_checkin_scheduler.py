"""Remote staff hourly check-in scheduler.

Har bir sotuvchiga (Rayxon, Mumtozmaxal, Shahnoza) Sales guruhidagi (-1003854308552)
o'z leads topic'iga soatlik xabar yozadi: MoiZvonki qo'ng'iroq faktlari va amoCRM'dagi
``AI_CALL_ANALYSIS`` xulosalari asosida konversiyani oshirishga yordam beradi.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
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
# Rayxonaning shaxsiy sotuv-menejer topic'i: check-in umumiy hisobot topic'iga emas, shu yerga boradi.
REP_TOPIC_ID = 2976

DEFAULT_REP_NAME = "Rayxon"
DEFAULT_REP_TG = "@RayxonJonbranding"
DEFAULT_REP_EMAILS = ["rayxona@jonbranding.uz"]

MIN_CHECKIN_INTERVAL_SECONDS = 45 * 60  # 45 daqiqa minimal oraliq
STATE_FILE = "data/checkin_state.json"
CONTEXT_FILE = "data/checkin_context.json"
SUMMARY_MAX_CHARS = 220

# Har bir sotuvchining o'z leads topic'i (owner 2026-10-28). Rayxon kalitlari eski fayl/kv nomlarida
# qoladi; boshqalar o'z nomlarini oladi. REMOTE_CHECKIN_REPS (JSON ro'yxat) bilan almashtirsa bo'ladi.
DEFAULT_REPS: List[Dict[str, Any]] = [
    {"key": "rayxon", "name": DEFAULT_REP_NAME, "tg": DEFAULT_REP_TG,
     "emails": DEFAULT_REP_EMAILS, "topic": REP_TOPIC_ID},
    {"key": "mumtozmaxal", "name": "Mumtozmaxal", "tg": "",
     "emails": ["mumtozmaxal@jonbranding.uz"], "topic": 120},
    {"key": "shahnoza", "name": "Shahnoza", "tg": "",
     "emails": ["shahnoza@jonbranding.uz"], "topic": 122},
]


def get_reps() -> List[Dict[str, Any]]:
    raw = os.getenv("REMOTE_CHECKIN_REPS", "").strip()
    if raw:
        try:
            reps = json.loads(raw)
            if isinstance(reps, list) and reps:
                return reps
        except ValueError:
            logger.warning("[CHECKIN] REMOTE_CHECKIN_REPS JSON emas, standart ro'yxat ishlatiladi.")
    return DEFAULT_REPS


def rep_storage(rep_key: str) -> tuple[str, str, str]:
    """(state_file, kv_prefix, context_file) — Rayxon eski nomlarda qoladi."""
    if not rep_key or rep_key == "rayxon":
        return STATE_FILE, "CHECKIN", CONTEXT_FILE
    return (
        f"data/checkin_state_{rep_key}.json",
        f"CHECKIN_{rep_key.upper()}",
        f"data/checkin_context_{rep_key}.json",
    )


def get_checkin_state(
    db_path: str = "data/bot.db", state_file: str = STATE_FILE, kv_prefix: str = "CHECKIN"
) -> dict:
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
            "SELECT key, value FROM kv_settings WHERE key IN (?, ?, ?)",
            (f"{kv_prefix}_LAST_HOUR_KEY", f"{kv_prefix}_LAST_SENT_TS", f"{kv_prefix}_LAST_TEXT_HASH"),
        )
        for k, v in c.fetchall():
            if k == f"{kv_prefix}_LAST_HOUR_KEY":
                state["last_hour_key"] = str(v or "")
            elif k == f"{kv_prefix}_LAST_SENT_TS":
                try:
                    state["last_sent_ts"] = int(float(v or 0))
                except (ValueError, TypeError):
                    pass
            elif k == f"{kv_prefix}_LAST_TEXT_HASH":
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
    kv_prefix: str = "CHECKIN",
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
            VALUES (?, ?, ?), (?, ?, ?), (?, ?, ?)
            """,
            (
                f"{kv_prefix}_LAST_HOUR_KEY", hour_key, now_iso,
                f"{kv_prefix}_LAST_SENT_TS", str(sent_ts), now_iso,
                f"{kv_prefix}_LAST_TEXT_HASH", text_hash, now_iso,
            ),
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
    kv_prefix: str = "CHECKIN",
) -> tuple[bool, str]:
    """Check deduplication rules to guarantee: bitta narsani ketma-ket ikki marta yubormasin."""
    if force:
        return True, "forced"

    hour_key = now.strftime("%Y-%m-%d-%H")
    text_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    state = get_checkin_state(db_path=db_path, state_file=state_file, kv_prefix=kv_prefix)

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
        topic_id = REP_TOPIC_ID

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


def format_handle(tg_handle: str) -> str:
    if not (tg_handle or "").strip("@ "):
        return ""
    try:
        from src.services.core.sales_staff_copilot import get_known_staff_user_id
        known_id = get_known_staff_user_id(tg_handle)
        if known_id:
            return f'<a href="tg://user?id={known_id}">@{tg_handle.lstrip("@")}</a>'
    except Exception:
        pass
    return tg_handle if tg_handle.startswith("@") else f"@{tg_handle}"


def addressee(seller_name: str, handle: str) -> str:
    return f"{seller_name} ({handle})" if handle else seller_name


def build_checkin_message(
    seller_name: str,
    tg_handle: str,
    now: datetime,
    activity: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a natural, human ROP message based on real MoiZvonki telephony data."""
    handle = format_handle(tg_handle)

    if not activity or activity.get("total", 0) == 0:
        return (
            f"Assalomu alaykum, {addressee(seller_name, handle)}! 😊\n\n"
            f"Oxirgi soatda telefoniyada qo'ng'iroq ko'rinmadi — yozishmalar bilan bandmisiz? "
            f"Qaysi mijoz ustida ishlayapsiz? Kimga qo'ng'iroq qilishni yoki nima deyishni "
            f"birga o'ylab ko'raylikmi?"
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
            f"Assalomu alaykum, {addressee(seller_name, handle)}! 👏\n\n"
            f"Zo'r soat bo'libdi: {total} ta raqam terib, {answered} ta mijoz bilan yaxshi gaplashibsiz "
            f"({clients_text}; jami {format_duration(total_talk)}).\n\n"
            f"Nimalarga kelishdingiz? Shu xabarga reply qilib yozing — keyingi qadamni "
            f"qanday qilsak bitim yopiladi, birga o'ylaymiz."
        )

    if answered > 0 and solid == 0:
        msg = (
            f"Assalomu alaykum, {addressee(seller_name, handle)}! 😊\n\n"
            f"Oxirgi soatda {total} ta raqam terdingiz, {answered} tasi ko'tardi"
        )
        if clients_text:
            msg += f" ({clients_text})"
        msg += (
            f". Suhbatlar qisqa bo'libdi — band edimi yoki keyinroq gaplashamiz deyishdimi?\n\n"
            f"Shu xabarga reply qilib yozing, nima bo'lganini — keyingi qo'ng'iroqda "
            f"gapni qanday boshlash bo'yicha tayyor gap bilan yordam beraman!"
        )
        return msg

    return (
        f"Assalomu alaykum, {addressee(seller_name, handle)}! 😊\n\n"
        f"Oxirgi soatda {total} ta raqam terdingiz, hozircha hech kim ko'tarmadi — bu normal holat, "
        f"ruhingiz tushmasin!\n\n"
        f"Qayta terishda ko'tarish ehtimoli ko'proq bo'ladigan vaqt va birinchi gap bo'yicha "
        f"maslahat kerak bo'lsa, shu xabarga reply qilib yozing."
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


def _analysis_summary(note_text: str) -> str:
    """``[AI_CALL_ANALYSIS] ...`` qaydidan sarlavhadan keyingi birinchi mazmunli qator."""
    lines = [ln.strip() for ln in str(note_text or "").splitlines()]
    for ln in lines[1:]:
        if ln:
            return ln[:SUMMARY_MAX_CHARS]
    return ""


async def fetch_call_summaries(
    answered_clients: List[Dict[str, Any]], amocrm: Any = None, max_items: int = 3
) -> List[str]:
    """Javob berilgan qo'ng'iroqlar bo'yicha amoCRM'dagi Oisha AI tahlil xulosalari (raqamsiz)."""
    if amocrm is None:
        try:
            from src.context import app_ctx

            amocrm = getattr(app_ctx, "amocrm", None)
        except Exception:
            amocrm = None
    if amocrm is None or not answered_clients:
        return []

    from src.services.call_analytics.helpers import ANALYSIS_MARKER

    summaries: List[str] = []
    seen: set[str] = set()
    for client in sorted(answered_clients, key=lambda c: -int(c.get("duration") or 0)):
        number = "".join(ch for ch in str(client.get("number") or "") if ch.isdigit())
        if not number or number in seen:
            continue
        seen.add(number)
        try:
            leads = await amocrm.search_leads(number, limit=1)
            if not leads:
                continue
            notes = await amocrm.get_lead_notes(int(leads[0]["id"]))
        except Exception as exc:
            logger.debug("[CHECKIN] amoCRM tahlil o'qilmadi: %s", exc)
            continue
        texts = [
            str((n.get("params") or {}).get("text") or "")
            for n in notes
            if ANALYSIS_MARKER in str((n.get("params") or {}).get("text") or "")
        ]
        summary = _analysis_summary(texts[0]) if texts else ""
        if summary:
            summaries.append(summary)
        if len(summaries) >= max_items:
            break
    return summaries


async def send_remote_checkin(
    bot_runtime: Any,
    *,
    now_fn=get_local_now,
    seller_name: str = DEFAULT_REP_NAME,
    tg_handle: str = DEFAULT_REP_TG,
    rep_emails: Optional[List[str]] = None,
    rep_key: str = "rayxon",
    topic_id: Optional[int] = None,
    force: bool = False,
) -> bool:
    if not is_enabled() and not force:
        return False

    now = now_fn()
    if not is_work_hour(now) and not force:
        logger.info("[CHECKIN] Outside work hours (%02d:%02d), skipping.", now.hour, now.minute)
        return False

    chat_id, default_topic = get_target_destination()
    topic_id = topic_id if topic_id is not None else default_topic
    if not chat_id or bot_runtime is None:
        logger.warning("[CHECKIN] Missing destination chat or bot_runtime.")
        return False

    state_file, kv_prefix, context_file = rep_storage(rep_key)
    emails = rep_emails or DEFAULT_REP_EMAILS
    end_ts = int(now.timestamp())
    start_ts = end_ts - 3600
    calls_info = await asyncio.to_thread(fetch_recent_calls_for_rep, emails, start_ts, end_ts)
    if calls_info and calls_info.get("answered_clients"):
        calls_info["summaries"] = await fetch_call_summaries(calls_info["answered_clients"])

    if tg_handle:
        try:
            from src.services.core.sales_staff_copilot import auto_resolve_staff_id
            from src.context import app_ctx
            if getattr(app_ctx, "client", None):
                await auto_resolve_staff_id(client=app_ctx.client, username=tg_handle)
        except Exception as exc:
            logger.debug("[CHECKIN] Proactive staff id resolve notice: %s", exc)

    text = build_checkin_message(seller_name, tg_handle, now, calls_info)
    ai_text = None
    try:
        from src.services.core.checkin_composer import compose_checkin, load_context

        ai_text = await compose_checkin(
            seller_name, now, calls_info, context=load_context(context_file)
        )
    except Exception as exc:
        logger.debug("[CHECKIN] AI composer unavailable: %s", exc)
    if ai_text:
        # Ism + link bilan murojaat (bildirishnoma borishi uchun), qolgani AI matni.
        text = f"{addressee(seller_name, format_handle(tg_handle))}, {html.escape(ai_text)}"

    # Persistent deduplication check
    can_send, reason = can_dispatch_checkin(
        now, text, force=force, state_file=state_file, kv_prefix=kv_prefix
    )
    if not can_send:
        logger.info("[CHECKIN] Skipping checkin dispatch for %s: reason=%s", rep_key, reason)
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
        save_checkin_dispatch(
            hour_key, int(now.timestamp()), text_hash, state_file=state_file, kv_prefix=kv_prefix
        )
        try:
            from src.services.core.checkin_composer import save_context

            save_context(
                {"date": now.strftime("%Y-%m-%d"), "last_checkin": text}, path=context_file
            )
        except Exception as exc:
            logger.debug("[CHECKIN] context save notice: %s", exc)

        logger.info("[CHECKIN] Dispatched hourly check-in for %s to chat=%s topic=%s", seller_name, chat_id, topic_id)
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
                for rep in get_reps():
                    key = str(rep.get("key") or "")
                    try:
                        await send_remote_checkin(
                            bot_runtime,
                            now_fn=get_local_now,
                            seller_name=str(rep.get("name") or key),
                            tg_handle=str(rep.get("tg") or ""),
                            rep_emails=list(rep.get("emails") or []),
                            rep_key=key,
                            # Rayxon uchun REMOTE_CHECKIN_TOPIC_ID override saqlanadi.
                            topic_id=None if key == "rayxon" else rep.get("topic"),
                        )
                    except Exception:
                        logger.exception("[CHECKIN] %s check-in failed", key)
        except Exception:
            logger.exception("[CHECKIN] loop iteration error")
        await asyncio.sleep(30)
