"""
Telegram Prospect Importer to amoCRM.

Telegram guruh va kanallaridan (prospect_discovery) topilgan yuqori
ehtimolli potensial mijozlarni amoCRM 'Yangi LEads' bosqichiga eslatma bilan tushiradi.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from src.services.core.crm.amocrm.sync import AmoCRMSync
from src.services.core.crm.amocrm_pipeline_config import (
    SALES_NEW_STATUS_ID,
    SALES_PIPELINE_ID,
)

logger = logging.getLogger("tg_prospect_importer")

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_IMPORTED_STORE = _PROJECT_ROOT / "data" / "imported_tg_prospects.json"


def _load_imported_keys() -> set[str]:
    if not _IMPORTED_STORE.exists():
        return set()
    try:
        with open(_IMPORTED_STORE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("imported_keys", []))
    except Exception as e:
        logger.warning(f"[TG_PROSPECT_IMPORTER] Deduplikatsiyani o'qishda xato: {e}")
        return set()


def _save_imported_key(key: str) -> None:
    os.makedirs(_IMPORTED_STORE.parent, exist_ok=True)
    keys = _load_imported_keys()
    keys.add(key)
    try:
        with open(_IMPORTED_STORE, "w", encoding="utf-8") as f:
            json.dump({"imported_keys": sorted(list(keys))}, f, indent=2)
    except Exception as e:
        logger.warning(f"[TG_PROSPECT_IMPORTER] Saqlashda xato: {e}")


def build_prospect_playbook(prospect_data: Dict[str, Any]) -> str:
    service = prospect_data.get("service") or "Brending"
    url = prospect_data.get("url") or "Havola mavjud emas"
    phone = prospect_data.get("phone") or "Telefon aniqlanmagan"
    quote = prospect_data.get("quote") or prospect_data.get("message_text") or ""
    chat_title = prospect_data.get("chat_title") or "Telegram hamjamiyati"

    return f"""### 📡 TELEGRAM POTENSIAL MIJOZ (PROSPECT)
• Xizmat sohasi: {service.capitalize()}
• Manba: {chat_title}
• Havola: {url}
• Telefon: {phone}

### 💬 MIJOZNING XABARI / TALABI:
"{quote.strip()}"

### 🎯 U BILAN QANDAY MUNOSABAT O'RNATISH KERAK:
1. **Shaxsiy muloqot boshlash (Telegram DM)**:
   "Assalomu alaykum! {chat_title} dagi e'loningizni ko'rib bog'lanmoqdaman. Jon Branding agentligidanmiz."
2. **Qiymat taklif qilish**:
   "Siz aytgan {service} yo'nalishida yaqinda yakunlangan muvaffaqiyatli keyslarimiz va dastlabki tekshiruv shartlarimizni ulashmoqchi edim."
3. **Qo'ng'iroqqa taklif**:
   "Agar sizga qulay bo'lsa, loyiha tafsilotlarini 10 daqiqalik qo'ng'iroqda muhokama qilishimiz mumkin."
"""


class TelegramProspectImporter:
    """Telegram potensial mijozlarini amoCRMga tushiruvchi servis."""

    def __init__(self, amo: Optional[AmoCRMSync] = None):
        self.amo = amo or AmoCRMSync()

    async def import_pending_prospects(self, limit: int = 5) -> Dict[str, Any]:
        from src.services.core.leads.prospect_store import get_prospect_store

        store = get_prospect_store()
        await store.initialize()

        imported_keys = _load_imported_keys()
        rows = await store.pool.execute("SELECT * FROM prospect_queue ORDER BY created_at DESC LIMIT 50")

        imported = []
        headers = self.amo._get_headers()

        for row in rows:
            key = row["candidate_key"]
            if key in imported_keys:
                continue

            try:
                payload_data = json.loads(row["payload"])
            except Exception:
                continue

            service = payload_data.get("service") or "Brending"
            phone = payload_data.get("phone") or ""
            lead_name = f"TG: {service.capitalize()} so'rovi"
            if phone:
                lead_name += f" ({phone})"

            note_text = build_prospect_playbook(payload_data)

            # AmoCRM da lead yaratish
            lead_payload = {
                "name": lead_name,
                "pipeline_id": SALES_PIPELINE_ID,
                "status_id": SALES_NEW_STATUS_ID,
                "price": 0,
                "_embedded": {
                    "tags": [{"name": "Telegram_Prospect"}, {"name": service.capitalize()}]
                },
            }

            url = f"{self.amo.base_url}/api/v4/leads"
            try:
                resp = requests.post(url, headers=headers, json=[lead_payload], timeout=30)
                if resp.status_code in (200, 201):
                    new_id = resp.json().get("_embedded", {}).get("leads", [{}])[0].get("id")
                    if new_id:
                        note_payload = [{"note_type": "common", "params": {"text": note_text}}]
                        requests.post(f"{self.amo.base_url}/api/v4/leads/{new_id}/notes", headers=headers, json=note_payload, timeout=20)
                        _save_imported_key(key)
                        imported.append({"candidate_key": key, "new_lead_id": new_id, "service": service})
                        logger.info(f"[TG_PROSPECT_IMPORTER] Yangi Telegram lead #{new_id} yaratildi.")
                        if len(imported) >= limit:
                            break
            except Exception as e:
                logger.error(f"[TG_PROSPECT_IMPORTER] Lead yaratishda xato: {e}")

        return {"imported_count": len(imported), "leads": imported}
