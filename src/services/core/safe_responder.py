import asyncio
import random
import logging
import os
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ─── Rate-limit constants (Phase 2.2) ────────────────────────────────────
# Har chat uchun minimal oraliq (soniya). Spam/flood'dan himoya.
PER_CHAT_LIMIT_SECS = int(os.environ.get("AUTO_REPLY_PER_CHAT_SECS", "30"))
# Soatiga global maksimal javob soni (Telegram FloodWait threshold'dan past).
GLOBAL_HOURLY_LIMIT = int(os.environ.get("AUTO_REPLY_GLOBAL_HOURLY", "30"))


class SafeResponder:
    """
    Userbot xavfsizligini ta'minlovchi xizmat.
    - Tasodifiy kechikishlar qo'shadi.
    - Guruhlarni filtrlash qoidalarini boshqaradi.
    - Rate-limiting (xabarlar orasidagi masofa)ni nazorat qiladi.
      - Per-chat: `PER_CHAT_LIMIT_SECS` (default 30s)
      - Global: `GLOBAL_HOURLY_LIMIT` (default 30/hour)
    """

    def __init__(self, allowed_groups: list = None):
        # Faqat ruxsat berilgan guruh ID lari yoki Nomlari
        self.allowed_groups = allowed_groups or ["Jon Branding Team", "Loyihalar | Jon.Branding"]
        self.last_response_time = {} # {chat_id: timestamp}
        self.global_rate_limit = 2.0 # Har bir xabarlar orasidagi minimal vaqt (soniya)
        self.me_id = None
        # Global hourly limit uchun sliding window
        self._global_response_times: deque = deque(maxlen=max(GLOBAL_HOURLY_LIMIT * 2, 60))
        # Jamoa a'zolari (Whitelist)
        self.team_whitelist = [
            1774538344630,      # Baxtiyor aka (Owner)
            "@E_Oydinn",        # Oydin opa
            "@Oydin_JonBranding",# Oydin opa (alt)
            "@baxtiyorjongaziyev", # Baxtiyor aka (username)
            "@YahyoNamer",       # Hasan aka (Yahyo Namer)
            "@JonBranding_PM"    # Inomjon aka (JonBranding PM)
        ]

    async def is_team_member(self, user_id: int, username: str = None) -> bool:
        """Foydalanuvchi jamoa a'zosi ekanligini tekshirish."""
        if user_id in self.team_whitelist:
            return True
        if username:
            if not username.startswith("@"):
                username = f"@{username}"
            if username in self.team_whitelist:
                return True
        return False

    async def update_me_id(self, me_id: int):
        self.me_id = me_id

    async def should_respond(self, event) -> bool:
        """Xabarga javob berish kerakmi yoki yo'qligini tekshirish."""
        # 0. Botning o'z xabarlariga javob bermaslik (Sikl oldini olish)
        if event.out:
            return False
            
        # 1. Botning o'zi yoki Sender ma'lumotlarini olish
        sender = await event.get_sender()
        sender_id = event.sender_id
        sender_username = getattr(sender, 'username', '')
        if sender_username:
            sender_username = f"@{sender_username}"

        # 2. Whitelist tekshiruvi (Jamoa a'zosi bo'lsa muloqot qilamiz)
        is_team_member = (
            sender_id in self.team_whitelist or 
            sender_username in self.team_whitelist
        )

        if not is_team_member:
            # Mijoz yoki notanish odam bo'lsa, javob bermaymiz
            logger.info(f"[SAFE] Blocking non-team member: {sender_id} ({sender_username})")
            return False

        # 3. Agar jamoa a'zosi bo'lsa, qayerda yozganiga qarab tekshiramiz
        if event.is_private:
            return True
        
        # 4. Guruh bo'lsa - faqat whitelist qilingan guruhlar ichida
        if event.is_group:
            chat = await event.get_chat()
            chat_id = event.chat_id
            chat_title = getattr(chat, 'title', '')
            if chat_title in self.allowed_groups or str(chat_id) in self.allowed_groups:
                # Faqat mention bo'lganda (agar guruh bo'lsa)
                if event.mentioned or event.is_reply:
                    return True
                return False
            else:
                # Jamoa a'zosi bo'lsa ham, ruxsat berilmagan guruhda bo'lsa javob bermaymiz
                return False

        return False

    async def prepare_to_reply(self, event, client):
        """Javob berishdan oldin 'human-like' effektlarni bajarish."""
        # 1. Typing... holatini ko'rsatish
        async with client.action(event.chat_id, 'typing'):
            # 2. Tasodifiy kechikish (3 dan 7 soniyagacha)
            delay = random.uniform(3, 7)
            logger.info(f"[SAFE] Delaying reply for {delay:.2f}s to chat {event.chat_id}")
            await asyncio.sleep(delay)

    def update_rate_limit(self, chat_id):
        """Oxirgi javob vaqtini saqlash (per-chat + global sliding window)."""
        now = datetime.now()
        self.last_response_time[chat_id] = now
        self._global_response_times.append(now)

    def is_rate_limited(self, chat_id) -> tuple[bool, str]:
        """
        Rate-limit tekshiruvi. Return: (limited, reason).
        - Per-chat: oxirgi javobdan `PER_CHAT_LIMIT_SECS` soniya o'tmagan bo'lsa bloklaydi.
        - Global: oxirgi 1 soatda `GLOBAL_HOURLY_LIMIT` dan ko'p javob bo'lsa bloklaydi.

        Chaqiruvchi `event.respond` oldidan tekshirib ko'rishi mumkin.
        """
        now = datetime.now()

        # Per-chat check
        last = self.last_response_time.get(chat_id)
        if last is not None:
            delta = (now - last).total_seconds()
            if delta < PER_CHAT_LIMIT_SECS:
                return True, f"per_chat({delta:.1f}s<{PER_CHAT_LIMIT_SECS}s)"

        # Global hourly check (sliding 1-hour window)
        cutoff = now - timedelta(hours=1)
        # Eski yozuvlarni tozalash (amortized O(1))
        while self._global_response_times and self._global_response_times[0] < cutoff:
            self._global_response_times.popleft()
        if len(self._global_response_times) >= GLOBAL_HOURLY_LIMIT:
            return True, f"global_hourly({len(self._global_response_times)}/{GLOBAL_HOURLY_LIMIT})"

        return False, "ok"
