import time
import logging
from typing import Dict, List, Optional
import asyncio

logger = logging.getLogger("SessionManager")

class SessionManager:
    def __init__(self, sync_callback, inactivity_timeout=600):
        """
        sync_callback: Function to call when a session block is ready (async)
        inactivity_timeout: Seconds of silence before flushing (default 10 mins)
        """
        self.sessions: Dict[int, List[Dict]] = {}
        self.last_activity: Dict[int, float] = {}
        self.sync_callback = sync_callback
        self.timeout = inactivity_timeout
        self.is_running = True

    def add_message(self, user_id: int, sender: str, text: str, phone: str = None):
        if user_id not in self.sessions:
            self.sessions[user_id] = []
        
        self.sessions[user_id].append({
            "sender": sender,
            "text": text,
            "time": time.strftime("%H:%M:%S"),
            "phone": phone
        })
        self.last_activity[user_id] = time.time()
        logger.info(f"[SESSION] Message added for {user_id}. Buffer size: {len(self.sessions[user_id])}")

    async def monitor_sessions(self):
        """Background task to flush inactive sessions."""
        while self.is_running:
            now = time.time()
            flushed_users = []
            
            for user_id, last_time in list(self.last_activity.items()):
                if now - last_time > self.timeout:
                    await self.flush_session(user_id)
                    flushed_users.append(user_id)
            
            await asyncio.sleep(60) # Check every minute

    async def flush_session(self, user_id: int):
        if user_id not in self.sessions or not self.sessions[user_id]:
            return

        messages = self.sessions[user_id]
        phone = messages[0].get("phone")
        
        # Build block text
        block_text = f"📝 --- SUHBAT BLOKI ({time.strftime('%Y-%m-%d')}) ---\n\n"
        for m in messages:
            block_text += f"[{m['time']}] {m['sender']}: {m['text']}\n"
        block_text += "\n--- BLOK YAKUNI ---"

        logger.info(f"[SESSION] Flushing {len(messages)} messages for {user_id}")
        
        try:
            await self.sync_callback(user_id, phone, block_text)
            # Clear session
            del self.sessions[user_id]
            del self.last_activity[user_id]
        except Exception as e:
            logger.error(f"[SESSION ERROR] Flush failed for {user_id}: {e}")

    def stop(self):
        self.is_running = False
