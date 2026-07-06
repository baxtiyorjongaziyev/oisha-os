import os
import hmac

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from src.context import app_ctx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/mcp", tags=["telegram_mcp"])

class SendMessageRequest(BaseModel):
    user_id: str
    text: str

def _require_internal_secret(request: Request) -> None:
    expected = (os.environ.get("OISHA_API_SECRET") or "").strip()
    if not expected:
        return
    auth = request.headers.get("Authorization", "")
    if not hmac.compare_digest(auth, f"Bearer {expected}"):
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.get("/dialogs", dependencies=[Depends(_require_internal_secret)])
async def get_recent_dialogs(limit: int = Query(10, le=50)):
    if not app_ctx.client:
        raise HTTPException(status_code=503, detail="Telegram client not initialized")
    try:
        dialogs = await app_ctx.client.get_dialogs(limit=limit)
        result = []
        for d in dialogs:
            result.append({
                "id": d.id,
                "name": d.name,
                "title": getattr(d, 'title', d.name),
                "is_user": d.is_user,
                "is_group": d.is_group,
                "is_channel": d.is_channel,
                "unread_count": d.unread_count,
            })
        return {"dialogs": result}
    except Exception as e:
        logger.error(f"[MCP API] Failed to fetch dialogs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/messages/{chat_id}", dependencies=[Depends(_require_internal_secret)])
async def get_chat_history(chat_id: str, limit: int = Query(20, le=100)):
    if not app_ctx.client:
        raise HTTPException(status_code=503, detail="Telegram client not initialized")
    try:
        # Resolve chat_id to int if possible, otherwise it might be a username string
        target_id = int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id
        messages = await app_ctx.client.get_messages(target_id, limit=limit)
        result = []
        for m in messages:
            if not m.text and not getattr(m, 'media', None):
                continue
            
            sender = await m.get_sender()
            sender_name = getattr(sender, 'first_name', '') or getattr(sender, 'title', 'Unknown')
            
            result.append({
                "id": m.id,
                "text": m.text or "[Media/Non-text message]",
                "sender_id": m.sender_id,
                "sender_name": sender_name,
                "is_out": getattr(m, 'out', False),
                "date": m.date.isoformat() if m.date else None
            })
        return {"messages": result}
    except Exception as e:
        logger.error(f"[MCP API] Failed to fetch messages for {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send_message", dependencies=[Depends(_require_internal_secret)])
async def send_telegram_message(request: SendMessageRequest):
    if not app_ctx.client:
        raise HTTPException(status_code=503, detail="Telegram client not initialized")
    try:
        target_id = int(request.user_id) if request.user_id.lstrip("-").isdigit() else request.user_id
        await app_ctx.client.send_message(target_id, request.text)
        return {"status": "success", "user_id": request.user_id}
    except Exception as e:
        logger.error(f"[MCP API] Failed to send message to {request.user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analyze_private_chats", dependencies=[Depends(_require_internal_secret)])
async def analyze_private_chats():
    from telethon.tl.functions.messages import GetDialogFiltersRequest
    from telethon.tl.types import DialogFilter, PeerUser
    from datetime import datetime, timezone
    if not app_ctx.client:
        raise HTTPException(status_code=503, detail="Telegram client not initialized")
    try:
        # 1. Fetch dialog filters to identify the "Oila" folder
        try:
            filters = await app_ctx.client(GetDialogFiltersRequest())
        except Exception as fe:
            logger.warning(f"[MCP API] Failed to fetch filters: {fe}")
            filters = []
            
        family_user_ids = set()
        
        filters_list = getattr(filters, 'filters', []) if hasattr(filters, 'filters') else (filters if isinstance(filters, list) else [])
        for f in filters_list:
            if isinstance(f, DialogFilter):
                title_lower = str(f.title).lower()
                # Check for oila, family, shaxsiy, relative
                if any(x in title_lower for x in ["oila", "family", "shaxsiy", "rodn"]):
                    for peer in f.include_peers:
                        if isinstance(peer, PeerUser):
                            family_user_ids.add(peer.user_id)
        
        # 2. Get dialogs
        dialogs = await app_ctx.client.get_dialogs(limit=100)
        private_chats = []
        
        for d in dialogs:
            if d.is_user and not d.is_group and not d.is_channel:
                if not d.entity:
                    continue
                real_id = d.entity.id
                if real_id in family_user_ids:
                    logger.info(f"Excluding family member: {d.name} (ID: {real_id})")
                    continue
                # Skip bot or itself
                if real_id == 150074828 or getattr(d.entity, 'bot', False):
                    continue
                
                private_chats.append(d)
        
        # 3. For each private chat, fetch messages since 2025-01-01
        start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = []
        
        for chat in private_chats[:25]:  # Fetch up to 25 chats
            if not chat.entity:
                continue
            messages = []
            try:
                async for m in app_ctx.client.iter_messages(chat.entity, limit=40):
                    if m.date < start_date:
                        break
                    if m.text:
                        messages.append({
                            "sender": "Me" if m.out else chat.name,
                            "text": str(m.text),
                            "date": m.date.isoformat()
                        })
            except Exception as me:
                logger.warning(f"[MCP API] Failed to fetch messages for {chat.name}: {me}")
                continue
                
            if messages:
                result.append({
                    "chat_id": chat.entity.id,
                    "name": chat.name,
                    "username": getattr(chat.entity, 'username', None),
                    "messages": messages
                })
                
        return {
            "family_folder_users_excluded": list(family_user_ids),
            "chats": result
        }
    except Exception as e:
        logger.error(f"[MCP API] Failed to analyze private chats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

