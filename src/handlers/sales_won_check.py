"""Toʻlov kartasi tabrigidan keyin amoCRM tekshiruvi: bitim Won ga oʻtkazilganmi.

Sotuvchi "TOʻLOV TASDIQLASH" kartasini yuborgach, bir oz kutib, uning oxirgi
sutkada Won (142) ga oʻtgan bitimi bor-yoʻqligi tekshiriladi. Yoʻq boʻlsa,
kartaga javoban eslatma yoziladi. Bu faqat oʻqish: CRM da hech narsa oʻzgarmaydi.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Optional

import structlog

from src.context import app_ctx
from src.handlers.non_crm_payment_intake import save_pending_intake
from src.services.core.crm.team_roster import find_staff
from src.services.core.rop.fetchers import RopFetcher, RopFetchError
from src.services.core.rop.targets import load_roster
from src.settings import settings
from src.time_utils import is_quiet_hours

logger = structlog.get_logger()

_WON_LOOKBACK_SECONDS = 86400
_NON_CRM_ASK_DELAY_SECONDS = 5
_NON_CRM_SELLER_SLUGS = frozenset({"hasanboy"})
_background_tasks: set = set()

SendFn = Callable[[int, int, str], Awaitable[Optional[int]]]

REMINDER_TEMPLATE = (
    "{seller}, amoCRMda bu bitim hali «Sotuv boʻldi» bosqichiga oʻtkazilmagan. "
    "Iltimos, bitimni yopib qoʻying."
)

CLIENT_INFO_REQUEST_TEMPLATE = (
    "{seller}, bu toʻlov boʻyicha mijoz maʼlumotlarini shu yerga yozib qoldiring, iltimos:\n"
    "1. Mijoz ismi va telefon raqami\n"
    "2. Qaysi xizmat(lar) uchun\n"
    "3. Manba (target, tavsiya va h.k.)\n"
    "4. Davlat boji bormi (boʻlsa — summasi)"
)


def _is_non_crm_seller(
    sender_id: Optional[int], seller_label: Optional[str], card_seller: Optional[str]
) -> bool:
    """CRM bilan ishlamaydigan sotuvchini (masalan, Hasanboy) aniqlaydi."""
    for identifier in (sender_id, seller_label, card_seller):
        if not identifier:
            continue
        member = find_staff(identifier)
        if member and member.slug in _NON_CRM_SELLER_SLUGS:
            return True
    return False


def _find_seller(roster: list, sender_id: Optional[int], card_seller: Optional[str]) -> Any:
    """Avval Telegram ID, topilmasa kartadagi "Sotuvchi" ismi boʻyicha."""
    if sender_id:
        for target in roster:
            if target.telegram_user_id == sender_id:
                return target
    wanted = (card_seller or "").strip().lower()
    if wanted:
        for target in roster:
            name = (target.seller_name or "").strip().lower()
            if name and (name == wanted or wanted in name.split()):
                return target
    return None


async def _won_lead_id(seller: Any, delay: int) -> Optional[int]:
    """Won bitim id yoki None. CRM oʻqilmasa RopFetchError koʻtariladi (xulosa chiqarilmaydi)."""
    amocrm = app_ctx.msg_controller.crm.amocrm
    since = int(time.time()) - _WON_LOOKBACK_SECONDS - delay
    for lead in await RopFetcher(amocrm).fetch_won_leads_since(since, strict=True):
        if lead.get("responsible_user_id") == seller.responsible_user_id:
            return int(lead.get("id") or 0)
    return None


async def check_won_after_payment(
    send: SendFn,
    chat_id: int,
    message_id: int,
    seller_label: str,
    *,
    sender_id: Optional[int],
    card_seller: Optional[str],
    db: Any,
    card: Optional[dict] = None,
    delay: Optional[int] = None,
) -> None:
    """Kutadi, amoCRM ni tekshiradi va kerak boʻlsa sotuvchiga eslatadi. Xato koʻtarmaydi."""
    state_key = f"sales_won_check:{chat_id}:{message_id}"
    try:
        if _is_non_crm_seller(sender_id, seller_label, card_seller):
            ask_delay = _NON_CRM_ASK_DELAY_SECONDS if delay is None else delay
            if ask_delay > 0:
                await asyncio.sleep(ask_delay)
            if is_quiet_hours():
                logger.info(f"[SALES_WON_CHECK] Quiet hours; mijoz maʼlumoti soʻralmadi msg={message_id}")
                await db.set_state(state_key, "quiet_hours")
                return
            ask_msg_id = await send(chat_id, message_id, CLIENT_INFO_REQUEST_TEMPLATE.format(seller=seller_label))
            await save_pending_intake(db, chat_id, message_id, ask_msg_id, seller_label, card)
            await db.set_state(state_key, "asked_client_info")
            return

        if delay is None:
            delay = int(settings.SALES_WON_CHECK_DELAY_SECONDS)
        await asyncio.sleep(delay)
        seller = _find_seller(await load_roster(db.rop), sender_id, card_seller)
        if seller is None:
            logger.warning(f"[SALES_WON_CHECK] Sotuvchi rop_targets da topilmadi msg={message_id}")
            await db.set_state(state_key, "unknown_seller")
            return

        try:
            lead_id = await _won_lead_id(seller, delay)
        except RopFetchError as exc:
            logger.warning(f"[SALES_WON_CHECK] CRM oʻqilmadi, eslatma yuborilmadi: {exc}")
            await db.set_state(state_key, "crm_unavailable")
            return
        if lead_id is not None:
            await db.set_state(state_key, f"won:{lead_id}")
            return
        if is_quiet_hours():
            logger.info(f"[SALES_WON_CHECK] Quiet hours; eslatma yuborilmadi msg={message_id}")
            await db.set_state(state_key, "quiet_hours")
            return

        await send(chat_id, message_id, REMINDER_TEMPLATE.format(seller=seller_label))
        await db.set_state(state_key, "reminded")
    except Exception as exc:
        logger.error(f"[SALES_WON_CHECK] Tekshiruv bajarilmadi: {type(exc).__name__}")


def schedule_won_check(send: SendFn, chat_id: int, message_id: int, seller_label: str, **kwargs: Any) -> None:
    """Tekshiruvni fonda ishga tushiradi; handler kutib qolmaydi."""
    task = asyncio.create_task(check_won_after_payment(send, chat_id, message_id, seller_label, **kwargs))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
