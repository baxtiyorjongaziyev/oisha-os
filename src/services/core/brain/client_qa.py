"""AI Q&A over unified client data.

Answers free-text questions about a client ("mijoz haqida savol") by pulling
together everything Oisha knows — AmoCRM lead, Telegram history, matching
Airtable projects, and the Instagram profile — via `ClientContextAggregator`,
then asking the free-AI router to answer in Uzbek, grounded only in that
gathered context.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from src.services.core.brain.client_context import ClientContextAggregator

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Sen Oisha — Jon Branding agentligining ichki operatsion yordamchisisan. "
    "Senga mijoz haqida barcha manbalardan (AmoCRM, Telegram, Airtable, Instagram) yig'ilgan "
    "ma'lumotlar beriladi. Faqat shu ma'lumotlarga tayanib, do'stona va aniq o'zbek tilida javob ber. "
    "Agar javob uchun ma'lumot yetarli bo'lmasa, buni ochiq ayt — o'ylab topma. "
    "Javobni qisqa va amaliy qil: kerak bo'lsa raqamlar, sanalar va keyingi qadamni ko'rsat."
)


class ClientQAError(Exception):
    """Raised when the client Q&A pipeline cannot produce an answer."""


async def answer_client_question(
    question: str,
    *,
    amocrm: Any,
    db: Any = None,
    tg_client: Any = None,
    lead_id: Optional[int] = None,
    name: str = "",
    phone: str = "",
) -> str:
    """Answer a free-text question about one client using every connected data source."""
    if not question or not question.strip():
        raise ClientQAError("Savol bo'sh bo'lishi mumkin emas.")
    if not (lead_id or name or phone):
        raise ClientQAError("Mijozni aniqlash uchun ism, telefon yoki lead ID kerak.")

    aggregator = ClientContextAggregator(amocrm=amocrm, db=db, tg_client=tg_client)
    context = await aggregator.gather(lead_id=lead_id, name=name, phone=phone)

    context_block = context.format_prompt_block()
    prompt = (
        f"Mijoz: {context.display_name}\n\n"
        f"{context_block}\n\n"
        f"---\nSavol: {question.strip()}"
    )

    from src.services.utils.free_ai_router import get_free_ai_router

    router = get_free_ai_router()
    try:
        result = await router.generate_text(prompt, system=_SYSTEM_PROMPT, max_tokens=1024, temperature=0.3)
    except Exception as exc:
        logger.error("[CLIENT_QA] AI generation failed: %s", exc)
        raise ClientQAError(f"AI javob bera olmadi: {exc}") from exc

    return result.text.strip()
