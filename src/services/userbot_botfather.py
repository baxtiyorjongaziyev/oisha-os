import logging
from dotenv import load_dotenv
load_dotenv()
import asyncio
import os
import sys
from functools import partial
from datetime import datetime, timezone

# Telegram & AI
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    filters,
    PreCheckoutQueryHandler,
    BusinessConnectionHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ContextTypes
)
from google import genai
from google.genai import types

# Project Modules
from settings import settings, logger
from database import Database
from controllers.message_controller import MessageController
from services.action_parser import ActionParser
from handlers import commands, messages, payments, callbacks
from invoicing import InvoiceGenerator
import tts_engine
import learning_engine
from amocrm_sync import AmoCRMSync

# Initialize Global Components
db = Database()
amocrm = AmoCRMSync(
    settings.AMOCRM_SUBDOMAIN,
    settings.AMOCRM_CLIENT_ID,
    settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
    settings.AMOCRM_REDIRECT_URL
)
invoicer = InvoiceGenerator()
tts = tts_engine.TTSEngine(voice="uz-UZ-MadinaNeural")
msg_controller = MessageController(api_keys={"gemini": settings.GEMINI_API_KEY.get_secret_value()}, db=db)
learner = learning_engine.LearningEngine({"gemini": settings.GEMINI_API_KEY.get_secret_value()}, db)
action_parser = ActionParser(
    db=db,
    gcontacts=msg_controller.google.contacts,
    gcalendar=msg_controller.google.calendar,
    invoicer=invoicer,
    amocrm=amocrm,
    config=settings # Using settings instead of config
)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and notify owner if critical."""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Main entry point to start the bot."""
    logger.info("oisha_starting", version="2.0.0_agentic", platform="cloud_run_ready")
    
    app = ApplicationBuilder().token(settings.BOT_TOKEN.get_secret_value()).build()
    
    # Inject application into controller's executor
    msg_controller.set_bot_app(app)
    action_parser.bot_app = app
    
    # Storage for business connections (needed by handler)
    business_connections = {}

    # --- Command Handlers ---
    app.add_handler(CommandHandler("start", commands.start_command))
    app.add_handler(CommandHandler("ping", commands.ping_command))
    app.add_handler(CommandHandler("help", commands.help_command))
    app.add_handler(CommandHandler("status", partial(commands.status_command, db=db, crm=amocrm)))
    app.add_handler(CommandHandler("register", partial(commands.register_command, db=db)))
    app.add_handler(CommandHandler("portfolio", commands.portfolio_command))
    app.add_handler(CommandHandler("broadcast", partial(commands.broadcast_command, db=db)))
    app.add_handler(CommandHandler("amofix", partial(commands.amofix_command, amocrm=amocrm)))
    app.add_handler(CommandHandler("task", partial(commands.task_command, db=db)))
    app.add_handler(CommandHandler("pay", commands.pay_command))

    # --- Message Handlers ---
    # Direct Messages
    app.add_handler(MessageHandler(
        filters.TEXT & (~filters.COMMAND), 
        partial(messages.handle_direct_message, db=db, action_parser=action_parser, msg_controller=msg_controller)
    ))
    
    # Business Connections
    app.add_handler(BusinessConnectionHandler(
        partial(messages.handle_business_connection, business_connections=business_connections)
    ))
    
    # Business Messages
    app.add_handler(MessageHandler(
        filters.UpdateType.BUSINESS_MESSAGE,
        partial(messages.handle_business_message, db=db, action_parser=action_parser, msg_controller=msg_controller)
    ))

    # Edited Messages (Learning)
    app.add_handler(MessageHandler(
        filters.UpdateType.EDITED_BUSINESS_MESSAGE,
        partial(messages.handle_edited_business_message, db=db, learner=learner)
    ))

    # --- Callbacks & Payments ---
    app.add_handler(CallbackQueryHandler(partial(callbacks.task_conf_callback, db=db), pattern="^task_"))
    app.add_handler(CallbackQueryHandler(callbacks.strat_conf_callback, pattern="^strat_"))
    app.add_handler(InlineQueryHandler(callbacks.handle_inline_query))
    
    app.add_handler(PreCheckoutQueryHandler(payments.precheckout_callback))
    app.add_handler(MessageHandler(
        filters.SUCCESSFUL_PAYMENT, 
        partial(payments.successful_payment_callback, db=db, invoicer=invoicer)
    ))

    # Error Handler
    app.add_error_handler(error_handler)
    
    print("✅ Bot is online.")
    app.run_polling()

if __name__ == "__main__":
    main()
