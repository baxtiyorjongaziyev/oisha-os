"""Payment-confirmation cards in the Kirim topic.

Sotuvchi "TO'LOV TASDIQLASH" kartasini yuborganda:
1. guruhda tabrik,
2. sotuvchiga shaxsiy (DM) tabrik,
3. moliyachini belgilab tasdiq so'rash.

Moliyachi kartaga javoban tasdiqlasa — sotuvchi yana bir bor (DM) tabriklanadi.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import structlog

from src.context import app_ctx
from src.handlers.kirim_shared import (
    build_finance_ask,
    build_individual_congratulation,
    is_approval_reply,
    is_kirim_topic_message,
    is_payment_confirmation_card,
    is_rejection_reply,
    message_text,
    parse_payment_card,
    seller_display_name,
)
from src.settings import settings

logger = structlog.get_logger()

FINANCE_MENTION_ENV = "KIRIM_FINANCE_MENTION"
DEFAULT_FINANCE_MENTION = "@jonbranding_finansist"
CARD_STATE_PREFIX = "kirim_payment"
ASK_STATE_PREFIX = "kirim_payment_ask"


def _card_key(chat_id: int, message_id: int) -> str:
    return f"{CARD_STATE_PREFIX}:{chat_id}:{message_id}"


def _ask_key(chat_id: int, message_id: int) -> str:
    return f"{ASK_STATE_PREFIX}:{chat_id}:{message_id}"


def finance_mention() -> str:
    mention = (os.getenv(FINANCE_MENTION_ENV) or "").strip()
    return mention or DEFAULT_FINANCE_MENTION


def _get_db() -> Any:
    return app_ctx.msg_controller.db if app_ctx.msg_controller else None


async def _send_group(
    event: Any, text: str, reply_to: Optional[int] = None
) -> Optional[int]:
    """Send into the team group: bot first, userbot reply as fallback."""
    if app_ctx.bot_client:
        try:
            sent = await app_ctx.bot_client.send_message(
                settings.TEAM_GROUP_ID,
                text,
                reply_to=reply_to,
                link_preview=False,
            )
            return int(getattr(sent, "id", 0)) or None
        except Exception as exc:
            logger.warning(
                f"[KIRIM] Bot send failed ({type(exc).__name__}); userbot fallback."
            )
    try:
        if reply_to:
            sent = await event.reply(text, link_preview=False)
        else:
            sent = await event.respond(text, link_preview=False)
        return int(getattr(sent, "id", 0)) or None
    except Exception as exc:
        logger.error(f"[KIRIM] Group send failed: {exc}")
        return None


async def _send_individual(
    text: str, *, handle: Optional[str] = None, user_id: Optional[int] = None
) -> bool:
    """Send the personal congratulation; bot first, then the userbot."""
    targets = [target for target in (handle, user_id) if target]
    for client in (app_ctx.bot_client, app_ctx.client):
        if not client:
            continue
        for target in targets:
            try:
                await client.send_message(target, text, link_preview=False)
                return True
            except Exception as exc:
                logger.debug(
                    f"[KIRIM] DM failed target={target}: {type(exc).__name__}"
                )
    return False


async def _build_group_celebration(seller: str, card: Dict[str, Any]) -> str:
    amount_label = card.get("amount_label") or "yangi to'lov"
    try:
        if app_ctx.advisor_agent:
            generated = await app_ctx.advisor_agent.generate_sales_celebration(
                seller, amount_label
            )
            if generated:
                return generated if seller in generated else f"{seller}, {generated}"
    except Exception as exc:
        logger.warning(f"[KIRIM] AI celebration fallback: {type(exc).__name__}")

    project_line = f"{card['project']} loyihasi uchun " if card.get("project") else ""
    return (
        f"{seller}, tabriklaymiz! 🎉\n\n"
        f"{project_line}{amount_label} to'lovi qabul qilindi.\n"
        "Zo'r natija — shu tempda davom etamiz!"
    )


async def _resolve_card_id(db: Any, chat_id: int, reply_to: int) -> Optional[int]:
    """Map a replied message to the original card message id."""
    state = await db.get_state(_card_key(chat_id, reply_to))
    if isinstance(state, dict):
        return reply_to

    card_id = await db.get_state(_ask_key(chat_id, reply_to))
    try:
        return int(card_id) if card_id else None
    except (TypeError, ValueError):
        return None


async def _is_finance_approver(sender: Any, db: Any) -> bool:
    sender_id = getattr(sender, "id", None)
    username = (getattr(sender, "username", None) or "").lower()
    if username and username == finance_mention().lstrip("@").lower():
        return True

    owner_id = getattr(settings, "OWNER_ID", None)
    if sender_id and owner_id and int(sender_id) == int(owner_id):
        return True

    get_user_by_role = getattr(db, "get_user_by_role", None)
    if not callable(get_user_by_role) or not sender_id:
        return False
    for role in ("finance", "moliya", "accountant", "buxgalter"):
        try:
            person = await get_user_by_role(role)
        except Exception:
            person = None
        if not person:
            continue
        try:
            if int(person.get("user_id") or 0) == int(sender_id):
                return True
        except (TypeError, ValueError):
            continue
    return False


async def _celebrate_and_ask(
    event: Any,
    card: Dict[str, Any],
    state: Dict[str, Any],
    card_id: int,
    db: Any,
) -> bool:
    """Group celebration -> personal DM -> finance confirmation request."""
    seller = state["seller_name"]
    celebration = await _build_group_celebration(seller, card)
    await _send_group(event, celebration, reply_to=card_id)

    individual_sent = await _send_individual(
        build_individual_congratulation(card),
        handle=card.get("seller_handle"),
        user_id=state.get("seller_id"),
    )
    if not individual_sent:
        logger.warning(
            f"[KIRIM] Individual DM failed seller={seller}; group celebration only."
        )

    ask_id = await _send_group(
        event,
        build_finance_ask(seller, card.get("amount_label"), finance_mention()),
        reply_to=card_id,
    )
    if ask_id:
        await db.set_state(_ask_key(int(event.chat_id), ask_id), card_id)
    return individual_sent


async def kirim_payment_handler(event: Any) -> None:
    """React to a payment-confirmation card: celebrate (group + DM) and ask finance."""
    if not settings.TEAM_GROUP_ID or not settings.TOPIC_KIRIM_ID:
        return
    if event.chat_id != settings.TEAM_GROUP_ID or getattr(event, "out", False):
        return
    if not is_kirim_topic_message(event.message, settings.TOPIC_KIRIM_ID):
        return

    text = message_text(event.message)
    if not is_payment_confirmation_card(text):
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return

    db = _get_db()
    if not db:
        logger.warning("[KIRIM] DB unavailable; payment celebration skipped.")
        return

    chat_id = int(event.chat_id)
    card_id = int(event.id)
    key = _card_key(chat_id, card_id)
    if await db.get_state(key):
        return

    card = parse_payment_card(text)
    seller = card.get("seller_name") or seller_display_name(sender)
    card["seller_name"] = seller
    state: Dict[str, Any] = {
        "stage": "processing",
        "card_message_id": card_id,
        "seller_id": getattr(sender, "id", None),
        "seller_name": seller,
        "seller_handle": card.get("seller_handle"),
        "amount": card.get("amount"),
        "amount_label": card.get("amount_label"),
        "project": card.get("project"),
    }
    await db.set_state(key, dict(state))

    individual_sent = await _celebrate_and_ask(event, card, state, card_id, db)

    state.update({"stage": "awaiting_approval", "individual_sent": individual_sent})
    await db.set_state(key, dict(state))
    logger.info(
        f"[KIRIM] Payment card handled chat={chat_id} msg={card_id} "
        f"seller={seller} dm={individual_sent}"
    )


def _decide_reply(text: str) -> Optional[bool]:
    """True = tasdiq, False = rad, None = qaror emas."""
    if is_rejection_reply(text):
        return False
    if is_approval_reply(text):
        return True
    return None


async def _publish_decision(event: Any, state: Dict[str, Any], approved: bool) -> None:
    seller = state.get("seller_name") or "Sotuvchi"
    if not approved:
        await _send_group(
            event,
            f"❌ To'lov rad etildi. {seller}, holatni moliyachi bilan aniqlashtiring.",
            reply_to=int(event.id),
        )
        return

    await _send_group(
        event,
        f"✅ To'lov tasdiqlandi. {seller}, yana bir bor tabriklaymiz! 🎉",
        reply_to=int(event.id),
    )
    await _send_individual(
        build_individual_congratulation(state, approved=True),
        handle=state.get("seller_handle"),
        user_id=state.get("seller_id"),
    )


async def kirim_payment_reply_handler(event: Any) -> None:
    """Finance reply to the card/ask message: approve -> second celebration."""
    if not settings.TEAM_GROUP_ID or getattr(event, "out", False):
        return
    if event.chat_id != settings.TEAM_GROUP_ID:
        return

    reply_to = getattr(event.message, "reply_to_msg_id", None)
    text = message_text(event.message)
    if not reply_to or not text:
        return

    approved = _decide_reply(text)
    if approved is None:
        return

    db = _get_db()
    if not db:
        return

    chat_id = int(event.chat_id)
    card_id = await _resolve_card_id(db, chat_id, int(reply_to))
    if not card_id:
        return

    key = _card_key(chat_id, card_id)
    state = await db.get_state(key)
    if not isinstance(state, dict) or state.get("stage") != "awaiting_approval":
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return
    if state.get("seller_id") and getattr(sender, "id", None) == state["seller_id"]:
        return
    if not await _is_finance_approver(sender, db):
        return

    state.update(
        {
            "stage": "approved" if approved else "rejected",
            "decided_by": getattr(sender, "id", None),
        }
    )
    await db.set_state(key, dict(state))
    await _publish_decision(event, state, approved)
    logger.info(
        f"[KIRIM] Payment {'approved' if approved else 'rejected'} "
        f"chat={chat_id} card={card_id} seller={state.get('seller_name')}"
    )
