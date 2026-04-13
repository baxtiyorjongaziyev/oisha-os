import logging
import json
from datetime import datetime
from telethon import events

logger = logging.getLogger(__name__)

class ActivityMonitor:
    """
    Foydalanuvchining (Baxtiyor aka) chiquvchi harakatlarini kuzatish xizmati.
    Maqsad: Qayerga forward qilinayotgani, kimga javob berilayotgani va vaqt sarfini audit qilish.
    """

    def __init__(self, db):
        self.db = db

    async def log_event(self, event):
        """Chiquvchi xabarni tahlil qilish va bazaga saqlash."""
        try:
            message = event.message
            chat = await event.get_chat()
            chat_name = getattr(chat, 'title', None) if hasattr(chat, 'title') else getattr(chat, 'first_name', 'Xususiy')
            
            event_type = 'text'
            source_id = None
            source_name = None
            
            # 1. Forward tekshiruvi
            if message.fwd_from:
                event_type = 'forward'
                fwd = message.fwd_from
                # Kanal, Guruh yoki Userdan forward
                if fwd.from_id:
                    source_id = str(fwd.from_id)
                source_name = fwd.post_author or "Unknown manba"
                
            # 2. Reply tekshiruvi
            elif getattr(message, 'reply_to_msg_id', None):
                event_type = 'reply'

            # 3. Metadata yig'ish
            metadata = {
                'message_id': message.id,
                'is_group': event.is_group,
                'is_private': event.is_private,
                'reply_to': getattr(message, 'reply_to_msg_id', None)
            }

            # 4. Bazaga saqlash
            # Ensure log_user_activity exists in db
            self.db.log_user_activity(
                event_type=event_type,
                chat_id=event.chat_id,
                chat_name=chat_name,
                source_chat_id=source_id,
                source_name=source_name,
                content=message.text[:500] if message.text else "[Media/Fwd]",
                metadata=json.dumps(metadata)
            )
            
            logger.info(f"[MONITOR] Logged {event_type} action in {chat_name}")
            
        except Exception as e:
            logger.error(f"[MONITOR ERROR] log_event: {e}")

    async def get_audit_summary(self, limit=50):
        """Audit uchun oxirgi loglarni yig'ish."""
        return self.db.get_recent_user_activity(limit=limit)
