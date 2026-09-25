"""
Income seller attribution supervisor (Oisha AI Nazoratchi).

Monitors Airtable 'Tranzaksiyalar' table for incoming revenue records,
identifies which sales manager closed each deal (via linked projects,
AmoCRM deal lookup, phone/client matching, or note text), updates Airtable
records with the identified seller, and alerts the team via Telegram.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set

import requests

from src.settings import settings

logger = logging.getLogger("OishaIncomeSupervisor")

# AmoCRM responsible_user_id -> Airtable 'Jamoa' record ID
AMOCRM_USER_TO_JAMOA: Dict[int, str] = {
    8128012: "reccXjZIGIcRezKgB",   # Baxtiyorjon Gaziyev
    13021974: "rec8fmSHRpZi5Rx9N",  # Shahnoza Abdijabborova
    13838466: "recfj3ExodGmnN2VW",  # Oydin Ermuhammadova
    13841510: "recfj3ExodGmnN2VW",  # Oydin Ermuhammadova
}

# Jamoa record ID -> Display Name & Telegram Handle
JAMOA_SELLER_INFO: Dict[str, Dict[str, str]] = {
    "rec8fmSHRpZi5Rx9N": {"name": "Shahnoza Abdijabborova", "handle": "@Shahnozzy"},
    "reccXjZIGIcRezKgB": {"name": "Baxtiyorjon Gaziyev", "handle": "@Baxtiyorjon_Gaziyev"},
    "recp8ClrBsXi6G0Km": {"name": "Ahrorbek", "handle": "@Ahrorbek"},
    "recfj3ExodGmnN2VW": {"name": "Oydin Ermuhammadova", "handle": "@oydin_jonbranding"},
    "recndwD6R8Wk3CNtY": {"name": "Farangiz Shamsi", "handle": "@Farangiz_Shamsi"},
    "recPi9SROzJNK8SX7": {"name": "Hasanboy Gaziyev", "handle": "@jonbranding_pm"},
}

NAME_TO_JAMOA: Dict[str, str] = {
    "shahnoza": "rec8fmSHRpZi5Rx9N",
    "shaxnoza": "rec8fmSHRpZi5Rx9N",
    "baxtiyorjon": "reccXjZIGIcRezKgB",
    "baxtiyor": "reccXjZIGIcRezKgB",
    "ahrorbek": "recp8ClrBsXi6G0Km",
    "ahror": "recp8ClrBsXi6G0Km",
    "oydin": "recfj3ExodGmnN2VW",
    "farangiz": "recndwD6R8Wk3CNtY",
    "hasanboy": "recPi9SROzJNK8SX7",
}

# Strict boundary: All finance tracking and seller attribution starts from September 2026
SEPTEMBER_START_DATE: str = "2026-09-01"

# Disk-persistent deduplication store for unassigned alerts (prevents spam across restarts)
_ALERT_STORE_PATH = os.path.join("data", "income_supervisor_alerted.json")


def _load_alerted_record_ids() -> Set[str]:
    """Load alerted record IDs from disk to prevent repeated spam."""
    try:
        if os.path.exists(_ALERT_STORE_PATH):
            with open(_ALERT_STORE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
    except Exception as exc:
        logger.warning("[SUPERVISOR] Failed to load alerted records from %s: %s", _ALERT_STORE_PATH, exc)
    return set()


def _save_alerted_record_id(rec_id: str) -> None:
    """Persist alerted record ID to disk immediately."""
    _ALERTED_RECORD_IDS.add(rec_id)
    try:
        os.makedirs(os.path.dirname(_ALERT_STORE_PATH), exist_ok=True)
        with open(_ALERT_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(list(_ALERTED_RECORD_IDS), f, indent=2)
    except Exception as exc:
        logger.warning("[SUPERVISOR] Failed to save alerted record to %s: %s", _ALERT_STORE_PATH, exc)


def _discard_alerted_record_id(rec_id: str) -> None:
    """Remove resolved record ID from alert cache."""
    if rec_id in _ALERTED_RECORD_IDS:
        _ALERTED_RECORD_IDS.discard(rec_id)
        try:
            with open(_ALERT_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(list(_ALERTED_RECORD_IDS), f, indent=2)
        except Exception:
            pass


_ALERTED_RECORD_IDS: Set[str] = _load_alerted_record_ids()


def _secret_text(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "").strip()


def _send_tg_message(text: str, chat_id: int, topic_id: Optional[int] = None) -> bool:
    """Direct Telegram Bot API notification dispatch."""
    bot_token = _secret_text(getattr(settings, "BOT_TOKEN", None)) or os.getenv("BOT_TOKEN", "").strip()
    if not bot_token or not chat_id:
        return False

    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if topic_id is not None:
        payload["message_thread_id"] = topic_id

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as exc:
        logger.warning("[SUPERVISOR] Telegram dispatch failed: %s", exc)
        return False


def _dispatch_supervisor_alert(text: str) -> bool:
    """Send notification to Sales report topic (115) and Finance topic if configured."""
    sales_group_id = getattr(settings, "CRM_SALES_REPORT_GROUP_ID", None) or -1003854308552
    sales_topic_id = getattr(settings, "CRM_SALES_REPORT_TOPIC_ID", None) or 115
    return _send_tg_message(text, sales_group_id, sales_topic_id)


def extract_phone_numbers(text: str) -> List[str]:
    """Extract 9-12 digit phone numbers from text."""
    if not text:
        return []
    cleaned = re.sub(r"[\s\-\(\)]+", "", text)
    matches = re.findall(r"(?:998)?\d{9}", cleaned)
    results = []
    for m in matches:
        digits = m if len(m) == 9 else m[-9:]
        results.append(digits)
    return list(set(results))


def extract_brand_or_client(text: str) -> List[str]:
    """Extract brand name or client name markers from note text."""
    if not text:
        return []
    queries = []
    brand_match = re.search(r"Brand\s*(?:nomi)?\s*[:\-]\s*([^\n\r,]+)", text, re.IGNORECASE)
    if brand_match:
        queries.append(brand_match.group(1).strip())
    client_match = re.search(r"Mijoz\s*[:\-]\s*([^\n\r,]+)", text, re.IGNORECASE)
    if client_match:
        queries.append(client_match.group(1).strip())
    return queries


async def resolve_seller_for_income(
    record: Dict[str, Any],
    airtable_sync: Any = None,
    amocrm_sync: Any = None,
) -> Optional[Dict[str, Any]]:
    """Determine who sold this income entry."""
    fields = record.get("fields", {}) or {}
    trx_title = fields.get("Tranzaksiya", "")
    izoh = fields.get("Izoh", "")
    project_links = fields.get("Loyiha", []) or []

    # 1. Check linked Loyiha record
    if project_links and airtable_sync:
        project_id = project_links[0]
        try:
            proj = await asyncio.to_thread(airtable_sync.get_project, project_id)
            if proj:
                p_fields = proj.get("fields", {}) or {}
                p_seller = p_fields.get("Sotuvchi") or []
                if p_seller:
                    seller_id = p_seller[0] if isinstance(p_seller, list) else p_seller
                    return {
                        "seller_id": seller_id,
                        "source": "Loyiha kartasi",
                        "project_id": project_id,
                        "project_name": p_fields.get("Loyiha nomi") or trx_title,
                    }
        except Exception as exc:
            logger.debug("[SUPERVISOR] Failed to check project %s: %s", project_id, exc)

    # 2. Extract phone numbers and search AmoCRM
    phones = extract_phone_numbers(izoh)
    if amocrm_sync:
        for phone in phones:
            try:
                leads = await amocrm_sync.search_leads(phone, limit=2)
                for lead in leads:
                    resp_id = lead.get("responsible_user_id")
                    if resp_id and resp_id in AMOCRM_USER_TO_JAMOA:
                        return {
                            "seller_id": AMOCRM_USER_TO_JAMOA[resp_id],
                            "source": f"AmoCRM telefon ({phone})",
                            "lead_id": lead.get("id"),
                            "lead_name": lead.get("name"),
                        }
            except Exception as exc:
                logger.debug("[SUPERVISOR] AmoCRM phone search failed: %s", exc)

    # 3. Extract brand/client or project query and search AmoCRM
    search_terms = extract_brand_or_client(izoh)
    if not search_terms and trx_title:
        clean_title = re.sub(r"^(?:Kirim\s*[\-\:]\s*|KIRIM\-[A-Za-z0-9\-]+\s*)", "", trx_title).strip()
        if len(clean_title) >= 3:
            search_terms.append(clean_title)

    if amocrm_sync:
        for term in search_terms:
            try:
                leads = await amocrm_sync.search_leads(term, limit=3)
                for lead in leads:
                    resp_id = lead.get("responsible_user_id")
                    if resp_id and resp_id in AMOCRM_USER_TO_JAMOA:
                        return {
                            "seller_id": AMOCRM_USER_TO_JAMOA[resp_id],
                            "source": f"AmoCRM bitim ({term})",
                            "lead_id": lead.get("id"),
                            "lead_name": lead.get("name"),
                        }
            except Exception as exc:
                logger.debug("[SUPERVISOR] AmoCRM term search failed: %s", exc)

    # 4. Text keyword matching in Izoh
    lowered_izoh = izoh.lower()
    for name_key, jamoa_id in NAME_TO_JAMOA.items():
        if re.search(rf"\b{name_key}\b", lowered_izoh):
            return {
                "seller_id": jamoa_id,
                "source": f"Izohdagi ism ({name_key.title()})",
            }

    return None


async def supervise_recent_incomes(
    airtable_sync: Any = None,
    amocrm_sync: Any = None,
    notify_telegram: bool = True,
) -> Dict[str, int]:
    """Audit unassigned Kirim records, resolve sellers, and notify."""
    from src.services.core.airtable_sync import AirtableSync
    from src.services.core.crm.amocrm.sync import AmoCRMSync

    at_sync = airtable_sync or AirtableSync(table_name="Tranzaksiyalar")
    crm_sync = amocrm_sync or AmoCRMSync()

    try:
        raw_records = await asyncio.to_thread(at_sync.get_transactions, force_refresh=True)
        records = []
        for r in raw_records:
            r_fields = r.get("fields", {}) or {}
            turi = r_fields.get("Turi")
            if isinstance(turi, dict):
                turi = turi.get("name")
            sana = str(r_fields.get("Sana") or "").strip()
            if sana and sana < SEPTEMBER_START_DATE:
                continue
            if (turi or "").strip() == "Kirim" and not r_fields.get("Sotuvchi"):
                records.append(r)
    except Exception as exc:
        logger.error("[SUPERVISOR] Failed to query unassigned incomes: %s", exc)
        return {"checked": 0, "resolved": 0, "unresolved": 0}

    stats = {"checked": len(records), "resolved": 0, "unresolved": 0}
    for record in records:
        rec_id = record.get("id")
        fields = record.get("fields", {}) or {}
        trx_title = fields.get("Tranzaksiya") or "Nomsiz kirim"
        summa = fields.get("Summa UZS") or fields.get("Summa") or 0
        valyuta = fields.get("Valyuta") or "UZS"
        izoh = (fields.get("Izoh") or "").strip()
        project_links = fields.get("Loyiha") or []

        resolution = await resolve_seller_for_income(record, airtable_sync=at_sync, amocrm_sync=crm_sync)
        if resolution and resolution.get("seller_id"):
            seller_id = resolution["seller_id"]
            seller_info = JAMOA_SELLER_INFO.get(seller_id, {"name": "Sotuvchi", "handle": ""})
            s_name = seller_info["name"]
            s_handle = seller_info["handle"]

            # Update Tranzaksiyalar record
            try:
                update_ok = await asyncio.to_thread(at_sync.update_project_fields, rec_id, {"Sotuvchi": [seller_id]})
                if not update_ok:
                    raise RuntimeError(f"Airtable update_project_fields returned falsy for record {rec_id}")
                # If project was linked and missing seller, update it too
                if project_links:
                    proj_sync = AirtableSync(table_name="Loyihalar")
                    await asyncio.to_thread(proj_sync.update_project_fields, project_links[0], {"Sotuvchi": [seller_id]})

                stats["resolved"] += 1
                logger.info("[SUPERVISOR] Resolved seller for %s -> %s (%s)", trx_title, s_name, resolution["source"])

                patent_extra = ""
                if "patent" in (trx_title + " " + izoh).lower() and summa > 5_000_000:
                    patent_extra = " <i>(5 mln so'mi xizmat haqi hisoblanadi, qolgani davlat boji)</i>"

                if notify_telegram:
                    msg = (
                        "🟢 <b>[OISHA AI NAZORATCHI] Kirim sotuvchisi aniqlandi:</b>\n\n"
                        f"💰 <b>Summa:</b> {summa:,.0f} {valyuta}{patent_extra}\n"
                        f"📝 <b>Tranzaksiya:</b> {trx_title}\n"
                        f"👤 <b>Sotuvchi:</b> {s_name} {s_handle}\n"
                        f"🔍 <b>Manba:</b> {resolution['source']}"
                    )
                    _dispatch_supervisor_alert(msg)
                _discard_alerted_record_id(rec_id)
            except Exception as exc:
                logger.error("[SUPERVISOR] Failed to update Airtable for %s: %s", rec_id, exc)
        else:
            stats["unresolved"] += 1
            if rec_id not in _ALERTED_RECORD_IDS:
                if notify_telegram:
                    snippet = izoh[:150] + ("..." if len(izoh) > 150 else "") if izoh else "Izoh yo'q"
                    msg = (
                        "⚠️ <b>[OISHA AI NAZORATCHI] Diqqat: Kirim bo'yicha sotuvchi aniqlanmadi!</b>\n\n"
                        f"💰 <b>Summa:</b> {summa:,.0f} {valyuta}\n"
                        f"📝 <b>Tranzaksiya:</b> {trx_title}\n"
                        f"📋 <b>Izoh:</b> <i>{snippet}</i>\n\n"
                        "❓ <i>Ushbu kirimni qaysi sotuvchi amalga oshirgan? Iltimos, Airtable'da 'Sotuvchi' ustuniga belgilang.</i>"
                    )
                    # Only mark as alerted once the notification is actually delivered,
                    # otherwise a transient Telegram failure permanently suppresses it.
                    if _dispatch_supervisor_alert(msg):
                        _save_alerted_record_id(rec_id)
                    else:
                        logger.warning(
                            "[SUPERVISOR] Failed to deliver unresolved-income alert for %s; will retry next cycle",
                            rec_id,
                        )

    return stats


async def income_supervisor_loop() -> None:
    """Continuous supervisor loop (runs every 120 seconds)."""
    logger.info("[SUPERVISOR] Oisha AI Income Supervisor started (interval: 120s).")
    await asyncio.sleep(45)  # initial boot cooldown
    while True:
        try:
            await supervise_recent_incomes(notify_telegram=True)
        except Exception as exc:
            logger.error("[SUPERVISOR] Error in income supervisor loop: %s", exc)
        await asyncio.sleep(120)
