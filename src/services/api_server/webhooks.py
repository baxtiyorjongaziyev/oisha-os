"""
Webhook endpoints for AmoCRM and Telegram in Oisha-OS API.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Request, HTTPException, Query, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.context import app_ctx
from src.settings import settings
from src.services.api_server.helpers import (
    _get_amocrm_instance,
    _get_db_instance,
    mark_heartbeat,
    add_activity,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])
limiter = Limiter(key_func=get_remote_address)

async def process_telegram_ai_update(update: Dict[str, Any]):
    """Central dispatcher for Bot API 10.0 AI updates."""
    from src.services.core.telegram.telegram_ai_features import (
        TelegramBotAPI10Client,
        classify_update as classify_bot_api_update,
        extract_guest_message_context,
        build_text_article_result,
    )

    update_type = classify_bot_api_update(update)
    logger.info("[TG-AI] update_type=%s", update_type)

    if update_type == "guest_message":
        guest_ctx = extract_guest_message_context(update)
        if not guest_ctx:
            return {"handled": False, "reason": "no_guest_context"}

        token = os.environ.get("BOT_TOKEN") or settings.BOT_TOKEN.get_secret_value()
        response_text = ""
        try:
            from src.openclaw_bridge import handle_openclaw_message
            response_text = await handle_openclaw_message(
                text=guest_ctx.guest_text,
                sender=guest_ctx.caller_user,
                sender_id=str(guest_ctx.caller_user),
                channel="telegram_business",
            )
        except Exception as exc:
            logger.error("[TG-AI] Agent error: %s", exc)

        if not response_text:
            response_text = "Oisha savolni qabul qildi, lekin hozir aniq javob shakllanmadi."

        result = build_text_article_result(
            response_text,
            title="Oisha javobi",
            description="Jon Branding AI agent javobi",
        )
        client = TelegramBotAPI10Client(token)
        sent = await client.answer_guest_query(guest_ctx.guest_query_id, result)
        return {"ok": True, "handled": True, "update_type": "guest_message", "sent_guest_message": sent}

    return {"handled": False, "reason": f"unhandled_update_type:{update_type}"}


@router.post("/webhook/telegram-ai")
@limiter.limit("60/minute")
async def telegram_ai_webhook(request: Request):
    """HTTPS ingress for Bot API 10.0 AI updates."""
    expected_secret = _secret_setting_text(settings.TELEGRAM_WEBHOOK_SECRET)
    received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected_secret:
        raise HTTPException(status_code=503, detail="TELEGRAM_WEBHOOK_SECRET is required")
    if not hmac.compare_digest(expected_secret, received_secret):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")

    update = await request.json()
    if not isinstance(update, dict):
        raise HTTPException(status_code=400, detail="Invalid Telegram update payload")
    return await process_telegram_ai_update(update)


@router.post("/webhook/telegram")
@limiter.limit("60/minute")
async def telegram_webhook(request: Request):
    """Legacy webhook alias."""
    return await telegram_ai_webhook(request)


# =====================================================================
# AmoCRM Chat Integration (Wazzup Alternative)
# =====================================================================

@router.post("/webhook/amocrm_chat")
@limiter.limit("60/minute")
async def amocrm_chat_webhook(request: Request):
    """Retired unsigned alias; the canonical amoJo route verifies HMAC."""
    return JSONResponse(
        status_code=410,
        content={"status": "retired", "endpoint": "/webhook/amocrm/chats"},
    )


@router.post("/webhook/amocrm_lead_created")
@limiter.limit("60/minute")
async def amocrm_lead_created_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    secret: Optional[str] = Query(default=None),
):
    """Receive lead[add] webhooks from AmoCRM to trigger Voice Agent.

    Requires a shared secret (AMOCRM_WEBHOOK_SECRET) as a query param since
    AmoCRM webhooks carry no signature — and stays fully disabled unless
    ENABLE_VOICE_AGENT=True, regardless of whether VAPI_API_KEY is set.
    """
    if not settings.ENABLE_VOICE_AGENT:
        return JSONResponse(status_code=404, content={"status": "disabled"})

    expected_secret = settings.AMOCRM_WEBHOOK_SECRET.get_secret_value() if settings.AMOCRM_WEBHOOK_SECRET else ""
    if not expected_secret or not secret or not hmac.compare_digest(secret.encode("utf-8"), expected_secret.encode("utf-8")):
        return JSONResponse(status_code=401, content={"status": "unauthorized"})

    try:
        from src.services.core.voice_agent import trigger_voice_agent
        form_data = await request.form()

        # Parse AmoCRM structure: leads[add][0][name], etc.
        lead_id = form_data.get("leads[add][0][id]")
        if not lead_id:
            return JSONResponse(status_code=400, content={"status": "ignored", "message": "Not a lead addition"})

        # Idempotency: skip if this lead_id already triggered a call.
        idempotency_key = f"voice_call_triggered:{lead_id}"
        db = get_db()
        if await db.kv.get_state(idempotency_key):
            return JSONResponse(content={"status": "ignored", "message": "Already processed"})

        lead_name = form_data.get("leads[add][0][name]", f"Lead {lead_id}")

        # This is a naive extraction. In reality, we'd need to extract from custom fields (CFs)
        # However, AmoCRM webhooks usually send custom fields as array indexes.
        # For the stub, we just try to find something that looks like a phone.
        phone_number = None
        for key, value in form_data.items():
            if "custom_fields" in key and "values" in key and "value" in key:
                if str(value).replace("+", "").isdigit() and len(str(value)) > 8:
                    phone_number = str(value)
                    break

        if not phone_number:
            await db.kv.set_state(idempotency_key, True)
            return JSONResponse(content={"status": "ignored", "message": "No phone number found"})

        # Mark processed now so a retried webhook delivery can't queue a second
        # approval request for the same lead.
        await db.kv.set_state(idempotency_key, True)

        # Owner approval gate — do NOT call the Vapi API directly from the
        # webhook. Stash the pending call and ask the owner to approve it.
        approval_key = f"voice_call_pending:{lead_id}"
        await db.kv.set_state(approval_key, {
            "lead_id": lead_id,
            "lead_name": lead_name,
            "phone_number": phone_number,
        })

        owner_id = int(getattr(settings, "OWNER_ID", 0) or 0)
        if owner_id:
            if app_ctx.outgoing_messages is None:
                app_ctx.outgoing_messages = asyncio.Queue()
            await app_ctx.outgoing_messages.put({
                "chat_id": owner_id,
                "text": (
                    f"🎙 Voice Agent tasdiq so'raladi\n\n"
                    f"Lead: {lead_name} (ID: {lead_id})\n"
                    f"Telefon: {phone_number}\n\n"
                    f"Tasdiqlash uchun: /voice_approve {lead_id}\n"
                    f"Rad etish uchun: /voice_reject {lead_id}"
                ),
            })

        return JSONResponse(content={"status": "pending_approval", "message": "Awaiting owner approval"})
    except Exception as e:
        logger.error(f"AmoCRM Lead Created Webhook error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "message": "Internal server error"})


async def approve_voice_call(lead_id: str) -> bool:
    """Owner tasdiqlagach chaqiriladi (masalan /voice_approve buyrug'idan).

    Pending call yozuvini o'qiydi, mavjud bo'lsa Vapi.ai chaqiruvini navbatga
    qo'yadi va pending yozuvni tozalaydi. Ikki marta tasdiqlash xavfsiz —
    yozuv topilmasa False qaytaradi.
    """
    if not settings.ENABLE_VOICE_AGENT:
        return False

    from src.services.core.voice_agent import trigger_voice_agent

    db = get_db()
    approval_key = f"voice_call_pending:{lead_id}"
    pending = await db.kv.get_state(approval_key)
    if not pending:
        return False

    await db.kv.set_state(approval_key, None)
    await trigger_voice_agent(
        lead_name=pending["lead_name"],
        phone_number=pending["phone_number"],
        context=f"AmoCRM Lead ID: {lead_id} (owner-approved)",
    )
    return True


async def reject_voice_call(lead_id: str) -> bool:
    """Owner rad etganda chaqiriladi. Pending yozuvni tozalaydi."""
    db = get_db()
    approval_key = f"voice_call_pending:{lead_id}"
    pending = await db.kv.get_state(approval_key)
    if not pending:
        return False
    await db.kv.set_state(approval_key, None)
    return True


@router.post("/webhook/amocrm_notes")
@limiter.limit("60/minute")
async def amocrm_notes_webhook(request: Request):
    """Receive note[add] webhooks from AmoCRM to send Telegram messages natively."""
    try:
        form = await request.form()
        notes = {}
        for key, value in form.multi_items():
            if key.startswith("notes[add]["):
                parts = key.replace("notes[add][", "").split("][")
                if len(parts) >= 2:
                    idx = parts[0]
                    field = parts[-1].rstrip("]")
                    if idx not in notes:
                        notes[idx] = {}
                    notes[idx][field] = value
                    
        for idx, note_data in notes.items():
            text = note_data.get("text", "")
            lead_id_str = note_data.get("element_id")
            
            # Agar menejer "TG: salom" deb yozsa
            if text.lower().startswith("tg:") and lead_id_str:
                clean_text = text[3:].strip()
                lead_id = int(lead_id_str)
                
                from src.services.core.crm.amocrm_sync import AmoCRMSync
                amocrm = AmoCRMSync()
                phone = amocrm.get_lead_phone(lead_id)
                
                if phone:
                    if app_ctx.outgoing_messages is None:
                        app_ctx.outgoing_messages = asyncio.Queue()
                    await app_ctx.outgoing_messages.put({
                        "chat_id": phone,
                        "text": clean_text
                    })
                    logger.info(f"[NATIVE AMOCRM CHAT] Sent to {phone}: {clean_text}")
                    
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[AMOCRM NOTES WEBHOOK ERROR] {e}")
        return {"status": "error"}
