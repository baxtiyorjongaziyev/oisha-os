"""Sotuvchining soatlik check-in'ga javobini amoCRM vazifalariga aylantirish.

Oqim: javob matni + check-in matni -> LLM (free_ai_router) JSON ro'yxat qaytaradi ->
har bir mijoz uchun amoCRM'dan lid qidiriladi (telefon yoki ism) -> bitta lid topilsa
vazifa qo'yiladi. Topilmaganlari sotuvchidan do'stona so'raladi. Hech qachon raise qilmaydi.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, List, Optional

logger = logging.getLogger(__name__)

Generate = Callable[..., Awaitable[str]]

TASK_ACTIONS = {"callback", "payment", "meeting", "followup"}
NO_TASK_ACTIONS = {"wrong_number", "lost"}

EXTRACT_SYSTEM = """Sen sotuv bo'limi yordamchisisan. Sotuvchining xabaridan har bir mijoz bo'yicha
keyingi qadamni ajratib ol. Faqat JSON massiv qaytar, boshqa hech narsa yozma.

Har element:
{"client": "mijoz ismi yoki raqami", "phone": "+998... yoki null",
 "action": "callback|payment|meeting|followup|wrong_number|lost",
 "due": "YYYY-MM-DD HH:MM yoki null", "note": "qisqa izoh"}

Qoidalar:
- callback: qayta qo'ng'iroq (band, keyinroq, obeddan keyin). payment: to'lov va'dasi.
  meeting: uchrashuv. followup: boshqa keyingi qadam. wrong_number: raqam o'chirilgan/noto'g'ri.
  lost: rad etdi, qiziqmaydi.
- Telefonni faqat matnda aniq bo'lsa yoz. Check-in matnidagi ism-raqam juftligidan foydalan.
- Vaqtni hozirgi vaqtga nisbatan hisobla: "obeddan keyin" = bugun 14:00,
  "2 kunda" = 2 kundan keyin 10:00, "ertaga" = ertaga 10:00. Aniq bo'lmasa null.
- Bir xabarda bir nechta mijoz bo'lishi mumkin. Mijozga oid bo'lmagan gaplarni tashla.
- Kirill yozuvini ham tushun (Шахбоз = Shaxboz)."""

ACTION_LABELS = {
    "callback": "Qayta qo'ng'iroq",
    "payment": "To'lovni nazorat qilish",
    "meeting": "Uchrashuv",
    "followup": "Keyingi qadam",
}


@dataclass
class SellerAction:
    client: str
    action: str
    phone: Optional[str] = None
    due: Optional[datetime] = None
    note: str = ""


@dataclass
class ApplyResult:
    created: List[SellerAction] = field(default_factory=list)
    unresolved: List[SellerAction] = field(default_factory=list)
    skipped: List[SellerAction] = field(default_factory=list)


async def _router_generate(prompt: str, *, system: str, max_tokens: int, temperature: float) -> str:
    from src.services.utils.free_ai_router import get_free_ai_router

    result = await get_free_ai_router().generate_text(
        prompt, system=system, max_tokens=max_tokens, temperature=temperature
    )
    return (getattr(result, "text", "") or "").strip()


def _parse_due(raw: Any) -> Optional[datetime]:
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def parse_actions(raw: str) -> List[SellerAction]:
    """LLM javobidan JSON massivni ajratib oladi. Buzuq bo'lsa bo'sh ro'yxat."""
    match = re.search(r"\[.*\]", raw or "", re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group(0))
    except ValueError:
        return []
    actions: List[SellerAction] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "").strip().lower()
        client = str(item.get("client") or "").strip()
        if action not in TASK_ACTIONS | NO_TASK_ACTIONS or not client:
            continue
        phone = item.get("phone")
        actions.append(
            SellerAction(
                client=client,
                action=action,
                phone=str(phone).strip() if phone else None,
                due=_parse_due(item.get("due")),
                note=str(item.get("note") or "").strip(),
            )
        )
    return actions


