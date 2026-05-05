"""
META (Facebook/Instagram) Webhook Handler
==========================================
Bu skript Flask orqali META platformasidan kelgan kommentlar va DM larni qayta ishlaydi.
AIdan javob oladi va META Graph API orqali javobni yuboradi.

TALABLAR:
1. META Developer akkaunt (developers.facebook.com)
2. Facebook App yaratish
3. Instagram Business akkaunt + Facebook Page ga ulash
4. Bu server VPS da ishlashi va HTTPS bo'lishi kerak (Telegram bot bilan birgalikda)

ISHGA TUSHIRISH:
  pip install flask requests
  python meta_webhook.py

ENVIRONMENT (.env da saqlanadi):
  META_VERIFY_TOKEN=jonbranding_meta_verify_2026
  META_PAGE_ACCESS_TOKEN=<META Developer dan olingan token>
  META_APP_SECRET=<App Secret>
  BOT_TOKEN=<Telegram Bot Token>
"""

import os
import json
import logging
import hashlib
import hmac
import requests  # type: ignore
from flask import Flask, request, jsonify, Response  # type: ignore
import re

# Bot modullari
import src.config as config
from src.database import Database

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
db = Database()


# ==================== YORDAMCHI FUNKSIYALAR ====================


def verify_meta_signature(payload: bytes, signature: str) -> bool:
    """META tomonidan kelgan webhook xabar imzosini tekshiradi."""
    if not config.META_APP_SECRET:
        return True  # Secret yo'q bo'lsa, tekshirmaydi (test uchun)

    expected = (
        "sha256="
        + hmac.new(config.META_APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


def send_ig_reply(recipient_id: str, text: str):
    """Instagram DM yoki kommentga javob yuborish."""
    if not config.META_PAGE_ACCESS_TOKEN:
        logger.warning("[META] PAGE_ACCESS_TOKEN yo'q, javob yuborilmadi")
        return False

    url = "https://graph.facebook.com/v19.0/me/messages"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    headers = {"Content-Type": "application/json"}
    params = {"access_token": config.META_PAGE_ACCESS_TOKEN}

    try:
        resp = requests.post(
            url, json=payload, headers=headers, params=params, timeout=10
        )
        if resp.status_code == 200:
            logger.info(f"[META OK] IG ga javob yuborildi: {str(recipient_id)[:20]}...")
            return True
        else:
            logger.error(f"[META ERROR] {resp.status_code}: {str(resp.text)[:200]}")
            return False
    except Exception as e:
        logger.error(f"[META EXCEPTION] {e}")
        return False


def reply_to_comment(comment_id: str, text: str):
    """Facebook/Instagram kommentga javob (reply)."""
    if not config.META_PAGE_ACCESS_TOKEN:
        return False

    url = f"https://graph.facebook.com/v19.0/{comment_id}/replies"
    params = {"message": text, "access_token": config.META_PAGE_ACCESS_TOKEN}
    try:
        resp = requests.post(url, params=params, timeout=10)
        if resp.status_code == 200:
            logger.info(f"[META OK] Kommentga javob berildi: {comment_id}")
            return True
        else:
            logger.error(f"[META COMMENT ERROR] {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"[META COMMENT EXCEPTION] {e}")
        return False


def get_ai_reply(
    user_id: str, user_name: str, user_message: str, platform: str = "Instagram"
) -> str:
    """Jon Branding systemsidan mukammal AI javob olish."""
    try:
        # User history va context ni yuklash (DB dan)
        from src.agents.orchestrator import AgentOrchestrator
        from src.agents.core import AgentManager
        from src.settings import settings

        manager = AgentManager(settings.AI_KEYS)
        # Barcha agentlarni ro'yxatdan o'tkazish (SupportAgent, SalesAgent va h.k.)
        from src.agents.sales_agent import SalesAgent
        from src.agents.support_agent import SupportAgent

        manager.register_agent(
            SalesAgent("sales", settings.SALES_PROMPT, settings.AI_KEYS)
        )
        manager.register_agent(
            SupportAgent("support", settings.SUPPORT_PROMPT, settings.AI_KEYS)
        )

        orchestrator = AgentOrchestrator(manager)
        intent = orchestrator.determine_intent(user_message)

        # Pass source info in user message or context
        enhanced_message = f"[SOURCE: {platform}] {user_message}"
        reply = orchestrator.get_agent_response(
            intent, int(user_id) if str(user_id).isdigit() else 0, enhanced_message
        )

        return reply

    except Exception as e:
        logger.error(f"[AI ERROR] {e}")
        return "Assalomu alaykum! Xizmatlarimizga qiziqish bildirganingiz uchun rahmat. Tez orada mutaxassisimiz siz bilan batafsil bog'lanadi. 😊"


def notify_crm(source: str, user_name: str, user_id: str, message: str, reply: str):
    """CRM Telegram guruhiga yangi Instagram/FB leadni xabardor qilish."""
    if not config.CRM_GROUP_ID:
        return

    bot_token = os.environ.get("BOT_TOKEN", "")
    if not bot_token:
        return

    # Lead sifatini aniqlash
    quality = "Unknown"
    if "[LEAD_REPORT: QUALITY=sifatli]" in reply.lower():
        quality = "Sifatli 💎"
    elif "[LEAD_REPORT: QUALITY=oddiy]" in reply.lower():
        quality = "Oddiy ✅"

    # Tozalangan xabar
    clean_reply = re.sub(r"\[.*?\]", "", reply).strip()

    crm_msg = (
        f"📱 <b>YANGI {str(source).upper()} LEAD!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Foydalanuvchi:</b> {user_name}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"💎 <b>Sifati:</b> #{quality}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <b>Xabar:</b> <i>{str(message)[:300]}</i>\n"
        f"🤖 <b>AI Javobi:</b> <i>{str(clean_reply)[:300]}</i>\n"
    )

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": config.CRM_GROUP_ID,
            "text": crm_msg,
            "parse_mode": "HTML",
            "message_thread_id": config.CRM_TOPIC_ID,
        }
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"[CRM NOTIFY ERROR] {e}")


# ==================== WEBHOOK ROUTES ====================


@app.route("/meta/webhook", methods=["GET"])
def verify_webhook():
    """META Webhook tekshiruvi (bir marta ro'yxatdan o'tganda chaqiriladi)."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == config.META_VERIFY_TOKEN:
        logger.info("[META] Webhook muvaffaqiyatli tasdiqlandi!")
        return Response(challenge, mimetype="text/plain")
    else:
        logger.warning(f"[META] Webhook tasdiqlash muvaffaqiyatsiz! Token: {token}")
        return "Forbidden", 403


@app.route("/meta/webhook", methods=["POST"])
async def handle_webhook():
    """META dan kelgan barcha eventlarni qayta ishlash."""
    # Imzoni tekshirish
    signature = request.headers.get("X-Hub-Signature-256", "")
    if signature and not verify_meta_signature(request.data, signature):
        logger.warning("[META] Xavfsizlik: Noto'g'ri imzo!")
        return "Unauthorized", 401

    try:
        data = request.json
        if not data:
            return "OK", 200

        logger.info(f"[META RAW] {json.dumps(data)}")

        object_type = data.get("object", "")

        # Instagram yoki Facebook Page xabarlari
        for entry in data.get("entry", []):

            # Xabar turi (Message or Comment)
            changes = entry.get("changes", [])
            if changes:
                # Instagram/FB Comment handling
                change = changes[0].get("value", {})
                sender_id = change.get("from", {}).get("id")
                sender_name = change.get("from", {}).get("username", "User")
                text = change.get("text", "")
                media_url = change.get("media", {}).get("media_url", "")
                comment_id = change.get("id")

                if text:
                    logger.info(f"[META COMMENT] From {sender_name}: {text}")
                    # AI orqali javob olish va Telegramga yo'naltirish logikasi
                    # (Bu yerda inter-process communication yoki db orqali userbotga bildirish yuborish kerak)
                    await db.log_message(
                        sender_id, sender_name, f"COMMENT: {text}", "meta_comment"
                    )
                    return "EVENT_RECEIVED", 200  # Return here as comment is handled

            # Direct Message handling
            messaging = entry.get("messaging", [])
            if messaging:
                event = messaging[0]
                sender_id = event["sender"]["id"]
                message = event.get("message", {})
                text = message.get("text", "")

                if text:
                    if text and sender_id:
                        logger.info(f"[META DM] {sender_id}: {str(text)[:50]}")

                    # AI javob
                    ai_reply = get_ai_reply(
                        str(sender_id),
                        "Foydalanuvchi",
                        str(text),
                        platform="Instagram DM",
                    )

                    # Ma'lumotlarni saqlash (SAVE_INFO tag)
                    import re

                    save_matches = re.finditer(
                        r"\[SAVE_INFO:\s*(.*?)\]", str(ai_reply), re.IGNORECASE
                    )
                    info_updates = {}
                    for m in save_matches:
                        try:
                            parts = m.group(1).split("=", 1)
                            if len(parts) == 2:
                                info_updates[parts[0].strip().lower()] = parts[
                                    1
                                ].strip()
                        except:
                            pass

                    if info_updates:
                        await db.upsert_user(sender_id, "Foydalanuvchi", **info_updates)
                        logger.info(
                            f"[META DB] User updated: {sender_id} -> {info_updates}"
                        )

                    # Tezni tozalash
                    import re

                    clean_reply = re.sub(r"\[.*?\]", "", ai_reply).strip()

                    # Javobni jo'natish
                    send_ig_reply(sender_id, clean_reply)

                    # CRM ni xabardor qilish
                    notify_crm(
                        "Instagram DM", "Foydalanuvchi", sender_id, text, ai_reply
                    )

            # 2. Instagram/Facebook Kommentlar
            for change in entry.get("changes", []):
                value = change.get("value", {})
                comment_text = value.get("text", "")
                comment_id = value.get("id", "")
                from_obj = value.get("from", {})
                commenter_name = from_obj.get("name", "Foydalanuvchi")
                commenter_id = from_obj.get("id", "")

                if comment_text and comment_id:
                    logger.info(
                        f"[META COMMENT] {commenter_name}: {str(comment_text)[:50]}"
                    )

                    # Savol yoki xizmat haqida so'rov bo'lsa javob berish
                    ai_reply = get_ai_reply(
                        str(commenter_id),
                        str(commenter_name),
                        f"{commenter_name} deb komment yozdi: {comment_text}",
                        platform="Instagram Comment",
                    )

                    # Ma'lumotlarni saqlash (SAVE_INFO tag)
                    import re

                    save_matches = re.finditer(
                        r"\[SAVE_INFO:\s*(.*?)\]", str(ai_reply), re.IGNORECASE
                    )
                    info_updates = {}
                    for m in save_matches:
                        try:
                            parts = m.group(1).split("=", 1)
                            if len(parts) == 2:
                                info_updates[parts[0].strip().lower()] = parts[
                                    1
                                ].strip()
                        except:
                            pass

                    if info_updates:
                        await db.upsert_user(
                            commenter_id, commenter_name, **info_updates
                        )
                        logger.info(
                            f"[META DB] Commenter updated: {commenter_id} -> {info_updates}"
                        )

                    # Tezni tozalash
                    import re

                    clean_reply = re.sub(r"\[.*?\]", "", ai_reply).strip()

                    # Kommentga javob
                    reply_to_comment(comment_id, clean_reply)

                    # CRM ni xabardor qilish
                    notify_crm(
                        "Instagram Comment",
                        commenter_name,
                        commenter_id,
                        comment_text,
                        ai_reply,
                    )

        return "EVENT_RECEIVED", 200

    except Exception as e:
        logger.error(f"[META WEBHOOK ERROR] {e}")
        return "OK", 200


@app.route("/health", methods=["GET"])
def health():
    """Server sog'liq tekshiruvi."""
    return jsonify({"status": "ok", "service": "JonBranding META Webhook"})


if __name__ == "__main__":
    port = int(os.environ.get("META_WEBHOOK_PORT", 5050))
    logger.info(f"[META] Webhook server port {port} da ishga tushmoqda...")
    app.run(host="0.0.0.0", port=port, debug=False)
