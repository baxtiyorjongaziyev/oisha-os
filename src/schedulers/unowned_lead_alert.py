"""Egasiz inhouse lead eslatmasi.

Meta Lead Ads orqali inhouse'ga (Sotuv voronkasi, "taqsimot:inhouse" tegi) tushgan lead
30 daqiqadan beri hali bot nomida turgan bo'lsa va menejer o'zini teg qo'ymagan bo'lsa,
Target Leads guruhiga bir marta eslatma yuboriladi.

Xotira diskdagi faylda (data/alerted_unowned_leads.json) saqlanadi, shuning uchun qayta deploy
bo'lganda allaqachon ogohlantirilgan leadlar qayta yuborilmaydi.
UTC lead'lariga tegilmaydi. Quiet-hours (23:00–07:00) vaqtida jim turadi.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from src.services.core.crm.amocrm_pipeline_config import SALES_PIPELINE_ID
from src.time_utils import is_quiet_hours

logger = logging.getLogger("UnownedLeadAlert")

BOT_RESPONSIBLE_USER_ID = 13021974  # @jonbranding_assistant
INHOUSE_TAG = "taqsimot:inhouse"
UNOWNED_AFTER_SECONDS = 30 * 60
MAX_LEAD_AGE_SECONDS = 24 * 3600  # eski backlog uchun spam qilmaslik
CHECK_INTERVAL_SECONDS = 5 * 60
MAX_STORE_AGE_SECONDS = 14 * 86400  # 14 kundan eski yozuvlar diskdan tozalanadi

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEDUP_FILE = _PROJECT_ROOT / "data" / "alerted_unowned_leads.json"
_LOCK = threading.RLock()
_alerted: Set[int] = set()
_INITIALIZED: bool = False

DEFAULT_MANAGER_NAMES = {
    "shahnoza",
    "rayxon",
    "rayhona",
    "farangiz",
    "aziz",
    "ahrorbek",
    "dilbar",
    "hasanboy",
    "baxtiyorjon",
}

MANAGER_TAG_PREFIXES = (
    "menejer:",
    "manager:",
    "mas'ul:",
    "masul:",
    "sotuvchi:",
    "rep:",
    "owner:",
)


def get_known_manager_names() -> Set[str]:
    """Return lowercase known manager names from config and defaults."""
    names = set(DEFAULT_MANAGER_NAMES)
    env_reps = os.getenv("MOIZVONKI_REP_NAMES", "")
    if env_reps:
        for item in env_reps.split(","):
            if ":" in item:
                val = item.split(":", 1)[1].strip().lower()
                if val:
                    names.add(val)
    return names


def is_claimed_by_manager(
    tags: Iterable[str],
    known_managers: Optional[Set[str]] = None,
) -> bool:
    """Return True if lead has any tag indicating a manager took it."""
    managers = known_managers if known_managers is not None else get_known_manager_names()
    for tag in tags:
        t_clean = str(tag).strip()
        t_lower = t_clean.lower()
        if not t_lower:
            continue
        if t_lower in managers:
            return True
        for prefix in MANAGER_TAG_PREFIXES:
            if t_lower.startswith(prefix):
                return True
    return False


def _load_persisted_alerts() -> Dict[str, float]:
    """Load alerted lead IDs with timestamps from disk."""
    if not _DEDUP_FILE.exists():
        return {}
    try:
        with open(_DEDUP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {str(k): float(v) for k, v in data.items()}
            elif isinstance(data, list):
                return {str(k): time.time() for k in data}
    except Exception as exc:
        logger.warning("[UNOWNED LEAD] Dedup faylini o'qishda xatolik: %s", exc)
    return {}


def _save_persisted_alerts(store: Dict[str, float]) -> None:
    """Atomically save alerted lead IDs to disk."""
    try:
        _DEDUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = _DEDUP_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2)
        temp_file.replace(_DEDUP_FILE)
    except Exception as exc:
        logger.warning("[UNOWNED LEAD] Dedup fayliga yozishda xatolik: %s", exc)


def _ensure_initialized() -> None:
    """Load disk cache into _alerted set on first call."""
    global _INITIALIZED
    with _LOCK:
        if not _INITIALIZED:
            store = _load_persisted_alerts()
            for k in store:
                try:
                    _alerted.add(int(k))
                except ValueError:
                    pass
            _INITIALIZED = True


def is_lead_alerted(lead_id: int | str) -> bool:
    """Check if lead ID has already been alerted (RAM or disk)."""
    lid = int(lead_id)
    with _LOCK:
        _ensure_initialized()
        return lid in _alerted


def mark_lead_alerted(lead_id: int | str, alert_time: Optional[float] = None) -> None:
    """Mark lead as alerted in RAM and persist to disk atomically."""
    lid = int(lead_id)
    now_ts = alert_time if alert_time is not None else time.time()
    with _LOCK:
        _ensure_initialized()
        _alerted.add(lid)
        store = _load_persisted_alerts()
        cutoff = now_ts - MAX_STORE_AGE_SECONDS
        pruned = {k: v for k, v in store.items() if v >= cutoff}
        pruned[str(lid)] = now_ts
        _save_persisted_alerts(pruned)


def find_unowned_inhouse_leads(leads: List[Dict[str, Any]], now: float) -> List[Dict[str, Any]]:
    """Egasi hali bot bo'lgan, menejer tegi qo'yilmagan, 30 daqiqadan oshgan ochiq lead'lar."""
    result = []
    known_managers = get_known_manager_names()
    for lead in leads:
        if lead.get("status_id") in (142, 143):
            continue
        if lead.get("responsible_user_id") != BOT_RESPONSIBLE_USER_ID:
            continue
        tags = {str(t.get("name") or "").strip() for t in (lead.get("_embedded") or {}).get("tags") or []}
        if INHOUSE_TAG not in tags:
            continue
        if is_claimed_by_manager(tags, known_managers):
            continue
        age = now - int(lead.get("created_at") or now)
        lead_id = int(lead["id"])
        if UNOWNED_AFTER_SECONDS <= age <= MAX_LEAD_AGE_SECONDS and not is_lead_alerted(lead_id):
            result.append(lead)
    return result


