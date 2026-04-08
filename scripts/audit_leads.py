
import asyncio
import logging
import json
from telethon import TelegramClient
from settings import settings
from services.auto_lead_agent import AutoLeadAgent
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    # 1. Init
    client = TelegramClient('userbot_session', settings.API_ID, settings.API_HASH)
    await client.start()
    
    agent = AutoLeadAgent(api_key=settings.GEMINI_API_KEY.get_secret_value())
    
    logger.info("👸 Oisha-OS Audit boshlandi (Oxirgi 100 ta dialog)...")
    
    report = []
    async for dialog in client.iter_dialogs(limit=100):
        if not dialog.is_user or dialog.entity.bot:
            continue
            
        name = getattr(dialog.entity, 'first_name', 'User')
        user_id = dialog.id
        
        # Get last 10 messages for context
        messages = []
        async for msg in client.iter_messages(user_id, limit=10):
            if msg.text:
                messages.append(msg.text)
        
        if not messages:
            report.append(f"{name} (ID: {user_id}) -> SKIP (Xabar yo'q)")
            continue
            
        full_context = "\n".join(reversed(messages))
        user_profile = {"id": user_id, "first_name": name}
        
        # Analyze
        lead_data = await agent.extract_lead_info(full_context, user_profile)
        
        if lead_data and lead_data.get("is_lead"):
            status = "✅ LEAD"
            reason = f"Biznes: {lead_data.get('business', 'Noʻmalum')}"
        else:
            status = "❌ NOT LEAD"
            reason = "Shaxsiy yoki bizga taalluqli bo'lmagan suhbat"
            
        report_line = f"👤 {name} -> {status} -> {reason}"
        logger.info(report_line)
        report.append(report_line)
        
        # Small delay to keep Gemini happy
        await asyncio.sleep(1)

    print("\n" + "="*50)
    print("👸 Oisha-OS AUDIT HISOBOTI (OXIRGI 100 TA DIALOG)")
    print("="*50)
    for line in report:
        print(line)
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
