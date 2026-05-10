import logging
import asyncio
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes
import config
from src.services.core.telegram_ai_features import TelegramBotAPI10Client, build_text_article_result

logger = logging.getLogger(__name__)


async def process_message_logic(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    action_parser,
    msg_controller,
    is_business: bool = False,
    msg_business_connection_id: Optional[str] = None,
) -> None:
    """Core logic to process incoming messages (text, photo, voice)."""
    user = update.effective_user
    chat = update.effective_chat
    message = (
        update.message
        if not is_business
        else (update.business_message or update.message)
    )

    if not message:
        return

    user_id = user.id
    username = user.username or "yoq"
    first_name = user.first_name or "Noma'lum"

    # 1. Basic Rate Limiting / Security (Simplified for now)
    # TODO: Migrate rate limiting check here if needed

    # 2. Extract Message Content
    text_content = ""
    if message.text:
        text_content = message.text
    elif message.caption:
        text_content = message.caption

    # 3. Handle Special Input (Photos / Voice)
    # (Simplified: In a full refactor, specific processors would be here)
    if message.photo:
        # Process photo...
        pass
    if message.voice:
        # Process voice...
        pass

    # 4. Get AI Response via Controller
    try:
        # Smart Response Logic for Groups
        chat_type = chat.type
        bot_username = "@jonairobot"
        should_respond = False

        if chat_type == "private":
            should_respond = True
        elif chat_type in ["group", "supergroup"]:
            # Check if mentioned
            if bot_username in text_content:
                should_respond = True
            # Check if it's a reply to the bot
            reply_to = message.reply_to_message
            if (
                reply_to
                and reply_to.from_user
                and reply_to.from_user.username == bot_username.replace("@", "")
            ):
                should_respond = True

        if not should_respond:
            return

        # [NEW] API 10: Show draft status while AI is thinking
        if is_business:
            api_client = TelegramBotAPI10Client(context.bot.token if context and context.bot else config.BOT_TOKEN)
            await api_client.send_message_draft(
                chat_id=chat.id,
                draft_id=message.message_id,
                text="Oisha javob tayyorlamoqda...",
            )

        # Use MessageController for agentic flow
        ai_response = await msg_controller.get_response(
            user_id=user_id,
            user_name=first_name,
            message=text_content,
            context={
                "username": username,
                "is_business": is_business,
                "chat_title": chat.title,
                "is_bot": user.is_bot,
            },
        )

        # 5. Execute Actions and Clean Response
        final_text = await action_parser.parse_and_execute(
            reply_text=ai_response,
            sender_id=user_id,
            sender_name=first_name,
            username=username,
            saved_phone=None,  # To be fetched from DB if needed
            context=context,
            is_business=is_business,
            msg_business_connection_id=msg_business_connection_id,
        )

        # 6. Send Reply
        if final_text:
            if is_business:
                await message.reply_text(
                    final_text,
                    parse_mode="HTML",
                    business_connection_id=msg_business_connection_id,
                )
            else:
                # Bot-to-Bot check: if sender is a bot, add loop safeguard
                if user.is_bot:
                    final_text = f"🤖 [Bot-to-Bot] {final_text}"
                
                await message.reply_text(final_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"[MESSAGE_HANDLER] Error processing message: {e}")

async def handle_guest_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    msg_controller,
    bot_token: str,
) -> None:
    """Handle Guest Mode queries."""
    guest_message = update.guest_message
    if not guest_message:
        return

    query_id = guest_message.guest_query_id
    text = guest_message.text
    user = guest_message.from_user

    logger.info(f"[GUEST] Received query from {user.first_name}: {text}")

    try:
        # Show 'thinking' draft if possible (API 10)
        api_client = TelegramBotAPI10Client(bot_token)
        
        # Get AI Response
        ai_response = await msg_controller.get_response(
            user_id=user.id,
            user_name=user.first_name,
            message=text,
            context={"is_guest": True, "username": user.username},
        )

        # Prepare result
        result = build_text_article_result(ai_response, title="Oisha (AI Assistant)")

        # Answer guest query
        await api_client.answer_guest_query(query_id, result)
        logger.info(f"[GUEST] Answered query {query_id}")

    except Exception as e:
        logger.error(f"[GUEST ERROR] {e}")

async def handle_managed_bot(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle updates when bot is used as a managed bot."""
    managed_bot = update.managed_bot
    if managed_bot:
        logger.info(f"👸 [MANAGED] Bot state update received: {managed_bot.to_dict()}")
        # Here we could update our local settings based on what the user allowed for the managed bot
        # e.g. checking managed_bot.can_reply, managed_bot.can_read_all_group_messages


async def handle_direct_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    action_parser,
    msg_controller,
) -> None:
    """Entry point for direct messages."""
    await process_message_logic(
        update, context, db, action_parser, msg_controller, is_business=False
    )


async def handle_business_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    db,
    action_parser,
    msg_controller,
) -> None:
    """Entry point for business messages."""
    conn_id = (
        update.business_message.business_connection_id
        if update.business_message
        else None
    )
    await process_message_logic(
        update,
        context,
        db,
        action_parser,
        msg_controller,
        is_business=True,
        msg_business_connection_id=conn_id,
    )


async def handle_business_connection(
    update: Update, context: ContextTypes.DEFAULT_TYPE, business_connections: dict
) -> None:
    """Handle business account connection/disconnection."""
    conn = update.business_connection
    user = conn.user
    conn_id = conn.id

    if conn.is_enabled:
        can_reply_val = getattr(conn, "can_reply", getattr(conn, "can_reply_to", False))
        business_connections[conn_id] = {
            "user_id": user.id,
            "user_name": user.first_name,
            "can_reply": can_reply_val,
        }
        logger.info(f"[BUSINESS] New connection: {user.first_name} ({user.id})")
    else:
        business_connections.pop(conn_id, None)
        logger.info(f"[BUSINESS] Connection lost: {user.first_name} ({user.id})")


async def handle_edited_business_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, db, learner
) -> None:
    """Learn from owner-edited messages."""
    msg = update.edited_business_message
    if not msg or not msg.from_user or msg.from_user.id != config.OWNER_ID:
        return

    text = msg.text or msg.caption or ""
    if text:
        client_chat_id = msg.chat.id
        logger.info(f"[LEARNING] Learning from edited message in {client_chat_id}")
        db.log_message(client_chat_id, text, is_ai=True)
        # Trigger learning analysis
        # (Assuming learner is available in context or passed)
        if learner:
            asyncio.create_task(
                learner.analyze_and_learn(
                    client_chat_id, db.get_recent_messages(client_chat_id, limit=6)
                )
            )
