import logging
from telegram import Update
from telegram.ext import ContextTypes
import config

logger = logging.getLogger(__name__)


async def task_conf_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, db
) -> None:
    """Handle task confirmation callbacks."""
    query = update.callback_query
    await query.answer()
    data = query.data
    # task_confirm_12 or task_reject_12
    if "confirm" in data:
        task_id = int(data.split("_")[-1])
        db.complete_task(task_id)
        await query.edit_message_text(f"✅ Vazifa #{task_id} tasdiqlandi!")
    elif "reject" in data:
        await query.edit_message_text("❌ Vazifa rad etildi.")


async def strat_conf_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle strategy confirmation callbacks."""
    query = update.callback_query
    await query.answer("Strategiya qabul qilindi!")
    await query.edit_message_text("🚀 Strategiya amalga oshirilmoqda...")


async def handle_inline_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle inline search queries (e.g. for portfolio)."""
    # Simplified version from userbot.py
    from telegram import InlineQueryResultArticle, InputTextMessageContent

    query = update.inline_query.query
    if not query:
        return

    results = [
        InlineQueryResultArticle(
            id="1",
            title="Jon Branding Portfolio",
            input_message_content=InputTextMessageContent(
                f"Bizning ishlarimizni ko'ring: {config.WEBAPP_URL}"
            ),
        )
    ]
    await update.inline_query.answer(results)
