
import logging
import asyncio
from telethon import functions, types, TelegramClient
from typing import List, Optional

logger = logging.getLogger(__name__)

class FolderManager:
    """
    Manages Telegram Dialog Filters (Folders) to organize contacts based on AI intent.
    """
    
    # Mapping intent to folder titles (Premium Enhanced)
    INTENT_MAP = {
        "HOT_LEAD": "🔥 Issiq Lidlar",
        "POTENTIAL": "🌱 Potensial",
        "VIP_CLIENT": "👑 VIP Mijozlar",
        "PARTNER": "🤝 Hamkorlar",
        "CONTENT": "📚 Materiallar",
        "NETWORKING": "☕️ Networking",
        "SUPPORT": "🛠 Servis/Yordam",
        "TEAM": "👥 Jamoa",
        "SPAM": "🚫 Spam/Filter"
    }

    def __init__(self, client: TelegramClient):
        self.client = client
        self.existing_filters = []

    async def _fetch_filters(self):
        """Mavjud barcha papkalarni yuklash."""
        try:
            self.existing_filters = await self.client(functions.messages.GetDialogFiltersRequest())
            return self.existing_filters
        except Exception as e:
            logger.error(f"[FOLDER] GetDialogFilters error: {e}")
            return []

    async def assign_to_folder(self, user_id: int, intent: str):
        """Foydalanuvchini maqsadiga qarab tegishli papkaga joylashtirish."""
        folder_title = self.INTENT_MAP.get(intent)
        if not folder_title:
            logger.warning(f"[FOLDER] No folder title for intent: {intent}")
            return False

        try:
            # 1. Fetch current state
            filters = await self._fetch_filters()
            target_filter = None
            
            # 2. Find existing folder by title
            for f in filters:
                if isinstance(f, types.DialogFilter) and f.title == folder_title:
                    target_filter = f
                    break
            
            # 3. Create peer object
            peer = await self.client.get_input_entity(user_id)
            
            if target_filter:
                # Add to existing folder if not already there
                peer_ids = [p.user_id for p in target_filter.include_peers if isinstance(p, types.InputPeerUser)]
                if user_id not in peer_ids:
                    target_filter.include_peers.append(peer)
                    await self.client(functions.messages.UpdateDialogFilterRequest(
                        id=target_filter.id,
                        filter=target_filter
                    ))
                    logger.info(f"[FOLDER] User {user_id} added to existing folder: {folder_title}")
            else:
                # Create new folder
                # Telegram Premium allows up to 20 folders. IDs are usually sequential.
                used_ids = [f.id for f in filters if hasattr(f, 'id')]
                new_id = 2
                while new_id in used_ids:
                    new_id += 1
                
                if new_id > 25: # Safety break, though Premium handles many
                    logger.warning(f"[FOLDER] Too many folders already (ID {new_id}). Skipping.")
                    return False
                
                new_filter = types.DialogFilter(
                    id=new_id,
                    title=folder_title,
                    include_peers=[peer],
                    contacts=False,
                    non_contacts=False,
                    groups=False,
                    broadcasts=False,
                    bots=False,
                    exclude_muted=False,
                    exclude_read=False,
                    exclude_archived=False
                )
                await self.client(functions.messages.UpdateDialogFilterRequest(
                    id=new_id,
                    filter=new_filter
                ))
                logger.info(f"[FOLDER] New folder created and user {user_id} added: {folder_title}")
            
            return True
        except Exception as e:
            logger.error(f"[FOLDER] Assign error for user {user_id}: {e}")
            return False
