import asyncio
import os
import sys
import logging
from telethon import TelegramClient
from src.config import settings

# [CRITICAL] Ensure local modules are discoverable
sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def find_active_session():
    # List of common session paths to check
    possible_sessions = [
        'data/userbot_session',
        'userbot_session',
        'data/oisha_session',
        'oisha_session',
        'data/anon',
        'oisha_userbot'
    ]
    
    for session_path in possible_sessions:
        full_path = f"{session_path}.session"
        if not os.path.exists(full_path):
            continue
            
        logger.info(f"🔍 Checking session: {full_path}...")
        
        # Test connection WITHOUT blocking/interaction
        client = TelegramClient(
            session_path,
            settings.API_ID,
            settings.API_HASH
        )
        
        try:
            # Short timeout to avoid hanging on login prompts
            await client.connect()
            authorized = await client.is_user_authorized()
            
            if authorized:
                me = await client.get_me()
                logger.info(f"✅ FOUND AUTHORIZED SESSION: {full_path} (User: {me.first_name})")
                return session_path
            else:
                logger.warning(f"❌ Session NOT authorized: {full_path}")
        except Exception as e:
            logger.error(f"⚠️ Error checking {full_path}: {e}")
        finally:
            await client.disconnect()
            
    return None

if __name__ == "__main__":
    result = asyncio.run(find_active_session())
    if result:
        print(f"\n👸 [RESULT] Active Session Path: {result}")
    else:
        print("\n❌ [RESULT] No authorized sessions found. We need a fresh login!")
