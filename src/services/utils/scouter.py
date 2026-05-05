import os
import logging
from telethon import TelegramClient, functions
from telethon.tl.functions.messages import GetCommonChatsRequest
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "userbot_session"


class Scouter:
    def __init__(self, session_path=SESSION_NAME, api_key=None, db=None):
        self.client = TelegramClient(session_path, int(API_ID), API_HASH)
        self.api_key = api_key
        self.db = db
        self.is_connected = False

    async def connect(self):
        if not self.is_connected:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                logger.warning("[SCOUTER] User not authorized! Session setup required.")
                return False
            self.is_connected = True
            logger.info("[SCOUTER] Connected successfully.")
        return True

    async def get_user_dosye(self, user_id):
        """Mijoz haqida batafsil ma'lumot (Bio, Umumiy guruhlar, Xabarlar) yig'ish."""
        if not await self.connect():
            return None

        dosye = {
            "bio": "",
            "common_groups": [],
            "messages_in_groups": [],
            "profile_photos_count": 0,
        }

        try:
            # 1. Full User Info (Bio)
            full_user = await self.client(
                functions.users.GetFullUserRequest(id=user_id)
            )
            dosye["bio"] = getattr(full_user.full_user, "about", "")

            # 2. Common Chats
            common = await self.client(
                GetCommonChatsRequest(user_id=user_id, max_id=0, limit=100)
            )
            for chat in common.chats:
                dosye["common_groups"].append({"id": chat.id, "title": chat.title})

            # 3. Guruhlardagi muloqotni tahlil qilish (birinchi 3 ta umumiy guruhdan)
            owner_id = (await self.client.get_me()).id
            for group in dosye["common_groups"][:3]:
                group_id = group["id"]
                # 3.1. Mijozning xabarlarini va unga bo'lgan javoblarni olish
                async for msg in self.client.iter_messages(group_id, limit=20):
                    # Agar xabar mijozdan bo'lsa
                    if msg.sender_id == user_id:
                        dosye["messages_in_groups"].append(
                            f"Mijoz ({group['title']}): {msg.text}"
                        )

                    # Agar xabar Owner'dan bo'lsa va u mijozga REPLY bo'lsa (yoki yaqin muloqot)
                    elif msg.sender_id == owner_id:
                        if msg.reply_to and msg.reply_to.reply_to_msg_id:
                            # Reply qilingan xabarni topishga urinish (sodda usul - yaqinlik bo'yicha)
                            dosye["messages_in_groups"].append(
                                f"Siz (Guruh: {group['title']}): {msg.text}"
                            )
                        elif text := msg.text:
                            # Guruhdagi umumiy muloqotda Owner xabari (mijoz ismi/usernamesi zikr qilingan bo'lsa yanada yaxshi)
                            dosye["messages_in_groups"].append(
                                f"Siz (Guruh: {group['title']}): {text}"
                            )

            # 4. Profil rasmlari soni
            photos = await self.client.get_profile_photos(user_id)
            dosye["profile_photos_count"] = len(photos)

            return dosye
        except Exception as e:
            logger.error(f"[SCOUTER ERROR] {e}")
            return None

    async def disconnect(self):
        await self.client.disconnect()
        self.is_connected = False


if __name__ == "__main__":
    # Test uchun
    async def main():
        scouter = Scouter()
        # Test user_id ni kiriting
        res = await scouter.get_user_dosye(1234567)
        print(res)

    # asyncio.run(main())
