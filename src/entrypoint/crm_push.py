import inspect
import logging
import random
from typing import Any, Dict, Optional
from telethon import TelegramClient, functions, types

from src.context import app_ctx
from src.settings import settings

logger = logging.getLogger("OishaCRMPush")

async def push_block_to_amocrm(user_id: int, phone: str, block_text: str) -> None:
    """Callback for SessionManager to flush a block of messages.

    Args:
        user_id: The Telegram user ID
        phone: User's phone number
        block_text: The message block to push to AmoCRM
    """
    if not app_ctx.msg_controller:
        return
    try:
        if not phone:
            # Try to get phone from DB
            db_user = await app_ctx.msg_controller.db.get_user(user_id)
            if db_user and db_user.get("phone"):
                phone = db_user.get("phone")
        
        if not phone:
            logger.warning(f"[ENTERPRISE SYNC] Cannot push block for {user_id}: No phone number.")
            return

        contact_result = app_ctx.msg_controller.crm.amocrm.get_contact_by_phone(phone)
        contact = (
            await contact_result
            if inspect.isawaitable(contact_result)
            else contact_result
        )
        if contact:
            note_result = app_ctx.msg_controller.crm.amocrm.add_contact_note(
                contact["id"], block_text
            )
            if inspect.isawaitable(note_result):
                await note_result
            logger.info(f"[ENTERPRISE SYNC] Block pushed for {user_id}")
        else:
            logger.warning(
                f"[ENTERPRISE SYNC] Contact not found for {user_id} ({phone})"
            )
    except Exception as e:
        logger.error(f"[ENTERPRISE SYNC ERROR] Push failed: {e}")


# Global Search State (Memory-based for simplicity)
last_deep_search_time = 0


async def global_phone_lookup(phone: str, client: Optional[TelegramClient] = None) -> Optional[Dict[str, Any]]:
    """Butun Telegramdan raqam orqali qidirib topish (Xavfsiz rejimda)."""
    # Raqamni tozalash
    client = client or getattr(app_ctx, "client", None)
    if not client:
        return None

    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    if not clean_phone.startswith("998"):
        # Agar O'zbekiston raqami bo'lsa va + bo'lmasa, qo'shib qo'yamiz
        if len(clean_phone) == 9:
            clean_phone = "998" + clean_phone

    try:
        # 1. Vaqtinchalik kontakt yaratish
        contact = types.InputPhoneContact(
            client_id=random.randrange(-(2**63), 2**63),
            phone=clean_phone,
            first_name="Oisha Search",
            last_name="",
        )

        # 2. Import so'rovi
        result = await client(
            functions.contacts.ImportContactsRequest(contacts=[contact])
        )

        if result.users:
            user = result.users[0]
            user_data = {
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }

            # 3. Bazaga saqlab qo'yamiz (Keyingi safar tekin bo'lishi uchun)
            if app_ctx.msg_controller:
                await app_ctx.msg_controller.db.upsert_user(
                    user_id=user.id,
                    first_name=user.first_name,
                    username=user.username,
                    phone=clean_phone,
                    last_name=user.last_name,
                )

            # 4. Kontaktni darhol o'chirib tashlaymiz
            try:
                await client(functions.contacts.DeleteContactsRequest(id=[user.id]))
            except Exception as exc:
                logger.debug("[GLOBAL SEARCH] Contact delete failed: %s", exc)
            return user_data

        return None
    except Exception as e:
        logger.error(f"[GLOBAL SEARCH ERROR] {e}")
        return None


async def notify_admin(message: str, client: TelegramClient) -> None:
    """Admin (baxtiyorjon) ga muhim xabar yuborish.

    Args:
        message: The message text to send
        client: The Telethon client instance
    """
    try:
        await client.send_message("me", message)
    except Exception as e:
        logger.error(f"[NOTIFY ERROR] {e}")


async def sync_single_lead(event):
    """Single leadni avtomatik tahlil qilish va qo'shish — wrapper for backward compat."""
    from src.handlers.lead_sync import sync_single_lead as _impl
    await _impl(
        event,
        client=getattr(app_ctx, "client", None),
        lead_scraper=getattr(app_ctx, "lead_scraper", None),
        msg_controller=app_ctx.msg_controller,
        TN5_GROUP_ID=getattr(settings, "TN5_GROUP_ID", None),
    )


async def run_autonomous_advice(chat_id, sender_name, message_text):
    """Background worker to provide strategic advice — wrapper for backward compat."""
    from src.handlers.shadow_advisor import run_autonomous_advice as _impl
    await _impl(
        chat_id,
        sender_name,
        message_text,
        advisor_agent=getattr(app_ctx, "advisor_agent", None),
        client=getattr(app_ctx, "client", None),
        action_parser=getattr(app_ctx, "action_parser", None),
        evolution_scheduler=getattr(app_ctx, "evolution_scheduler", None),
    )

