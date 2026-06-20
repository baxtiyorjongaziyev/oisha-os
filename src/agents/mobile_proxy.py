"""
Oisha Mobile Proxy — Instagram va Telegram avtomatizatsiyasi.

Oisha-OS tizimi uchun ijtimoiy tarmoqlarga ulanib,
mijozlar bilan inson kabi muloqot qilish imkonini beradi.
"""
import os
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class OishaMobileProxy:
    """Instagram DM avtomatizatsiyasi (instagrapi asosida)."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.client = None
        self.username = username or os.getenv("IG_USERNAME")
        self.password = password or os.getenv("IG_PASSWORD")
        self._logged_in = False

    # ── Auth ───────────────────────────────────────────────

    def login(self):
        """Instagram'ga kirish."""
        if not self.username or not self.password:
            raise ValueError("Instagram username yoki password berilmagan. "
                             ".env faylda IG_USERNAME va IG_PASSWORD ni to'ldiring.")
        try:
            from instagrapi import Client
        except ImportError as exc:
            raise RuntimeError(
                "Instagram funksiyasi uchun 'instagrapi' paketi o'rnatilmagan."
            ) from exc
        if self.client is None:
            self.client = Client()
        logger.info(f"[MobileProxy] Logging in as {self.username}...")
        try:
            # Avval session fayldan yuklashga harakat qilamiz
            session_file = f"ig_session_{self.username}.json"
            if os.path.exists(session_file):
                self.client.load_settings(session_file)
                self.client.login(self.username, self.password)
                logger.info("[MobileProxy] Logged in from saved session.")
            else:
                self.client.login(self.username, self.password)
                self.client.dump_settings(session_file)
                logger.info("[MobileProxy] Fresh login successful, session saved.")
            self._logged_in = True
        except Exception as e:
            logger.error(f"[MobileProxy] Login xatolik: {e}")
            raise

    def _ensure_login(self):
        """Login qilinganligini tekshirish."""
        if not self._logged_in:
            raise RuntimeError("Instagram'ga kiring avval. login() ni chaqiring.")

    # ── Direct Messages ────────────────────────────────────

    def get_direct_threads(self, amount: int = 20) -> List[Any]:
        """Barcha DM thread'larni olish."""
        self._ensure_login()
        logger.info(f"[MobileProxy] Fetching {amount} direct threads...")
        return self.client.direct_threads(amount=amount)

    def get_unread_messages(self) -> List[Dict[str, Any]]:
        """O'qilmagan xabarlarni olish."""
        self._ensure_login()
        threads = self.client.direct_threads(amount=20)
        unread = []
        for thread in threads:
            # Oxirgi xabar bizdan emas bo'lsa — javob kutilmoqda
            if thread.messages:
                last_msg = thread.messages[0]
                if str(last_msg.user_id) != str(self.client.user_id):
                    unread.append({
                        "thread_id": thread.id,
                        "user_id": last_msg.user_id,
                        "username": thread.users[0].username if thread.users else "unknown",
                        "full_name": thread.users[0].full_name if thread.users else "unknown",
                        "text": last_msg.text or "[media]",
                        "timestamp": str(last_msg.timestamp),
                    })
        logger.info(f"[MobileProxy] Found {len(unread)} unread threads.")
        return unread

    def get_thread_messages(self, thread_id: int, amount: int = 20) -> List[Dict[str, Any]]:
        """Ma'lum bir thread'dagi xabarlar tarixini olish."""
        self._ensure_login()
        messages = self.client.direct_messages(thread_id, amount=amount)
        result = []
        for msg in messages:
            result.append({
                "user_id": msg.user_id,
                "text": msg.text or "[media]",
                "timestamp": str(msg.timestamp),
                "is_me": str(msg.user_id) == str(self.client.user_id),
            })
        return result

    def send_message(self, thread_id: int, text: str) -> bool:
        """DM ga xabar yuborish (thread_id orqali)."""
        self._ensure_login()
        logger.info(f"[MobileProxy] Sending message to thread {thread_id}: {text[:50]}...")
        try:
            self.client.direct_send(text, thread_ids=[thread_id])
            return True
        except Exception as e:
            logger.error(f"[MobileProxy] Send message error: {e}")
            return False

    def send_message_to_user(self, user_id: int, text: str) -> bool:
        """DM ga xabar yuborish (user_id orqali — thread topib)."""
        self._ensure_login()
        logger.info(f"[MobileProxy] Sending DM to user {user_id}: {text[:50]}...")
        try:
            self.client.direct_send(text, user_ids=[user_id])
            return True
        except Exception as e:
            logger.error(f"[MobileProxy] Send to user error: {e}")
            return False

    def send_photo_dm(self, thread_id: int, photo_path: str, caption: str = "") -> bool:
        """DM ga rasm yuborish."""
        self._ensure_login()
        logger.info(f"[MobileProxy] Sending photo to thread {thread_id}")
        try:
            self.client.direct_send_photo(photo_path, thread_ids=[thread_id])
            if caption:
                self.client.direct_send(caption, thread_ids=[thread_id])
            return True
        except Exception as e:
            logger.error(f"[MobileProxy] Send photo error: {e}")
            return False

    # ── User Info ──────────────────────────────────────────

    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Username orqali foydalanuvchi ma'lumotlarini olish."""
        self._ensure_login()
        try:
            user_id = self.client.user_id_from_username(username)
            info = self.client.user_info(user_id)
            return {
                "user_id": info.pk,
                "username": info.username,
                "full_name": info.full_name,
                "biography": info.biography,
                "follower_count": info.follower_count,
                "following_count": info.following_count,
                "media_count": info.media_count,
                "is_private": info.is_private,
                "is_verified": info.is_verified,
                "profile_pic_url": str(info.profile_pic_url),
            }
        except Exception as e:
            logger.error(f"[MobileProxy] User info error for {username}: {e}")
            return None

    def search_users(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Foydalanuvchilarni qidirish."""
        self._ensure_login()
        try:
            users = self.client.search_users(query)[:limit]
            return [
                {
                    "user_id": u.pk,
                    "username": u.username,
                    "full_name": u.full_name,
                    "is_private": u.is_private,
                }
                for u in users
            ]
        except Exception as e:
            logger.error(f"[MobileProxy] Search users error: {e}")
            return []

    # ── Content ────────────────────────────────────────────

    def get_user_posts(self, username: str, amount: int = 5) -> List[Dict[str, Any]]:
        """Foydalanuvchining so'nggi postlarini olish."""
        self._ensure_login()
        try:
            user_id = self.client.user_id_from_username(username)
            medias = self.client.user_medias(user_id, amount=amount)
            return [
                {
                    "media_id": str(m.pk),
                    "caption": (m.caption_text or "")[:200],
                    "like_count": m.like_count,
                    "comment_count": m.comment_count,
                    "taken_at": str(m.taken_at),
                    "media_type": str(m.media_type),
                }
                for m in medias
            ]
        except Exception as e:
            logger.error(f"[MobileProxy] Get posts error: {e}")
            return []

    # ── Following / Followers ──────────────────────────────

    def follow_user(self, username: str) -> bool:
        """Foydalanuvchini follow qilish."""
        self._ensure_login()
        try:
            user_id = self.client.user_id_from_username(username)
            self.client.user_follow(user_id)
            logger.info(f"[MobileProxy] Followed {username}")
            return True
        except Exception as e:
            logger.error(f"[MobileProxy] Follow error: {e}")
            return False

    def unfollow_user(self, username: str) -> bool:
        """Foydalanuvchini unfollow qilish."""
        self._ensure_login()
        try:
            user_id = self.client.user_id_from_username(username)
            self.client.user_unfollow(user_id)
            logger.info(f"[MobileProxy] Unfollowed {username}")
            return True
        except Exception as e:
            logger.error(f"[MobileProxy] Unfollow error: {e}")
            return False


class OishaTelegramProxy:
    """
    Telegram Userbot avtomatizatsiyasi.
    Bu klass asosiy Telethon client'ga wrapper sifatida ishlaydi
    va Oisha-OS ning boshqa qismlaridan Telegram funksiyalarini chaqirish uchun ishlatiladi.
    """

    def __init__(self, client=None):
        self.client = client
        self._initialized = False

    def set_client(self, client):
        """Telethon client'ni o'rnatish (main.py dan uzatiladi)."""
        self.client = client
        self._initialized = True

    def _ensure_client(self):
        """Client mavjudligini tekshirish."""
        if not self.client:
            raise RuntimeError("Telegram client not set. Call set_client() first.")

    async def send_message(self, chat_id: int, text: str):
        """Telegram chat'ga xabar yuborish."""
        self._ensure_client()
        logger.info(f"[TelegramProxy] Sending message to {chat_id}: {text[:50]}...")
        await self.client.send_message(chat_id, text)

    async def get_entity_info(self, identifier) -> Optional[Dict[str, Any]]:
        """Username yoki ID orqali entity ma'lumotlarini olish."""
        self._ensure_client()
        try:
            entity = await self.client.get_entity(identifier)
            return {
                "id": entity.id,
                "first_name": getattr(entity, "first_name", None),
                "last_name": getattr(entity, "last_name", None),
                "username": getattr(entity, "username", None),
                "phone": getattr(entity, "phone", None),
            }
        except Exception as e:
            logger.error(f"[TelegramProxy] Get entity error: {e}")
            return None

    async def get_recent_messages(self, chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """So'nggi xabarlarni olish."""
        self._ensure_client()
        messages = await self.client.get_messages(chat_id, limit=limit)
        return [
            {
                "id": msg.id,
                "text": msg.text or "[media]",
                "sender_id": msg.sender_id,
                "date": str(msg.date),
            }
            for msg in messages
        ]

    async def forward_message(self, from_chat: int, to_chat: int, message_id: int):
        """Xabarni bir chatdan boshqasiga forward qilish."""
        self._ensure_client()
        await self.client.forward_messages(to_chat, message_id, from_chat)

    async def search_contacts(self, phone: str) -> Optional[Dict[str, Any]]:
        """Telefon raqami bo'yicha Telegram kontaktni qidirish."""
        self._ensure_client()
        try:
            from telethon.tl.functions.contacts import ImportContactsRequest
            from telethon.tl.types import InputPhoneContact
            import random

            contact = InputPhoneContact(
                client_id=random.randint(0, 2**31),
                phone=phone,
                first_name="Search",
                last_name="",
            )
            result = await self.client(ImportContactsRequest([contact]))
            if result.users:
                user = result.users[0]
                return {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "phone": user.phone,
                }
        except Exception as e:
            logger.error(f"[TelegramProxy] Search contact error: {e}")
        return None


# Sinov uchun
if __name__ == "__main__":
    print("Oisha Mobile Proxy (Instagram + Telegram) tayyor.")
    print("Instagram: OishaMobileProxy() — login() bilan boshlang.")
    print("Telegram: OishaTelegramProxy() — set_client() bilan boshlang.")
