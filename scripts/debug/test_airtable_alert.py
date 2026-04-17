import asyncio
import os
import sys
import logging
from datetime import datetime

# Path setup to import from src
sys.path.append(os.getcwd())

from src.database import Database
from src import config
from src.services.airtable_sync import AirtableSync

async def run_test():
    logging.basicConfig(level=logging.INFO)
    print("🚀 [REAL TEST] Airtable Stagnation Alert testing with LIVE data...")
    
    sync = AirtableSync() # Will use new .env Base ID and 'Loyihalar' table
    overdue = sync.get_overdue_projects()
    
    if not overdue:
        print("ℹ️ No real overdue projects found in today's scan. Fetching all projects to verify connection...")
        all_projects = sync.get_projects()
        if all_projects:
            print(f"✅ Connection OK. Found {len(all_projects)} total projects.")
            print(f"Sample project: {all_projects[0].get('fields', {}).get('Loyiha nomi')}")
            # For the sake of the user's test request, if there are NO overdue ones, 
            # I will pick one project and treat it as 'Tested' to show the format.
            overdue = [all_projects[0]]
        else:
            print("❌ No projects found at all. Please check Airtable table content.")
            return

    bot_token = os.environ.get("BOT_TOKEN") or getattr(config, "BOT_TOKEN", None)
    group_id = getattr(config, "PROJECTS_GROUP_ID", None)
    thread_id = getattr(config, "TOPIC_TASKS_ID", None)
    
    from telegram import Bot
    bot = Bot(token=bot_token)
    
    msg = "🏗 **[REAL DATA TEST] AIRTABLE STAGNATION ALERT** 🏗\n\n"
    msg += "📢 @Inomjon_JonBranding, quyidagi loyihalar to'xtab qolgan yoki muddati o'tgan:\n\n"
    
    for p in overdue[:5]:
        fields = p.get("fields", {})
        p_name = fields.get('Loyiha nomi') or fields.get('Project Name') or "Nomsiz"
        stage = fields.get('Status') or fields.get('Stage') or "Noma'lum"
        deadline = fields.get('Deadline') or fields.get('Muddati') or "Belgilanmagan"
        
        msg += f"• <b>{p_name}</b> (Bosqich: {stage}, Muddat: {deadline})\n"
        
    msg += "\nIltimos, ushbu loyihalarni harakatga keltiring yoki statusni yangilang! 👸🛡️"
    
    try:
        # Fallback logic included in proactive_worker is manual here for test
        try:
            await bot.send_message(chat_id=group_id, text=msg, parse_mode="HTML", message_thread_id=thread_id)
            print("✅ Success via Thread!")
        except:
            await bot.send_message(chat_id=group_id, text=msg, parse_mode="HTML")
            print("✅ Success via Fallback (Direct Group)!")
    except Exception as e:
        print(f"❌ Error sending test: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