def format_duration(minutes: int) -> str:
    """1392 -> '23 soat 12 daqiqa'; 1500 -> '1 kun 1 soat'."""
    if minutes < 60:
        return f"{minutes} daqiqa"
    days, rem = divmod(minutes, 1440)
    hours, mins = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} kun")
    if hours:
        parts.append(f"{hours} soat")
    if mins and not days:
        parts.append(f"{mins} daqiqa")
    return " ".join(parts)


def build_alert_text(lead: Dict[str, Any], now: float) -> str:
    minutes = int((now - int(lead.get("created_at") or now)) // 60)
    name = html.escape(str(lead.get("name") or "Nomsiz lead"))
    return (
        "⚠️ <b>Lead egasiz turibdi</b>\n\n"
        f"📌 {name}\n"
        f"⏱ {format_duration(minutes)}dan beri hech kim olmadi\n\n"
        "Lead'ni olgan menejer AmoCRM'da <b>Mas'ul</b>ga o'z ismini qo'ysin."
    )


async def check_unowned_leads_once(amocrm: Any) -> int:
    if is_quiet_hours():
        return 0
    leads = await amocrm.get_leads(limit=250, **{"filter[pipeline_id][]": SALES_PIPELINE_ID, "order[created_at]": "desc"})
    now = time.time()
    from src.services.core.instagram.leadgen_router import _notify_telegram

    sent = 0
    for lead in find_unowned_inhouse_leads(leads, now):
        lead_id = int(lead["id"])
        markup = {"inline_keyboard": [[{"text": "🧾 AmoCRM bitimi", "url": f"https://jonbranding.amocrm.ru/leads/detail/{lead_id}"}]]}
        if await asyncio.to_thread(_notify_telegram, build_alert_text(lead, now), markup):
            mark_lead_alerted(lead_id, now)
            sent += 1
    return sent


async def unowned_lead_alert_loop() -> None:
    logger.info("[UNOWNED LEAD] inhouse egasiz lead nazorati ishga tushdi")
    await asyncio.sleep(30)
    from src.services.core.instagram.leadgen_router import _amocrm_instance

    while True:
        try:
            sent = await check_unowned_leads_once(_amocrm_instance())
            if sent:
                logger.info("[UNOWNED LEAD] %d ta eslatma yuborildi", sent)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("[UNOWNED LEAD] loop error: %s", exc, exc_info=True)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
