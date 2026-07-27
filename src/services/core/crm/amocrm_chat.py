import logging
import httpx
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("AmoCRMChatClient")

class AmoCRMChatClient:
    """Client for AmoCRM Online Chats API (Wazzup alternative)."""
    def __init__(self, amocrm_account_id: str, channel_id: str, channel_secret: str):
        self.account_id = amocrm_account_id
        self.channel_id = channel_id
        self.channel_secret = channel_secret
        self.base_url = f"https://amocrm.ru/v2/origin/custom/{self.channel_secret}"
    
    async def send_message_to_amocrm(
        self, 
        user_id: int, 
        chat_id: int, 
        text: str, 
        sender_name: str, 
        phone: Optional[str] = None
    ) -> bool:
        """Sends a message from Telegram to AmoCRM Chat interface."""
        if not self.channel_secret:
            logger.warning("[AMOCRM CHAT] channel_secret is not set. Skipping.")
            return False
            
        payload = {
            "account_id": self.account_id,
            "time": int(datetime.now().timestamp()),
            "message": {
                "type": "text",
                "text": text,
                "msg_id": str(uuid.uuid4()),
                "sender": {
                    "id": str(user_id),
                    "name": sender_name,
                },
                "conversation": {
                    "id": str(chat_id),
                    "client_id": str(user_id)
                }
            }
        }
        
        if phone:
            payload["message"]["sender"]["profile"] = {"phone": phone}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.base_url, json=payload)
                if response.status_code >= 400:
                    logger.error(f"[AMOCRM CHAT] Error {response.status_code}: {response.text}")
                    return False
                logger.info(f"[AMOCRM CHAT] Message successfully synced to AmoCRM for user {user_id}")
                return True
        except Exception as e:
            logger.error(f"[AMOCRM CHAT] Exception while sending to AmoCRM: {e}")
            return False
