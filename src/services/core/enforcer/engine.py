"""
DailyEnforcer main engine and Jon Branding team configuration.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from typing import Dict, Optional
from src.context import app_ctx
from src.services.core.mandatory_workflow import Role, get_mandatory_workflow
from src.services.core.enforcer.notifications import NotificationsMixin
from src.services.core.enforcer.routines import RoutinesMixin

logger = logging.getLogger("DailyEnforcer")


class DailyEnforcer(RoutinesMixin, NotificationsMixin):
    """
    Jon Branding jamoasi uchun kunlik qat'iy intizom va monitoring tizimi.
    """

    def __init__(self, bot=None):
        self.bot = bot
        self.workflow = get_mandatory_workflow()
        self.team_members: Dict[str, Dict] = {}
        self.is_running = False

        # Sozlamalar
        self.morning_time = time(8, 30)  # 08:30 - Vazifalar beriladi
        self.evening_time = time(18, 0)  # 18:00 - Tekshiriladi
        self.lunch_time = time(13, 0)  # 13:00 - Eslatma

        # Ogohlantirish chegaralari
        self.warning_hours = 2  # 2 soatdan keyin ogohlantirish
        self.block_hours = 4  # 4 soatdan keyin bloklash

        # Xabarlar
        self.morning_messages = [
            "🎯 {name}, bugungi Surgical Mission tayyor!",
            "⚔️  {name}, o'z vazifangizni bilasizmi?",
            "🔥 {name}, bugun qanday lead ovlaysiz?",
            "📊 {name}, kunlik rejani boshlash vaqti!",
        ]

        self.warning_messages = [
            "⚠️ {name}, {task} vazifasi hali bajarilmagan!",
            "⏰ {name}, {task} uchun vaqt tugayapti!",
            "🚨 {name}, {task} bajarilmasa bloklanasiz!",
        ]

        self.evening_messages = [
            "📈 {name}, bugungi natijalar qanday?",
            "🌙 {name}, kunlik hisobot tayyormi?",
            "✅ {name}, barcha vazifalar bajarildimi?",
        ]

    def register_team_member(
        self,
        user_id: str,
        name: str,
        role: Role,
        telegram_id: Optional[str] = None,
        phone: Optional[str] = None,
    ):
        """Jamoa a'zosini ro'yxatdan o'tkazish"""
        self.team_members[user_id] = {
            "id": user_id,
            "name": name,
            "role": role,
            "telegram_id": telegram_id,
            "phone": phone,
            "registered_at": datetime.now().isoformat(),
            "is_active": True,
            "streak_days": 0,  # Ketma-ket muvaffaqiyatli kunlar
            "total_completed": 0,
        }

    async def start_daily_cycle(self):
        """Kunlik tsiklni boshlash (async daemon)"""
        self.is_running = True

        while self.is_running:
            now = datetime.now()
            current_time = now.time()

            # 08:30 - Ertalabki taqsimlash
            if self._is_time_match(current_time, self.morning_time):
                await self._morning_routine()
                await asyncio.sleep(60)  # 1 daqiqa kutish

            # 13:00 - Tushlik eslatmasi
            elif self._is_time_match(current_time, self.lunch_time):
                await self._lunch_check()
                await asyncio.sleep(60)

            # 18:00 - Kechki tekshiruv
            elif self._is_time_match(current_time, self.evening_time):
                await self._evening_routine()
                await asyncio.sleep(60)

            # Har 15 daqiqada ogohlantirishlarni tekshirish
            await self._check_warnings()

            await asyncio.sleep(60)  # Har daqiqa tekshirish

    def stop(self):
        """Tsiklni to'xtatish"""
        self.is_running = False
        print("🛑 [DAILY ENFORCER] Stopped")


# Singleton
_enforcer: Optional[DailyEnforcer] = None


def get_daily_enforcer() -> DailyEnforcer:
    """Global enforcer instance"""
    global _enforcer
    if getattr(app_ctx, "enforcer", None) is not None:
        return app_ctx.enforcer
    if _enforcer is None:
        _enforcer = DailyEnforcer()
        app_ctx.enforcer = _enforcer
    return _enforcer


# Demo uchun team setup
async def setup_jon_branding_team():
    """Jon.Branding jamoasini sozlash"""
    enforcer = get_daily_enforcer()

    # Hunter
    enforcer.register_team_member(
        user_id="hunter_001", name="Diyor", role=Role.HUNTER, telegram_id="123456789"
    )

    # Setter
    enforcer.register_team_member(
        user_id="setter_001", name="Malika", role=Role.SETTER, telegram_id="987654321"
    )

    # Closer
    enforcer.register_team_member(
        user_id="closer_001", name="Jasur", role=Role.CLOSER, telegram_id="111222333"
    )

    # PM
    enforcer.register_team_member(
        user_id="pm_001",
        name="Dilshod",
        role=Role.PROJECT_MANAGER,
        telegram_id="444555666",
    )

    # Designer
    enforcer.register_team_member(
        user_id="designer_001",
        name="Nilufar",
        role=Role.DESIGNER,
        telegram_id="777888999",
    )

    print("✅ Jon.Branding team registered:")
    for uid, member in enforcer.team_members.items():
        print(f"   - {member['name']} ({member['role'].value})")

    return enforcer
