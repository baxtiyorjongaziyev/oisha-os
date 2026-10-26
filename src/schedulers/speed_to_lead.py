"""Lidga birinchi javob tezligi nazorati (speed-to-lead).

Sotuv voronkasidagi yangi lid uchun ish soatlarida sanaladigan taymer:
  * 15 daqiqa ichida sotuvchi harakati (chiquvchi qo'ng'iroq/xabar, status) bo'lmasa —
    Target Leads guruhiga mas'ul sotuvchini teg qilib eslatma;
  * 45 daqiqa ichida ham bo'lmasa — Owner'ga shaxsiy xabar;
  * javob topilsa — guruhga "✅ N daqiqada javob berildi" (faqat eslatma yuborilgan lidlar uchun).

Vaqt `seller_metrics.business_minutes` bilan (Du–Sha, 09:00–19:00, Toshkent) sanaladi —
kechasi kelgan lid ertalabgacha "kutmaydi". Xabarlar faqat ish vaqtida yuboriladi.

Holat diskda (data/speed_to_lead_state.json): qayta deploy'da eslatmalar takrorlanmaydi.
Birinchi ishga tushishda `since` belgilanadi — undan oldingi lidlar (backlog) ko'rilmaydi.
`SPEED_TO_LEAD_ENABLED=0` bilan o'chiriladi.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import html
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.services.core.crm.amocrm_pipeline_config import SALES_PIPELINE_ID
from src.services.core.marketing.seller_metrics import TZ, business_minutes, first_touch_ts

logger = logging.getLogger("SpeedToLead")

REMIND_AFTER_MIN = int(os.getenv("SPEED_TO_LEAD_REMIND_MIN", "15"))
ESCALATE_AFTER_MIN = int(os.getenv("SPEED_TO_LEAD_ESCALATE_MIN", "45"))
CHECK_INTERVAL_SECONDS = int(os.getenv("SPEED_TO_LEAD_INTERVAL_SEC", "120"))
MAX_LEAD_AGE_SECONDS = 4 * 86400  # dam olish kunidan keyin ham kuzatish uchun
CLOSED_STATUSES = (142, 143)
BOT_RESPONSIBLE_USER_ID = 13021974

STAGE_NONE, STAGE_REMINDED, STAGE_ESCALATED, STAGE_DONE = 0, 1, 2, 3

_STATE_FILE = Path(__file__).resolve().parents[2] / "data" / "speed_to_lead_state.json"
_LOCK = threading.RLock()


# ── Sof mantiq (testlanadi) ─────────────────────────────────────────────────

def elapsed_business_min(created_ts: int, now: float) -> float:
    return business_minutes(
        dt.datetime.fromtimestamp(int(created_ts), TZ), dt.datetime.fromtimestamp(now, TZ),
    )


def is_work_time(now: float) -> bool:
    return elapsed_business_min(int(now) - 60, now) > 0


def decide(stage: int, created_ts: int, touch_ts: Optional[int], now: float) -> Optional[str]:
    """Keyingi amal: 'answered' | 'remind' | 'escalate' | None."""
    if stage >= STAGE_DONE:
        return None
    if touch_ts:
        return "answered"
    minutes = elapsed_business_min(created_ts, now)
    if stage < STAGE_ESCALATED and minutes >= ESCALATE_AFTER_MIN:
        return "escalate"
    if stage < STAGE_REMINDED and minutes >= REMIND_AFTER_MIN:
        return "remind"
    return None


def parse_seller_map(raw: str) -> Dict[int, int]:
    """'amo_id:tg_id,amo_id:tg_id' → {amo_id: tg_id}. Noto'g'ri juftliklar tashlab ketiladi."""
    result: Dict[int, int] = {}
    for item in (raw or "").split(","):
        left, _, right = item.partition(":")
        try:
            result[int(left.strip())] = int(right.strip())
        except ValueError:
            continue
    return result


def seller_mention(user_id: Optional[int], name: str, seller_map: Dict[int, int]) -> str:
    if not user_id or user_id == BOT_RESPONSIBLE_USER_ID:
        return "<b>mas'ul belgilanmagan</b>"
    safe = html.escape(name or f"ID {user_id}")
    tg_id = seller_map.get(int(user_id))
    return f'<a href="tg://user?id={tg_id}">{safe}</a>' if tg_id else f"<b>{safe}</b>"


def _lead_title(lead: Dict[str, Any]) -> str:
    return html.escape(str(lead.get("name") or f"Lid #{lead.get('id')}"))


def build_text(action: str, lead: Dict[str, Any], mention: str, minutes: float) -> str:
    title, mins = _lead_title(lead), int(minutes)
    if action == "remind":
        return f"⏰ {mention}, lid <b>{mins} daqiqadan</b> beri javobsiz\n📌 {title}"
    if action == "escalate":
        return (f"🚨 <b>Lid {mins} daqiqadan beri javobsiz</b>\n📌 {title}\n"
                f"👤 Mas'ul: {mention}")
    return f"✅ {mention} lidga <b>{mins} daqiqada</b> javob berdi\n📌 {title}"


# ── Holat (disk) ────────────────────────────────────────────────────────────

def load_state() -> Dict[str, Any]:
    with _LOCK:
        try:
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("leads"), dict):
                return data
        except (OSError, ValueError):
            pass
        return {"since": None, "leads": {}}


def save_state(state: Dict[str, Any], now: float) -> None:
    cutoff = now - MAX_LEAD_AGE_SECONDS
    state["leads"] = {k: v for k, v in state["leads"].items() if v.get("created", now) >= cutoff}
    with _LOCK:
        try:
            _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = _STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(state), encoding="utf-8")
            tmp.replace(_STATE_FILE)
        except OSError as exc:
            logger.warning("[SPEED-TO-LEAD] holat saqlanmadi: %s", exc)


def candidate_leads(leads: List[Dict[str, Any]], state: Dict[str, Any], now: float) -> List[Dict[str, Any]]:
    since = state.get("since") or now
    result = []
    for lead in leads:
        created = int(lead.get("created_at") or 0)
        if not created or created < since or now - created > MAX_LEAD_AGE_SECONDS:
            continue
        if lead.get("status_id") in CLOSED_STATUSES:
            continue
        if state["leads"].get(str(lead["id"]), {}).get("stage", 0) >= STAGE_DONE:
            continue
        result.append(lead)
    return result


# ── I/O ─────────────────────────────────────────────────────────────────────

def _owner_chat_id() -> Optional[int]:
    from src.settings import settings
    return int(getattr(settings, "OWNER_ID", 0) or 0) or None


async def _send(action: str, text: str, lead_id: int) -> bool:
    from src.schedulers.leadgen_status_reporter import _send_tg_message
    from src.services.core.instagram.leadgen_router import _notify_telegram

    markup = {"inline_keyboard": [[{"text": "🧾 AmoCRM bitimi",
                                    "url": f"https://jonbranding.amocrm.ru/leads/detail/{lead_id}"}]]}
    if action == "escalate":
        owner = _owner_chat_id()
        return bool(owner) and await asyncio.to_thread(_send_tg_message, text, owner, None, markup)
    return await asyncio.to_thread(_notify_telegram, text, markup)


async def _process_lead(amocrm: Any, lead: Dict[str, Any], entry: Dict[str, Any],
                        seller_map: Dict[int, int], names: Dict[int, str], now: float) -> None:
    from src.services.core.marketing.attribution_sync import _fetch_lead_events

    lead_id, created = int(lead["id"]), int(lead["created_at"])
    stage = int(entry.get("stage", STAGE_NONE))
    if stage == STAGE_NONE and elapsed_business_min(created, now) < REMIND_AFTER_MIN:
        return  # hali erta — AmoCRM events so'rovini tejaymiz
    touch = first_touch_ts(created, await _fetch_lead_events(amocrm, lead_id))
    action = decide(stage, created, touch, now)
    if action is None:
        return
    if action == "answered" and stage == STAGE_NONE:
        entry["stage"] = STAGE_DONE  # eslatmasiz o'z vaqtida javob — shovqin qilmaymiz
        return
    uid = lead.get("responsible_user_id")
    if uid and uid not in names:
        names[uid] = await asyncio.to_thread(amocrm.get_user_name, uid)
    minutes = elapsed_business_min(created, touch or now)
    text = build_text(action, lead, seller_mention(uid, names.get(uid, ""), seller_map), minutes)
    if await _send(action, text, lead_id):
        entry["stage"] = {"remind": STAGE_REMINDED, "escalate": STAGE_ESCALATED}.get(action, STAGE_DONE)


async def check_once(amocrm: Any, now: Optional[float] = None) -> int:
    now = now or time.time()
    state = load_state()
    if not state.get("since"):
        state["since"] = now
        save_state(state, now)
        return 0
    if not is_work_time(now):
        return 0
    leads = await amocrm.get_leads(limit=100, **{"filter[pipeline_id][]": SALES_PIPELINE_ID,
                                                 "order[created_at]": "desc"})
    seller_map = parse_seller_map(os.getenv("SPEED_TO_LEAD_SELLER_MAP", ""))
    names: Dict[int, str] = {}
    handled = 0
    for lead in candidate_leads(leads or [], state, now):
        entry = state["leads"].setdefault(str(lead["id"]), {"created": int(lead["created_at"])})
        before = entry.get("stage", STAGE_NONE)
        try:
            await _process_lead(amocrm, lead, entry, seller_map, names, now)
        except Exception as exc:
            logger.warning("[SPEED-TO-LEAD] lid %s: %s", lead.get("id"), type(exc).__name__)
        handled += int(entry.get("stage", STAGE_NONE) != before)
    save_state(state, now)
    return handled


async def speed_to_lead_loop() -> None:
    if os.getenv("SPEED_TO_LEAD_ENABLED", "1").strip() in ("0", "false", "no"):
        logger.info("[SPEED-TO-LEAD] o'chirilgan (SPEED_TO_LEAD_ENABLED=0)")
        return
    logger.info("[SPEED-TO-LEAD] ishga tushdi: %d/%d daqiqa", REMIND_AFTER_MIN, ESCALATE_AFTER_MIN)
    await asyncio.sleep(45)
    from src.services.core.instagram.leadgen_router import _amocrm_instance

    while True:
        try:
            changed = await check_once(_amocrm_instance())
            if changed:
                logger.info("[SPEED-TO-LEAD] %d ta lid holati o'zgardi", changed)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("[SPEED-TO-LEAD] loop xatosi: %s", exc, exc_info=True)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