async def extract_actions(
    reply_text: str,
    checkin_text: str,
    now: datetime,
    generate: Generate = _router_generate,
) -> List[SellerAction]:
    prompt = (
        f"Hozirgi vaqt: {now:%Y-%m-%d %H:%M} (Toshkent).\n\n"
        f"Oisha yuborgan check-in:\n{checkin_text}\n\n"
        f"Sotuvchi javobi:\n{reply_text}"
    )
    try:
        raw = await generate(prompt, system=EXTRACT_SYSTEM, max_tokens=800, temperature=0.1)
    except Exception:
        logger.error("[SELLER-REPLY] LLM chaqiruvi xato.", exc_info=True)
        return []
    actions = parse_actions(raw)
    for action in actions:  # LLM Toshkent vaqtida yozadi; timestamp to'g'ri chiqishi uchun tz biriktiramiz
        if action.due is not None:
            action.due = action.due.replace(tzinfo=now.tzinfo)
    return actions


def _digits(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())[-9:]


async def _find_lead_id(amocrm: Any, action: SellerAction) -> Optional[int]:
    queries = [_digits(action.phone)] if action.phone and len(_digits(action.phone)) == 9 else []
    queries.append(action.client)
    for query in queries:
        leads = await amocrm.search_leads(query, limit=2)
        if len(leads) == 1:
            return int(leads[0]["id"])
    return None


def _task_text(action: SellerAction) -> str:
    label = ACTION_LABELS.get(action.action, "Keyingi qadam")
    note = f": {action.note}" if action.note else ""
    return f"{label} — {action.client}{note} (sotuvchi javobidan, Oisha)"


async def apply_actions(
    amocrm: Any,
    actions: List[SellerAction],
    now: datetime,
    responsible_user_id: Optional[int] = None,
) -> ApplyResult:
    result = ApplyResult()
    for action in actions:
        if action.action in NO_TASK_ACTIONS:
            result.skipped.append(action)
            continue
        due = action.due or (now + timedelta(hours=2))
        try:
            lead_id = await _find_lead_id(amocrm, action)
            ok = lead_id is not None and await amocrm.create_task(
                element_id=lead_id,
                text=_task_text(action),
                complete_till=int(due.timestamp()),
                responsible_user_id=responsible_user_id,
            )
        except Exception:
            logger.error("[SELLER-REPLY] Vazifa yaratishda xato: %s", action.client, exc_info=True)
            ok = False
        (result.created if ok else result.unresolved).append(action)
    return result


def _when(action: SellerAction) -> str:
    return f" ({action.due:%d.%m %H:%M})" if action.due else ""


def format_summary(seller_name: str, result: ApplyResult) -> str:
    """Sotuvchiga samimiy, qisqa tasdiq."""
    if not (result.created or result.unresolved or result.skipped):
        return f"Rahmat, {seller_name}! Yozganlaringizni oldim 🙌"
    lines = [f"Rahmat, {seller_name}! Hammasini yozib qo'ydim 🙌"]
    if result.created:
        lines.append("")
        lines.append("amoCRM'ga vazifa qo'ydim:")
        lines += [f"• {ACTION_LABELS[a.action]} — {a.client}{_when(a)}" for a in result.created]
    if result.skipped:
        lines.append("")
        lines += [
            f"• {a.client} — {'raqam ishlamaydi' if a.action == 'wrong_number' else 'rad etdi'}, belgilab oldim"
            for a in result.skipped
        ]
    if result.unresolved:
        lines.append("")
        names = ", ".join(a.client for a in result.unresolved)
        lines.append(
            f"{names} — amoCRM'da lidini aniq topa olmadim. Raqamini yozib yuborsangiz, vazifani o'zim qo'yaman."
        )
    lines.append("")
    lines.append("Zo'r ketyapsiz, omad! Biror narsa kerak bo'lsa, shu yerga yozing 💪")
    return "\n".join(lines)
