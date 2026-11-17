"""Stage classification: free_ai_router JSON with a signals-based fallback.

Stages: greeting, discovery, offer, objection, card_sent, paid, ghost.
``paid`` always comes from Airtable matching (``card_watch.matcher.is_paid``),
never from the LLM, so the model cannot "close" a deal on its own.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from src.services.core.card_watch.detector import CardSend
from src.services.core.card_watch.matcher import is_paid
from src.services.core.sales_copilot.signals import Signals
from src.services.core.sales_copilot.transcript import Transcript

logger = logging.getLogger("SalesCopilot")

STAGES = ("greeting", "discovery", "offer", "objection", "card_sent", "paid", "ghost")
GHOST_AFTER = timedelta(hours=72)
MAX_PROMPT_MESSAGES = 30

SYSTEM = (
    "Sen Jon Branding sotuv boʻlimi tahlilchisisan. Mijoz bilan yozishmani oʻqib, "
    "faqat JSON qaytar. Qoralama oʻzbek tilida, qisqa, hurmat bilan, sotuvchi nomidan."
)
PROMPT = (
    "Bosqichlar: greeting (salomlashish), discovery (ehtiyojni aniqlash), offer (narx/taklif berilgan), "
    "objection (eʼtiroz: qimmat, oʻylab koʻraman), card_sent (karta yuborilgan), ghost (mijoz jim).\n"
    "Qaytar: {{\"stage\": ..., \"quote\": \"bosqichni isbotlovchi aynan iqtibos\", "
    "\"confidence\": 0..1, \"blocker\": \"toʻsiq yoki boʻsh\", \"next_step\": \"sotuvchiga maslahat\", "
    "\"draft\": \"mijozga yuborish uchun tayyor matn\"}}\n"
    "Mijoz: {client}\nYozishma (M=biz, C=mijoz):\n{lines}"
)

FALLBACK_DRAFTS = {
    "greeting": "Assalomu alaykum! Biznesingiz haqida biroz aytib bersangiz, sizga mos yechimni tayyorlab beraman.",
    "discovery": "Maʼlumot uchun rahmat! Sizga mos taklifni tayyorladim — qisqa qoʻngʻiroqda tushuntirsam boʻladimi?",
    "offer": "Taklifimiz boʻyicha savollaringiz boʻlsa, bemalol yozing. Bugun boshlasak, ish muddati tezroq boʻladi.",
    "objection": "Tushunaman. Toʻlovni bosqichlarga boʻlib berishimiz mumkin — sizga qaysi variant qulay?",
    "card_sent": "Karta raqamini yuborgan edim. Toʻlov qilgan boʻlsangiz, chekni yuborsangiz, ishni darhol boshlaymiz.",
    "ghost": "Assalomu alaykum! Loyihangiz boʻyicha hali ham qiziqish bormi? Savollaringiz boʻlsa, javob beraman.",
    "paid": "",
}


@dataclass
class StageResult:
    stage: str
    quote: str
    confidence: float
    blocker: str = ""
    next_step: str = ""
    draft: str = ""
    source: str = "rules"  # "llm" | "rules" | "airtable"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _last_quote(t: Transcript, side: Optional[str] = None) -> str:
    fallback = ""
    for m in reversed(t.messages):
        if side is None or m.side == side:
            if not m.text.startswith("["):  # skip media markers when real text exists
                return m.text[:200]
            fallback = fallback or m.text[:200]
    return fallback


def fallback_stage(t: Transcript, s: Signals, now: datetime) -> StageResult:
    """Deterministic stage from signals (used when the LLM is unavailable/invalid)."""
    ghost = s.last_side == "us" and s.last_at is not None and now - s.last_at >= GHOST_AFTER
    if s.card_at:
        stage, quote, conf = "card_sent", s.card_message[:200], 0.9
    elif s.objections and (s.price_at or s.client_messages >= 2):
        stage, quote, conf = "objection", _last_quote(t, "client"), 0.6
    elif s.price_at:
        stage, quote, conf = "offer", next((m.text[:200] for m in t.messages if m.at == s.price_at), ""), 0.7
    elif s.client_messages >= 2 and s.our_messages >= 2:
        stage, quote, conf = "discovery", _last_quote(t, "client"), 0.5
    else:
        stage, quote, conf = "greeting", _last_quote(t), 0.5
    if ghost and stage != "card_sent":
        stage, conf = "ghost", 0.7
    return StageResult(stage, quote, conf, "", "", FALLBACK_DRAFTS.get(stage, ""), "rules")


def build_prompt(t: Transcript, crm: Optional[Dict[str, Any]] = None) -> str:
    lines = []
    for m in t.messages[-MAX_PROMPT_MESSAGES:]:
        who = "C" if m.side == "client" else "M"
        lines.append(f"[{m.at.strftime('%d.%m %H:%M')}] {who}: {m.text[:400]}")
    prompt = PROMPT.format(client=t.client_name or t.chat_title, lines="\n".join(lines))
    if crm:
        extra = [f"CRM bitim: {crm.get('lead', '')} narx {crm.get('price') or '?'}"]
        if crm.get("call_summary"):
            extra.append(f"Qoʻngʻiroq tahlili: {str(crm['call_summary'])[:400]}")
        extra.extend(f"Izoh: {n}" for n in crm.get("notes") or [])
        prompt += "\n" + "\n".join(extra)
    return prompt


def parse_llm(raw: str, fallback: StageResult) -> Optional[StageResult]:
    """Validate model JSON; ``None`` when unusable."""
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    stage = str(data.get("stage", "")).strip().lower()
    if stage not in STAGES or stage == "paid":
        return None
    try:
        conf = min(1.0, max(0.0, float(data.get("confidence", 0))))
    except (TypeError, ValueError):
        conf = 0.0
    draft = str(data.get("draft") or "").strip() or FALLBACK_DRAFTS.get(stage, "")
    return StageResult(
        stage=stage,
        quote=str(data.get("quote") or fallback.quote)[:300],
        confidence=conf,
        blocker=str(data.get("blocker") or "")[:300],
        next_step=str(data.get("next_step") or "")[:300],
        draft=draft[:700],
        source="llm",
    )


def check_paid(t: Transcript, s: Signals, incomes: Iterable[Dict[str, Any]]) -> bool:
    if not s.card_at:
        return False
    send = CardSend(
        manager_key=t.manager_key, chat_id=t.chat_id, chat_title=t.chat_title,
        client_name=t.client_name, message_id=0, sent_at=s.card_at,
        amount=s.card_amount, card=s.card,
    )
    return is_paid(send, incomes)


async def classify(
    t: Transcript,
    s: Signals,
    now: datetime,
    incomes: List[Dict[str, Any]],
    router: Any = None,
    use_llm: bool = True,
    crm: Optional[Dict[str, Any]] = None,
) -> StageResult:
    base = fallback_stage(t, s, now)
    if check_paid(t, s, incomes):
        return StageResult("paid", s.card_message[:200], 0.95, source="airtable")
    if not use_llm:
        return base
    try:
        if router is None:
            from src.services.utils.free_ai_router import get_free_ai_router

            router = get_free_ai_router()
        res = await router.generate_text(build_prompt(t, crm),system=SYSTEM, max_tokens=600, temperature=0.2)
        text = getattr(res, "text", res)
        parsed = parse_llm(str(text or ""), base)
    except Exception as exc:  # provider outage => deterministic fallback
        logger.warning("[SALES_COPILOT] stage LLM failed: %s", type(exc).__name__)
        return base
    if parsed is None:
        return base
    if base.stage == "card_sent" and parsed.stage in {"greeting", "discovery", "offer"}:
        parsed.stage = "card_sent"  # a sent card is a hard fact; never regress it
    return parsed
