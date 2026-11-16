"""Kun tartibi: ertalab taklif, eslatma, kunduzgi soʻrov, kechki xulosa, javoblar."""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from src.services.core.daily_priority import composer, state as st
from src.services.core.daily_priority.gatherer import gather_tasks
from src.services.core.daily_priority.team import find_member, get_team

logger = logging.getLogger("DailyPriority")


def _day(now) -> str:
    return now.strftime("%Y-%m-%d")


async def run_morning(bot: Any, now, *, fetch=None, generate=None) -> int:
    """Har bir aʼzoga bugungi asosiy pul ishini taklif qiladi. Kuniga bir marta."""
    team = get_team()
    day = _day(now)
    data = st.load()
    try:
        tasks_by_member = await gather_tasks(team, fetch=fetch, now_ts=now.timestamp())
    except Exception:
        logger.error("[DAILY] Ishlarni yigʻib boʻlmadi, ochiq savol bilan davom etamiz.", exc_info=True)
        tasks_by_member = {m["key"]: [] for m in team}

    sent = 0
    for member in team:
        key = member["key"]
        if st.get_entry(data, day, key):
            continue
        tasks = tasks_by_member.get(key) or []
        yesterday = st.last_entry_before(data, day, key)
        text = await composer.compose_morning(member, tasks, yesterday, generate=generate)
        try:
            await bot.send_message(int(member["user_id"]), text)
        except Exception as exc:
            logger.error("[DAILY] %s ga ertalabki xabar ketmadi: %s", key, exc)
            continue
        top = tasks[0] if tasks else None
        st.set_entry(data, day, key, {
            "task": composer.task_action(top, member.get("role", "sales")) if top else "",
            "lead_id": top.get("lead_id") if top else None,
            "status": st.STATUS_PROPOSED,
            "proposed_at": now.isoformat(),
            "message": text,
        })
        st.save(data, day)  # har yuborishdan keyin — qayta ishga tushsa takror ketmaydi
        sent += 1
    logger.info("[DAILY] Ertalabki takliflar: %s ta", sent)
    return sent


async def run_nudge(bot: Any, now, *, generate=None) -> int:
    """Javob bermaganlarga bir marta muloyim eslatma."""
    day = _day(now)
    data = st.load()
    sent = 0
    for member in get_team():
        entry = st.get_entry(data, day, member["key"])
        if not entry or entry.get("status") != st.STATUS_PROPOSED or entry.get("nudge_sent"):
            continue
        text = await composer.compose_nudge(member, entry.get("task") or "bugungi asosiy ish", generate=generate)
        try:
            await bot.send_message(int(member["user_id"]), text)
        except Exception as exc:
            logger.error("[DAILY] %s ga eslatma ketmadi: %s", member["key"], exc)
            continue
        entry["nudge_sent"] = now.isoformat()
        st.save(data, day)
        sent += 1
    return sent


async def run_followup(bot: Any, now, *, generate=None) -> int:
    """Kelishilgan, lekin hali bajarilmagan ish boʻyicha kunduzi bir marta soʻraydi."""
    day = _day(now)
    data = st.load()
    sent = 0
    for member in get_team():
        entry = st.get_entry(data, day, member["key"])
        if not entry or entry.get("followup_sent"):
            continue
        if entry.get("status") not in (st.STATUS_ACCEPTED, st.STATUS_CHANGED):
            continue
        text = await composer.compose_followup(member, entry.get("task") or "bugungi ish", generate=generate)
        try:
            await bot.send_message(int(member["user_id"]), text)
        except Exception as exc:
            logger.error("[DAILY] %s ga kunduzgi soʻrov ketmadi: %s", member["key"], exc)
            continue
        entry["followup_sent"] = now.isoformat()
        st.save(data, day)
        sent += 1
    return sent


async def run_owner_summary(bot: Any, now, owner_id: Optional[int]) -> bool:
    if not owner_id:
        logger.warning("[DAILY] OWNER_ID yoʻq, xulosa yuborilmadi.")
        return False
    day = _day(now)
    data = st.load()
    entries = data.get(day) or {}
    if not entries or entries.get("_summary_sent"):
        return False
    text = composer.compose_owner_summary(day, get_team(), entries)
    try:
        await bot.send_message(int(owner_id), text)
    except Exception as exc:
        logger.error("[DAILY] Egasiga xulosa ketmadi: %s", exc)
        return False
    entries["_summary_sent"] = now.isoformat()
    st.save(data, day)
    return True


async def handle_reply(user_id: int, text: str, now, *, generate=None) -> Optional[str]:
    """Aʼzoning shaxsiy javobini qayd qiladi va javob matnini qaytaradi.

    Bugun unga savol yuborilmagan boʻlsa — None (boshqa handlerlarga oʻtadi).
    """
    member = find_member(user_id)
    if not member:
        return None
    day = _day(now)
    data = st.load()
    entry = st.get_entry(data, day, member["key"])
    if not entry:
        return None

    status = composer.classify_reply(text)
    if entry.get("followup_sent") and entry.get("status") in (st.STATUS_ACCEPTED, st.STATUS_CHANGED):
        # Kunduzgi soʻrovga javob: faqat "bajarildi"ni holatga yozamiz.
        entry["followup_reply"] = text
        if status == st.STATUS_DONE:
            entry["status"] = st.STATUS_DONE
    else:
        entry["reply"] = text
        entry["reply_at"] = now.isoformat()
        if status == st.STATUS_CHANGED:
            entry["task"] = text.strip()[:200]
        entry["status"] = status
    st.save(data, day)
    return await composer.compose_reply(member, status, text, entry.get("task") or "", generate=generate)


def is_team_member(user_id: Optional[int]) -> bool:
    return find_member(user_id) is not None


__all__: List[str] = [
    "run_morning", "run_nudge", "run_followup", "run_owner_summary", "handle_reply", "is_team_member",
]
