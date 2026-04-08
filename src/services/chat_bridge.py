import logging
import aiohttp
import json
import os
from typing import Optional, Dict, Any

logger = logging.getLogger("ChatBridge")

class ChatBridge:
    def __init__(self, amocrm_subdomain: str, amocrm_token: str):
        self.subdomain = amocrm_subdomain
        self.token = amocrm_token
        # AmoCRM Chat Backend (Amojo)
        self.amojo_url = f"https://amojo.amocrm.ru/v1/chats"
        self.channel_id = os.environ.get("AMOCRM_CHAT_CHANNEL_ID")
        self.session = aiohttp.ClientSession()

    async def send_to_amocrm(self, user_id: int, user_name: str, text: str, message_id: str):
        """
        Send a message from Telegram to AmoCRM Chat.
        This simulates an incoming message from a customer.
        """
        if not self.channel_id:
            logger.warning("[CHAT BRIDGE] AMOCRM_CHAT_CHANNEL_ID not set. Skipping real-time sync.")
            return

        payload = {
            "conversation_id": f"tg_{user_id}",
            "user": {
                "id": str(user_id),
                "name": user_name,
                "avatar": "" # Optional
            },
            "message": {
                "id": message_id,
                "type": "text",
                "text": text,
                "timestamp": int(os.sys.time.time())
            }
        }
        
        # Note: In real life, we need a secret/token for Amojo.
        # This is a simplified version.
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        
        try:
            # Placeholder for actual Amojo endpoint call
            # response = await self.session.post(f"{self.amojo_url}/incoming", json=payload, headers=headers)
            logger.info(f"[CHAT BRIDGE] Pushed message from {user_name} to AmoCRM Chat.")
        except Exception as e:
            logger.error(f"[CHAT BRIDGE ERROR] Push failed: {e}")

    async def close(self):
        await self.session.close()

# Note: The mapping TG user -> AmoCRM contact is assumed to be handled 
# by the existing phone number lookup logic.
