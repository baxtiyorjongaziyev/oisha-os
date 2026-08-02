import logging
import httpx
import uuid
import hmac
import hashlib
import json
from email.utils import formatdate
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("AmoCRMChatClient")

class AmoCRMChatClient:
    """Client for AmoCRM Online Chats API (Wazzup alternative)."""
    def __init__(self, amocrm_account_id: str, channel_id: str, channel_secret: str):
        self.account_id = amocrm_account_id
        self.channel_id = channel_id
        self.channel_secret = channel_secret
        self.base_url = f"https://amojo.amocrm.ru/v2/origin/custom/{self.channel_id}"
    
    def _get_headers(self, method: str, path: str, body_bytes: bytes) -> dict:
        date_str = formatdate(timeval=None, localtime=False, usegmt=True)
        content_type = "application/json"
        # AmoCRM's request-signing protocol requires Content-MD5. This digest
        # is protocol metadata, not a password hash or security primitive.
        content_md5 = hashlib.md5(body_bytes, usedforsecurity=False).hexdigest().lower()
        
        signature_string = f"{method}\n{content_md5}\n{content_type}\n{date_str}\n{path}"
        signature = hmac.new(
            self.channel_secret.encode('utf-8'),
            signature_string.encode('utf-8'),
            hashlib.sha1
        ).hexdigest().lower()
        
        return {
            "Content-Type": content_type,
            "Date": date_str,
            "Content-MD5": content_md5,
            "X-Signature": signature
        }

    async def connect_channel(self) -> bool:
        if not self.channel_secret:
            return False
            
        url = f"{self.base_url}/connect"
        path = f"/v2/origin/custom/{self.channel_id}/connect"
        
        payload = {
            "account_id": self.account_id,
            "title": "Oisha Telegram Chat",
            "hook_api_version": "v2"
        }
        
        body_bytes = json.dumps(payload).encode('utf-8')
        headers = self._get_headers("POST", path, body_bytes)
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, content=body_bytes, headers=headers)
                if response.status_code >= 400:
                    logger.error(f"[AMOCRM CHAT] Error connecting channel: {response.text}")
                    return False
                logger.info("[AMOCRM CHAT] Channel successfully connected!")
                return True
        except Exception as e:
            logger.error(f"[AMOCRM CHAT] Exception connecting channel: {e}")
            return False
    
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

        url = self.base_url
        path = f"/v2/origin/custom/{self.channel_id}"
        body_bytes = json.dumps(payload).encode('utf-8')
        headers = self._get_headers("POST", path, body_bytes)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, content=body_bytes, headers=headers)
                if response.status_code >= 400:
                    logger.error(f"[AMOCRM CHAT] Error {response.status_code}: {response.text}")
                    return False
                logger.info(f"[AMOCRM CHAT] Message successfully synced to AmoCRM for user {user_id}")
                return True
        except Exception as e:
            logger.error(f"[AMOCRM CHAT] Exception while sending to AmoCRM: {e}")
            return False
