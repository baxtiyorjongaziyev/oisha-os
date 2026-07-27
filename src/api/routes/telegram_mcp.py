import hmac
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.context import app_ctx
from src.api.rbac import Permission, require_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/mcp", tags=["telegram_mcp"])


class SendMessageRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=4096)


def _require_internal_secret(request: Request) -> None:
    expected = (os.environ.get("OISHA_API_SECRET") or "").strip()
    if not expected:
        logger.error("[MCP API] OISHA_API_SECRET is missing; denying internal access")
        raise HTTPException(
            status_code=503, detail="Internal API authentication is not configured"
        )

    auth = request.headers.get("Authorization", "")
    if not hmac.compare_digest(auth, f"Bearer {expected}"):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get(
    "/dialogs",
    dependencies=[
        Depends(_require_internal_secret),
        require_permissions(Permission.MCP_READ),
    ],
)
async def get_recent_dialogs(limit: int = Query(10, ge=1, le=50)):
    if not app_ctx.client:
        raise HTTPException(status_code=503, detail="Telegram client not initialized")
    try:
        dialogs = await app_ctx.client.get_dialogs(limit=limit)
        result = []
        for dialog in dialogs:
            result.append(
                {
                    "id": dialog.id,
                    "name": dialog.name,
                    "title": getattr(dialog, "title", dialog.name),
                    "is_user": dialog.is_user,
                    "is_group": dialog.is_group,
                    "is_channel": dialog.is_channel,
                    "unread_count": dialog.unread_count,
                }
            )
        return {"dialogs": result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[MCP API] Failed to fetch dialogs: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Telegram dialogs unavailable") from exc


@router.get(
    "/messages/{chat_id}",
    dependencies=[
        Depends(_require_internal_secret),
        require_permissions(Permission.MCP_READ),
    ],
)
async def get_chat_history(chat_id: str, limit: int = Query(20, ge=1, le=100)):
    if not app_ctx.client:
        raise HTTPException(status_code=503, detail="Telegram client not initialized")
    try:
        target_id = int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id
        messages = await app_ctx.client.get_messages(target_id, limit=limit)
        result = []
        for message in messages:
            if not message.text and not getattr(message, "media", None):
                continue

            sender = await message.get_sender()
            sender_name = getattr(sender, "first_name", "") or getattr(
                sender, "title", "Unknown"
            )
            result.append(
                {
                    "id": message.id,
                    "text": message.text or "[Media/Non-text message]",
                    "sender_id": message.sender_id,
                    "sender_name": sender_name,
                    "is_out": getattr(message, "out", False),
                    "date": message.date.isoformat() if message.date else None,
                }
            )
        return {"messages": result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "[MCP API] Failed to fetch messages for %s: %s",
            chat_id,
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="Telegram history unavailable") from exc


@router.post(
    "/send_message",
    dependencies=[
        Depends(_require_internal_secret),
        require_permissions(Permission.MCP_WRITE),
    ],
)
async def send_telegram_message(request: SendMessageRequest):
    if not app_ctx.client:
        raise HTTPException(status_code=503, detail="Telegram client not initialized")
    try:
        target_id = (
            int(request.user_id)
            if request.user_id.lstrip("-").isdigit()
            else request.user_id
        )
        await app_ctx.client.send_message(target_id, request.text)
        return {"status": "success", "user_id": request.user_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "[MCP API] Failed to send message to %s: %s",
            request.user_id,
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="Telegram send failed") from exc


@router.get(
    "/analyze_private_chats",
    dependencies=[
        Depends(_require_internal_secret),
        require_permissions(Permission.MCP_READ),
    ],
)
async def analyze_private_chats():
    from telethon.tl.functions.messages import GetDialogFiltersRequest
    from telethon.tl.types import DialogFilter, PeerUser

    if not app_ctx.client:
        raise HTTPException(status_code=503, detail="Telegram client not initialized")
    try:
        try:
            filters = await app_ctx.client(GetDialogFiltersRequest())
        except Exception as exc:
            logger.warning(
                "[MCP API] Failed to fetch filters: %s", type(exc).__name__
            )
            filters = []

        family_user_ids = set()
        filters_list = (
            getattr(filters, "filters", [])
            if hasattr(filters, "filters")
            else (filters if isinstance(filters, list) else [])
        )
        for dialog_filter in filters_list:
            if isinstance(dialog_filter, DialogFilter):
                title_lower = str(dialog_filter.title).lower()
                if any(
                    keyword in title_lower
                    for keyword in ["oila", "family", "shaxsiy", "rodn"]
                ):
                    for peer in dialog_filter.include_peers:
                        if isinstance(peer, PeerUser):
                            family_user_ids.add(peer.user_id)

        dialogs = await app_ctx.client.get_dialogs(limit=100)
        private_chats = []
        for dialog in dialogs:
            if dialog.is_user and not dialog.is_group and not dialog.is_channel:
                if not dialog.entity:
                    continue
                real_id = dialog.entity.id
                if real_id in family_user_ids:
                    logger.info("Excluding family member ID: %s", real_id)
                    continue
                if real_id == 150074828 or getattr(dialog.entity, "bot", False):
                    continue
                private_chats.append(dialog)

        start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = []
        for chat in private_chats[:25]:
            if not chat.entity:
                continue
            messages = []
            try:
                async for message in app_ctx.client.iter_messages(chat.entity, limit=40):
                    if message.date < start_date:
                        break
                    if message.text:
                        messages.append(
                            {
                                "sender": "Me" if message.out else chat.name,
                                "text": str(message.text),
                                "date": message.date.isoformat(),
                            }
                        )
            except Exception as exc:
                logger.warning(
                    "[MCP API] Failed to fetch messages for chat %s: %s",
                    chat.entity.id,
                    type(exc).__name__,
                )
                continue

            if messages:
                result.append(
                    {
                        "chat_id": chat.entity.id,
                        "name": chat.name,
                        "username": getattr(chat.entity, "username", None),
                        "messages": messages,
                    }
                )

        return {
            "family_folder_users_excluded": list(family_user_ids),
            "chats": result,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[MCP API] Private chat analysis failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Private chat analysis unavailable") from exc
