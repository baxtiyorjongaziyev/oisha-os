import asyncio
import logging
from typing import Any, Dict
from fastapi import APIRouter, Request

from src.context import app_ctx

logger = logging.getLogger(__name__)
router = APIRouter(tags=["telegram_extension"])


async def telegram_extension_history(phone: str) -> Dict[str, Any]:
    """Fetch chat history (via AmoCRM notes) for a given phone number."""
    try:
        from src.services.core.crm.amocrm_sync import AmoCRMSync
        amocrm = AmoCRMSync()
        
        # 1. Mijozni topish
        lead = amocrm.find_active_lead_by_phone(phone)
        if not lead:
            contact = amocrm.get_contact_by_phone(phone)
            if not contact:
                return {"success": False, "error": "Mijoz topilmadi"}
            leads = amocrm.get_active_leads_for_contact(contact["id"])
            if leads:
                lead = leads[0]
            else:
                return {"success": False, "error": "Mijozning faol bitimi yo'q"}
                
        lead_id = lead["id"]
        
        # 2. Mijoz izohlarini (Notes) olish
        notes = await amocrm.get_lead_notes(lead_id)
        
        messages = []
        for note in notes:
            text = note.get("params", {}).get("text", "")
            if not text:
                continue
            is_outbound = "Menejer:" in text or "TG:" in text or "Oisha:" in text or note.get("created_by") != 0
            clean_text = text.replace("TG: ", "").replace("Menejer: ", "")
            messages.append({
                "text": clean_text,
                "outbound": is_outbound,
                "created_at": note.get("created_at")
            })
            
        messages.sort(key=lambda x: x["created_at"])
        return {
            "success": True, 
            "messages": messages,
            "chatId": phone,
            "leadId": lead_id
        }
    except Exception as e:
        logger.error(f"[TELEGRAM EXT HISTORY] {e}")
        return {"success": False, "error": "Telegram history request failed"}


@router.post("/api/telegram/extension/send")
async def telegram_extension_send(request: Request) -> Dict[str, Any]:
    """Send a message to a client via Telegram and log it in AmoCRM."""
    try:
        data = await request.json()
        chat_id = data.get("chat_id")
        text = data.get("text")
        
        if not chat_id or not text:
            return {"success": False, "error": "chat_id and text required"}
            
        target = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
        sent = False
        
        # A) Telethon Userbot orqali
        if getattr(app_ctx, "client", None):
            try:
                await app_ctx.client.send_message(target, text)
                sent = True
                logger.info(f"[TELEGRAM EXT] Sent via Userbot to {target}")
            except Exception as ex:
                logger.warning(f"[TELEGRAM EXT] Userbot send failed: {ex}")
                
        # B) Bot runtime orqali fallback
        if not sent and getattr(app_ctx, "bot_runtime", None):
            try:
                await app_ctx.bot_runtime.send_message(target, text)
                sent = True
                logger.info(f"[TELEGRAM EXT] Sent via Bot to {target}")
            except Exception as ex:
                logger.warning(f"[TELEGRAM EXT] Bot send failed: {ex}")
                
        # C) Queue fallback
        if not sent:
            if app_ctx.outgoing_messages is None:
                app_ctx.outgoing_messages = asyncio.Queue()
            await app_ctx.outgoing_messages.put({"chat_id": chat_id, "text": text})
        
        # 2. AmoCRM ga Note qilib yozib qo'yish
        try:
            from src.services.core.crm.amocrm_sync import AmoCRMSync
            amocrm = AmoCRMSync()
            phone_clean = str(chat_id).replace("+", "")
            lead = amocrm.find_active_lead_by_phone(phone_clean)
            if lead:
                await amocrm.add_lead_note(lead["id"], f"Menejer: {text}")
        except Exception as ex:
            logger.warning(f"[TELEGRAM EXT] Note logging failed: {ex}")
            
        return {"success": True, "sent": sent}
    except Exception as e:
        logger.error(f"[TELEGRAM EXT] Error: {e}")
        return {"success": False, "error": "Telegram send request failed"}
