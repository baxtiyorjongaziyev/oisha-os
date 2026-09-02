"""Hisobchi Vision — Extract transaction data from receipt/cheque images via Gemini Vision."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from src.settings import settings
from src.services.utils.gemini_fallback import generate_content_with_fallback

logger = logging.getLogger(__name__)


async def parse_receipt_image(client: Any, image_path: str) -> Optional[dict]:
    """Send a receipt/cheque photo to Gemini Vision and extract transaction data."""
    system_prompt = (
        "Sen Hisobchi — moliyaviy yordamchi. Rasmdagi kvitansiya/chek ma'lumotlarini o'qib, "
        "quyidagi JSON formatida qaytar. Faqat JSON, boshqa matn yo'q.\n\n"
        "{\n"
        '  "is_receipt": true/false,\n'
        '  "amount": 0,\n'
        '  "merchant": "Do\'kon nomi",\n'
        '  "date": "YYYY-MM-DD",\n'
        '  "items": [{"name": "...", "price": 0}],\n'
        '  "currency": "UZS",\n'
        '  "category_hint": "Tushlik",\n'
        '  "notes": ""\n'
        "}\n\n"
        "Agar rasmda chek/chek bo'lmasa, is_receipt: false qilib qaytar."
    )

    try:
        upload = client.files.upload(path=image_path)
        fallbacks = ("gemini-1.5-flash", "gemini-1.5-pro")
        response, model = await generate_content_with_fallback(
            client=client,
            primary_model=getattr(settings, "GEMINI_VISION_MODEL", None) or settings.GEMINI_CALL_MODEL,
            contents=[system_prompt, upload],
            env_name="GEMINI_VISION_FALLBACK_MODELS",
            extra_models=fallbacks,
            log_prefix="[HISOBCHI-VISION]",
        )
        if response and response.text:
            cleaned = response.text.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)
            if data.get("is_receipt"):
                return data
    except Exception as exc:
        logger.error("[HISOBCHI-VISION] Parse error: %s", exc)
    return None


async def process_receipt_photo(client: Any, photo_path: str) -> Optional[dict]:
    """Download and process a receipt photo, return structured transaction data."""
    parsed = await parse_receipt_image(client, photo_path)
    if not parsed or not parsed.get("is_receipt"):
        return None

    amount = parsed.get("amount", 0)
    if amount <= 0:
        return None

    return {
        "amount": int(amount),
        "merchant": (parsed.get("merchant") or "Noma'lum")[:50],
        "category": (parsed.get("category_hint") or "Boshqa")[:50],
        "date": parsed.get("date", ""),
        "items": parsed.get("items", []),
        "notes": parsed.get("notes", ""),
    }
