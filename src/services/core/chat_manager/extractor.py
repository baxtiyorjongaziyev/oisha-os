"""Suhbatdan zayavka ajratish: kategoriya + 1 gaplik xulosa → amoCRM.

Mijoz jim qolgan dialoglar (standart 5 daqiqa) free-AI router orqali tahlil
qilinadi. Natija `chat_requests` ga yoziladi; "lead" kategoriyasi telefon bilan
kelganda amoCRM "Sotuv" voronkasida yangi lid ochiladi (dialog boshiga bitta).
Router ishlamasa dialog belgilanmaydi — keyingi siklda qayta urinadi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.services.core.chat_manager import store

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,18}\d")
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_PROMPT = (
    "Sen Jon Branding agentligining sotuv tahlilchisisan. Mijoz bilan suhbatni o'qib, "
    "faqat JSON qaytar: {\"categories\": [...], \"summary\": \"...\", \"phone\": \"...\"}. "
    "categories — quyidagilardan nol yoki bir nechtasi: "
    "\"lead\" (mijoz kontakt qoldirdi yoki aniq buyurtma/uchrashuv xohlaydi), "
    "\"interested\" (narx/xizmat so'radi, qiziqdi, lekin kontakt yo'q), "
    "\"complaint\" (norozilik, shikoyat, e'tiroz), "
    "\"suggestion\" (taklif, hamkorlik). Salomlashish yoki spam bo'lsa — bo'sh ro'yxat. "
    "summary — o'zbek tilida bitta gap, uchinchi shaxsda (\"Mijoz ... so'radi\"). "
    "phone — matnda telefon bo'lsa, aks holda bo'sh. Hech narsani o'ylab topma."
)


def find_phone(text: str) -> str:
    for match in _PHONE_RE.finditer(text or ""):
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) == 9:
            digits = "998" + digits
        if 12 <= len(digits) <= 15:
            return "+" + digits
    return ""


def _transcript(messages: List[Dict[str, Any]]) -> str:
    who = {"client": "Mijoz", "ai_draft": "AI", "operator": "Menejer"}
    return "\n".join(
        f"{who.get(m['author'], m['author'])}: {m['text']}" for m in messages[-30:]
    )


def parse_result(raw: str) -> Optional[Dict[str, Any]]:
    """LLM javobidan JSON'ni oladi; noto'g'ri bo'lsa None."""
    match = _JSON_RE.search(raw or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    categories = [
        c for c in data.get("categories") or [] if c in store.REQUEST_CATEGORIES
    ]
    summary = str(data.get("summary") or "").strip()
    phone = find_phone(str(data.get("phone") or ""))
    return {"categories": list(dict.fromkeys(categories)), "summary": summary, "phone": phone}


async def _create_amocrm_lead(amocrm: Any, dialog: Dict[str, Any], summary: str,
                              phone: str) -> Optional[int]:
    from src.services.core.crm.amocrm_pipeline_config import (
        SALES_NEW_STATUS_ID,
        SALES_PIPELINE_ID,
    )

    channel = "Telegram" if dialog["channel"] == "telegram" else "Instagram"
    lead_id = await amocrm.create_lead(
        name=dialog["name"] or f"{channel} mijoz",
        phone=phone,
        pipeline_id=SALES_PIPELINE_ID,
        status_id=SALES_NEW_STATUS_ID,
    )
    if not lead_id:
        return None
    note = f"[AI Chat Manager, {channel}] {summary}"
    await asyncio.to_thread(amocrm.add_lead_note, int(lead_id), note)
    return int(lead_id)


async def extract_dialog(dialog: Dict[str, Any], router: Any,
                         amocrm: Any = None) -> List[int]:
    """Bitta dialogni tahlil qiladi. Yangi zayavka id'larini qaytaradi."""
    messages = await asyncio.to_thread(store.get_messages, dialog["id"], 60)
    if not any(m["direction"] == "in" for m in messages):
        await asyncio.to_thread(store.mark_extracted, dialog["id"])
        return []
    result = await router.generate_text(
        _transcript(messages), system=SYSTEM_PROMPT, max_tokens=300, temperature=0.1
    )
    parsed = parse_result(getattr(result, "text", ""))
    if parsed is None:
        logger.warning("[chat-manager] dialog %s: AI JSON qaytarmadi", dialog["id"])
        await asyncio.to_thread(store.mark_extracted, dialog["id"])
        return []
    client_text = " ".join(m["text"] for m in messages if m["direction"] == "in")
    phone = parsed["phone"] or find_phone(client_text) or dialog.get("phone", "")
    created: List[int] = []
    for category in parsed["categories"]:
        summary = parsed["summary"] or store.REQUEST_CATEGORIES[category]
        request_id, is_new = await asyncio.to_thread(
            store.upsert_request, dialog["id"], category, summary, phone
        )
        if is_new:
            created.append(request_id)
        if category == "lead" and phone and amocrm is not None:
            existing = [
                r for r in await asyncio.to_thread(store.list_requests, dialog["id"])
                if r["id"] == request_id
            ]
            if existing and not existing[0]["amocrm_lead_id"]:
                try:
                    lead_id = await _create_amocrm_lead(amocrm, dialog, summary, phone)
                except Exception as exc:  # noqa: BLE001 - CRM down must not lose request
                    logger.warning("[chat-manager] amoCRM lead failed: %s", exc)
                    lead_id = None
                if lead_id:
                    await asyncio.to_thread(store.set_request_lead, request_id, lead_id)
    await asyncio.to_thread(store.mark_extracted, dialog["id"])
    return created


async def run_cycle(router: Any, amocrm: Any = None, min_idle_sec: float = 300) -> int:
    """Jim qolgan dialoglarni tahlil qiladi; yaratilgan zayavkalar soni."""
    from src.services.utils.free_ai_router import AllProvidersUnavailableError

    dialogs = await asyncio.to_thread(store.dialogs_needing_extraction, min_idle_sec)
    total = 0
    for dialog in dialogs:
        try:
            total += len(await extract_dialog(dialog, router, amocrm))
        except AllProvidersUnavailableError as exc:
            logger.warning("[chat-manager] AI mavjud emas, sikl to'xtadi: %s", exc)
            break
    return total
