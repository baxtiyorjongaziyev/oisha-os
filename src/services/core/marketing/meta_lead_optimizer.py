"""Avtomatik Meta Lead Ads Optimizatsiyasi (Conversion Leads).

Faol Ad Set'larni kampaniyalar kesimida tekshiradi va oddiy `LEAD_GENERATION` (shunchaki forma)
rejimida turganlarini avtomatik `QUALITY_LEAD` (Conversion Leads) optimizatsiyasiga o'tkazadi.
Lowest Cost / Advantage Campaign Budget talablariga muvofiq, bir xil kampaniyadagi barcha
guruhlarni bir vaqtda moslashtiradi.
"""
from __future__ import annotations

import collections
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.settings import settings

logger = logging.getLogger("MetaLeadOptimizer")

_DEFAULT_API_VERSION = "v21.0"
_DEFAULT_AD_ACCOUNT_ID = "370591433710957"


def _secret_text(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "").strip()


def get_meta_config() -> Dict[str, str]:
    """Meta Ads API uchun sozlamalarni xavfsiz oladi."""
    token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
    if not token:
        token = _secret_text(getattr(settings, "META_PAGE_ACCESS_TOKEN", None))

    dataset_id = os.environ.get("META_CAPI_DATASET_ID", "").strip()
    if not dataset_id:
        dataset_id = str(getattr(settings, "META_CAPI_DATASET_ID", "") or "").strip()

    ad_account_id = os.environ.get("META_AD_ACCOUNT_ID", "").strip()
    if not ad_account_id:
        ad_account_id = str(getattr(settings, "META_AD_ACCOUNT_ID", "") or "").strip()
    if not ad_account_id:
        ad_account_id = _DEFAULT_AD_ACCOUNT_ID

    version = os.environ.get("META_GRAPH_API_VERSION", "").strip() or _DEFAULT_API_VERSION
    return {
        "access_token": token,
        "dataset_id": dataset_id,
        "ad_account_id": ad_account_id,
        "version": version,
    }


def _account_path(account_id: str) -> str:
    acc = (account_id or "").strip()
    return acc if acc.startswith("act_") else f"act_{acc}"


def fetch_active_lead_adsets(cfg: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Ad Account'dagi faol Lead Generation Ad Set'larni qaytaradi."""
    conf = cfg or get_meta_config()
    token = conf.get("access_token")
    account_id = conf.get("ad_account_id", "")
    version = conf.get("version", _DEFAULT_API_VERSION)

    if not token or not account_id:
        logger.warning("[META OPTIMIZER] Token yoki Ad Account ID mavjud emas")
        return []

    url = f"https://graph.facebook.com/{version}/{_account_path(account_id)}/adsets"
    params = {
        "fields": "id,name,status,optimization_goal,destination_type,promoted_object,campaign_id",
        "effective_status": json.dumps(["ACTIVE"]),
        "access_token": token,
        "limit": 100,
    }

    try:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            logger.warning("[META OPTIMIZER] Adsets so'rovi xatosi: %s", resp.text[:200])
            return []
        data = resp.json().get("data", [])
        return [adset for adset in data if isinstance(adset, dict)]
    except Exception as exc:
        logger.error("[META OPTIMIZER] fetch_active_lead_adsets xatosi: %s", exc)
        return []


def upgrade_adset_to_quality_lead(
    adset: Dict[str, Any], cfg: Optional[Dict[str, str]] = None
) -> Tuple[bool, str]:
    """Bitta Ad Set'ni QUALITY_LEAD optimizatsiyasiga o'tkazishga urinadi."""
    conf = cfg or get_meta_config()
    token = conf.get("access_token", "")
    version = conf.get("version", _DEFAULT_API_VERSION)
    adset_id = str(adset.get("id") or "").strip()

    if not token or not adset_id:
        return False, "Token yoki Ad Set ID yetishmaydi"

    url = f"https://graph.facebook.com/{version}/{adset_id}"
    payload: Dict[str, Any] = {
        "optimization_goal": "QUALITY_LEAD",
        "access_token": token,
    }

    try:
        resp = requests.post(url, data=payload, timeout=20)
        res_data = resp.json()
        if resp.status_code == 200 and res_data.get("success") is True:
            return True, "Muvaffaqiyatli o'tkazildi"
        err_msg = str(res_data.get("error", {}).get("message") or resp.text[:200])
        return False, err_msg
    except Exception as exc:
        return False, str(exc)


async def notify_optimization_success(adset_name: str, adset_id: str, bot_runtime: Any = None) -> None:
    """Telegram orqali jamoaga optimizatsiya muvaffaqiyati haqida xabar beradi."""
    text = (
        f"🎯 <b>[Meta Avtopilot]: Reklama Guruhi Yangilandi!</b>\n\n"
        f"📌 <b>Ad Set:</b> {adset_name}\n"
        f"🆔 <b>ID:</b> <code>{adset_id}</code>\n"
        f"🚀 <b>Yangi Rejim:</b> Conversion Leads (QUALITY_LEAD)\n"
        f"📈 <i>Endi algoritm faqat sifatli lidlarni qidiradi.</i>"
    )
    from src.settings import settings

    target_chat = getattr(settings, "TEAM_GROUP_ID", None) or getattr(settings, "OWNER_ID", None)
    if not bot_runtime or not target_chat:
        logger.info("[META OPTIMIZER] Xabar loglandi: %s", adset_name)
        return

    try:
        send_fn = getattr(bot_runtime, "send_message", None)
        if callable(send_fn):
            await send_fn(target_chat, text, parse_mode="html")
    except Exception as exc:
        logger.warning("[META OPTIMIZER] Telegram bildirishnomasi jo'natilmadi: %s", exc)


def run_lead_optimization_sweep(cfg: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Barcha faol guruhlarni kampaniyalar kesimida skaner qiladi va yangilaydi."""
    adsets = fetch_active_lead_adsets(cfg)
    total_scanned = len(adsets)
    converted: List[str] = []
    skipped: List[str] = []
    pending_warmup: List[str] = []

    # Kampaniyalar bo'yicha guruhlash
    campaign_map: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for adset in adsets:
        cid = str(adset.get("campaign_id") or "single")
        goal = str(adset.get("optimization_goal") or "").upper()
        if goal == "QUALITY_LEAD":
            skipped.append(str(adset.get("id") or ""))
        campaign_map[cid].append(adset)

    for cid, camp_adsets in campaign_map.items():
        all_leadgen = [a for a in camp_adsets if str(a.get("optimization_goal") or "").upper() == "LEAD_GENERATION"]
        if not all_leadgen:
            continue

        for adset in all_leadgen:
            adset_id = str(adset.get("id") or "")
            name = str(adset.get("name") or adset_id)
            ok, msg = upgrade_adset_to_quality_lead(adset, cfg)
            if ok:
                logger.info("[META OPTIMIZER] '%s' QUALITY_LEAD ga o'tkazildi!", name)
                converted.append(name)
            else:
                logger.info("[META OPTIMIZER] '%s' kutishda: %s", name, msg)
                pending_warmup.append(name)

    return {
        "scanned": total_scanned,
        "converted": converted,
        "already_quality": len(skipped),
        "pending": pending_warmup,
    }
