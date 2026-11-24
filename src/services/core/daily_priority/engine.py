"""Kun tartibi: ertalab taklif, eslatma, kunduzgi soʻrov, kechki xulosa, javoblar.

Holat fayli xodim javoblari bilan birga yoziladi. Shuning uchun hech bir funksiya
faylni `await`dan oldin oʻqib, keyin eski nusxasini saqlamaydi: har oʻzgarish
`state.update_entry` orqali eng soʻnggi faylga qoʻllanadi.
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

from src.services.core.daily_priority import composer, state as st
from src.services.core.daily_priority.gatherer import gather_tasks
from src.services.core.daily_priority.team import find_member, get_team

logger = logging.getLogger("DailyPriority")

SUMMARY_KEY = "_summary"


def is_enabled() -> bool:
    """`DAILY_PRIORITY_ENABLED=0` jadvalni ham, javob handlerini ham oʻchiradi."""
    return os.getenv("DAILY_PRIORITY_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def _day(now) -> str:
    return now.strftime("%Y-%m-%d")


def _entry(day: str, key: str) -> Optional[dict]:
    return st.get_entry(st.load(), day, key)


async def run_morning(bot: Any, now, *, fetch=None, generate=None) -> int:
    """Har bir aʼzoga bugungi asosiy pul ishini taklif qiladi. Kuniga bir marta."""
    team = get_team()
    day = _day(now)
    try:
        tasks_by_member = await gather_tasks(team, fetch=fetch, now_ts=now.timestamp())
    except Exception:
        logger.error("[DAILY] Ishlarni yigʻib boʻlmadi, ochiq savol bilan davom etamiz.", exc_info=True)
        tasks_by_member = {m["key"]: [] for m in team}

    sent = 0
    for member in team:
        key = member["key"]
        if _entry(day, key):
            continue
        tasks = tasks_by_member.get(key) or []
        yesterday = st.last_entry_before(st.load(), day, key)
        text = await composer.compose_morning(member, tasks, yesterday, generate=generate)
        try:
            await bot.send_message(int(member["user_id"]), text)
        except Exception as exc:
            logger.error("[DAILY] %s ga ertalabki xabar ketmadi: %s", key, exc)
            continue
        top = tasks[0] if tasks else None
        proposal = {
            "task": composer.task_action(top, member.get("role", "sales")) if top else "",
            "lead_id": top.get("lead_id") if top else None,
            "status": st.STATUS_PROPOSED,
            "proposed_at": now.isoformat(),
            "message": text,
        }
        # Javob xabar yetib borgunicha kelgan boʻlsa — uni saqlab qolamiz.
        st.update_entry(day, key, lambda cur: {**proposal, **cur})
        sent += 1
    logger.info("[DAILY] Ertalabki takliflar: %s ta", sent)
    return sent


async def _send_once(bot, now, member, flag: str, allowed_status, make_text) -> bool:
    day, key = _day(now), member["key"]
    entry = _entry(day, key)
    if not entry or entry.get(flag) or entry.get("status") not in allowed_status:
        return False
    text = await make_text(entry)
    # Yozish paytida holat oʻzgargan boʻlishi mumkin (xodim javob berdi) — qayta tekshiramiz.
    entry = _entry(day, key)
    if not entry or entry.get(flag) or entry.get("status") not in allowed_status:
        return False
    try:
        await bot.send_message(int(member["user_id"]), text)
    except Exception as exc:
        logger.error("[DAILY] %s ga %s ketmadi: %s", key, flag, exc)
        return False
    st.update_entry(day, key, lambda cur: {**cur, flag: now.isoformat()})
    return True


async def run_nudge(bot: Any, now, *, generate=None) -> int:
    """Javob bermaganlarga bir marta muloyim eslatma."""
    sent = 0
    for member in get_team():
        sent += await _send_once(
            bot, now, member, "nudge_sent", (st.STATUS_PROPOSED,),
            lambda e, m=member: composer.compose_nudge(m, e.get("task") or "bugungi asosiy ish", generate=generate),
        )
    return sent


async def run_followup(bot: Any, now, *, generate=None) -> int:
    """Kelishilgan, lekin hali bajarilmagan ish boʻyicha kunduzi bir marta soʻraydi."""
    sent = 0
    for member in get_team():
        sent += await _send_once(
            bot, now, member, "followup_sent", (st.STATUS_ACCEPTED, st.STATUS_CHANGED),
            lambda e, m=member: composer.compose_followup(m, e.get("task") or "bugungi ish", generate=generate),
        )
    return sent


async def run_owner_summary(bot: Any, now, owner_id: Optional[int]) -> bool:
    if not owner_id:
        logger.warning("[DAILY] OWNER_ID yoʻq, xulosa yuborilmadi.")
        return False
    day = _day(now)
    data = st.load()
    entries = {k: v for k, v in (data.get(day) or {}).items() if not k.startswith("_")}
    if not entries or st.get_entry(data, day, SUMMARY_KEY):
        return False
    text = composer.compose_owner_summary(day, get_team(), entries)
    try:
        await bot.send_message(int(owner_id), text)
    except Exception as exc:
        logger.error("[DAILY] Egasiga xulosa ketmadi: %s", exc)
        return False
    st.update_entry(day, SUMMARY_KEY, lambda cur: {"sent_at": now.isoformat()})
    return True


def is_awaiting_reply(entry: Optional[dict]) -> bool:
    """Oishaʼning kunlik savoli hali javobsizmi (ertalabki yoki kunduzgi soʻrov).

    Javob olingandan keyingi DMʼlar oddiy savol — ularni team-DM handleri oladi.
    """
    if not entry:
        return False
    if not entry.get("reply"):
        return True
    return bool(entry.get("followup_sent")) and not entry.get("followup_reply")


def _apply_reply(entry: dict, text: str, status: str, now) -> dict:
    entry = dict(entry)
    if entry.get("followup_sent") and entry.get("status") in (st.STATUS_ACCEPTED, st.STATUS_CHANGED):
        # Kunduzgi soʻrovga javob: faqat aniq "bajarildi" holatni oʻzgartiradi.
        entry["followup_reply"] = text
        if status == st.STATUS_DONE:
            entry["status"] = st.STATUS_DONE
        return entry
    entry["reply"] = text
    entry["reply_at"] = now.isoformat()
    if status == st.STATUS_CHANGED:
        entry["task"] = text.strip()[:200]
    entry["status"] = status
    return entry


async def handle_reply(user_id: int, text: str, now, *, generate=None) -> Optional[str]:
    """Aʼzoning shaxsiy javobini qayd qiladi va javob matnini qaytaradi.

    Bugun unga savol yuborilmagan boʻlsa — None (boshqa handlerlarga oʻtadi).
    """
    member = find_member(user_id)
    if not member:
        return None
    day = _day(now)
    if not _entry(day, member["key"]):
        return None
    status = composer.classify_reply(text)
    updated = st.update_entry(day, member["key"], lambda cur: _apply_reply(cur, text, status, now))
    task = (updated or {}).get("task") or ""
    return await composer.compose_reply(member, status, text, task, generate=generate)


def is_team_member(user_id: Optional[int]) -> bool:
    return find_member(user_id) is not None


__all__: List[str] = [
    "run_morning", "run_nudge", "run_followup", "run_owner_summary", "handle_reply",
    "is_team_member", "is_enabled",
]
