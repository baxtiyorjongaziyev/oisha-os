"""
Daily Enforcer - Kunlik majburiy vazifalarni nazorat qilish
Jon.Branding - Har kuni, har soat, har daqiqa nazorat!
"""

from __future__ import annotations

import asyncio
from datetime import datetime, time
from typing import Any, Dict, Optional

from src.services.core.mandatory_workflow import (
    get_mandatory_workflow,
    Role,
    TaskStatus,
)


class DailyEnforcer:
    """
    Kunlik qat'iy nazorat tizimi

    Vazifalari:
    - Har kuni ertalab vazifalarni taqsimlash
    - Kechqurun tekshirish
    - O'tgan vazifalar uchun ogohlantirish
    - Blokirovka qilish
    """

    def __init__(self):
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

    def _is_time_match(
        self, current: time, target: time, tolerance_minutes: int = 1
    ) -> bool:
        """Vaqtni solishtirish"""
        current_minutes = current.hour * 60 + current.minute
        target_minutes = target.hour * 60 + target.minute
        return abs(current_minutes - target_minutes) <= tolerance_minutes

    async def _morning_routine(self):
        """Ertalabki rejim - Vazifalarni taqsimlash"""
        print(f"🌅 [DAILY ENFORCER] Morning routine started at {datetime.now()}")

        for user_id, member in self.team_members.items():
            if not member["is_active"]:
                continue

            # Vazifalarni taqsimlash
            tasks = self.workflow.assign_daily_tasks(
                user_id=user_id, user_name=member["name"], role=member["role"]
            )

            # Birinchi vazifani olish
            first_task = None
            for task in tasks:
                if task.status == TaskStatus.MANDATORY:
                    first_task = task
                    break

            # Telegram xabari
            message = self._format_morning_message(
                member["name"],
                len(tasks),
                first_task.step.name if first_task else "Boshlash",
            )

            await self._send_notification(
                user_id=member.get("telegram_id"), message=message, priority="high"
            )

            print(f"   📋 {member['name']}: {len(tasks)} tasks assigned")

        print("✅ [DAILY ENFORCER] Morning routine completed")

    async def _lunch_check(self):
        """Tushlik tekshiruvi - Yarim kun natijalari"""
        print(f"🍽️ [DAILY ENFORCER] Lunch check at {datetime.now()}")

        for user_id, member in self.team_members.items():
            status = self.workflow.get_user_status(user_id)

            # Agar kamida 50% bajarilmagan bo'lsa
            total = status["active_tasks"] + status["completed_today"]
            if total > 0 and status["completed_today"] / total < 0.5:
                message = (
                    f"⚠️ {member['name']}, tushlik vaqti!\n"
                    f"Bugun faqat {status['completed_today']}/{total} vazifa bajarildi.\n"
                    f"Keyingisi: {status['next_mandatory']['name'] if status['next_mandatory'] else 'Yoq'}"
                )

                await self._send_notification(
                    user_id=member.get("telegram_id"),
                    message=message,
                    priority="medium",
                )

    async def _evening_routine(self):
        """Kechki tekshiruv - Kun yakuni"""
        print(f"🌙 [DAILY ENFORCER] Evening routine at {datetime.now()}")

        report_lines = ["📊 KUNLIK HISOBOT\n" + "=" * 40]
        total_completed = 0
        total_pending = 0
        violations = []

        for user_id, member in self.team_members.items():
            status = self.workflow.get_user_status(user_id)

            completed = status["completed_today"]
            pending = status["mandatory_pending"] + status["blocked_tasks"]

            total_completed += completed
            total_pending += pending

            # Streak yangilash
            if pending == 0:
                member["streak_days"] += 1
                member["total_completed"] += completed
            else:
                member["streak_days"] = 0  # Reset streak
                violations.append(
                    {
                        "name": member["name"],
                        "role": member["role"].value,
                        "pending": pending,
                    }
                )

            # Shaxsiy hisobot
            emoji = "🔥" if pending == 0 else "⚠️"
            report_lines.append(
                f"{emoji} {member['name']} ({member['role'].value}): "
                f"{completed} ✅ | {pending} ⏳ | Streak: {member['streak_days']} kun"
            )

            # Foydalanuvchiga xabar
            if pending > 0:
                message = (
                    f"🌙 {member['name']}, ish kuni tugadi!\n"
                    f"Bajarildi: {completed} ✅\n"
                    f"Bajarilmadi: {pending} ❌\n"
                    f"Ertaga davom etamiz..."
                )
            else:
                message = (
                    f"🎉 {member['name']}, ajoyib!\n"
                    f"Bugun barcha {completed} vazifani bajardingiz!\n"
                    f"Streak: {member['streak_days']} kun 🔥"
                )

            await self._send_notification(
                user_id=member.get("telegram_id"),
                message=message,
                priority="high" if pending > 0 else "normal",
            )

        # Jamoaviy hisobot
        report_lines.extend(
            [
                "=" * 40,
                f"Jami: {total_completed} ✅ | {total_pending} ⏳",
                f"Qoidabuzarlar: {len(violations)} ta",
            ]
        )

        if violations:
            report_lines.append("\n⚠️ Ertaga bloklanadilar:")
            for v in violations[:5]:
                report_lines.append(f"   - {v['name']}: {v['pending']} vazifa")

        # Direktorga yuborish
        await self._send_to_director("\n".join(report_lines))

        print("✅ [DAILY ENFORCER] Evening routine completed")
        print(f"   📊 Total: {total_completed} completed, {total_pending} pending")

    async def _check_warnings(self):
        """Ogohlantirishlarni tekshirish"""
        now = datetime.now()

        for user_id, member in self.team_members.items():
            status = self.workflow.get_user_status(user_id)

            # Agar foydalanuvchi bloklangan bo'lsa
            if status["is_blocked"]:
                continue

            # Aktiv vazifalarni tekshirish
            for task_id, task in self.workflow.active_tasks.items():
                if task.user_id != user_id:
                    continue

                if task.status != TaskStatus.MANDATORY:
                    continue

                # Qancha vaqt o'tdi?
                assigned_time = task.assigned_at
                elapsed = now - assigned_time
                elapsed_hours = elapsed.total_seconds() / 3600

                # 2 soatdan keyin ogohlantirish
                if (
                    elapsed_hours >= self.warning_hours
                    and elapsed_hours < self.block_hours
                ):
                    if not hasattr(task, "_warning_sent"):
                        message = (
                            f"⚠️ {member['name']}!\n"
                            f"'{task.step.name}' vazifasi {int(elapsed_hours)} soatdan beri kutmoqda!\n"
                            f"⏰ Yana {self.block_hours - int(elapsed_hours)} soat vaqt bor."
                        )
                        await self._send_notification(
                            user_id=member.get("telegram_id"),
                            message=message,
                            priority="high",
                        )
                        task._warning_sent = True

                # 4 soatdan keyin bloklash
                elif elapsed_hours >= self.block_hours:
                    # Foydalanuvchini bloklash
                    self.workflow.block_user(
                        user_id,
                        f"'{task.step.name}' vazifasi {int(elapsed_hours)} soat bajarilmadi",
                    )

                    message = (
                        f"🚫 {member['name']}, SIZ BLOKLANDINGIZ!\n"
                        f"'{task.step.name}' vazifasi bajarilmagan.\n"
                        f"📞 Direktor bilan bog'laning: +998 XX XXX XX XX"
                    )
                    await self._send_notification(
                        user_id=member.get("telegram_id"),
                        message=message,
                        priority="urgent",
                    )

                    # Direktorga xabar
                    await self._send_to_director(
                        f"🚨 {member['name']} ({member['role'].value}) BLOKLANDI!\n"
                        f"Sababi: {task.step.name} vazifasi bajarilmagan"
                    )

    def _format_morning_message(
        self, name: str, task_count: int, first_task: str
    ) -> str:
        """Ertalabki xabar formati"""
        import random

        template = random.choice(self.morning_messages)
        base = template.format(name=name)

        return (
            f"{base}\n\n"
            f"📋 Bugun {task_count} ta majburiy vazifa:\n"
            f"1️⃣ {first_task}\n\n"
            f"⚔️ Boshlash uchun: /start_task\n"
            f"📊 Status: /my_status"
        )

    async def _send_notification(
        self, user_id: Optional[str], message: str, priority: str = "normal"
    ):
        """Xabar yuborish (Telegram)"""
        if not user_id:
            print("   ⚠️ No telegram_id for user")
            return

        # Bu yerda Telegram bot orqali yuborish
        # Hozircha print qilamiz
        print(f"   📨 To {user_id}: {message[:50]}...")

        # Real implementation:
        # await telegram_bot.send_message(user_id, message)

    async def _send_to_director(self, message: str):
        """Direktorga xabar yuborish"""
        print(f"   👔 To Director: {message[:100]}...")
        # await telegram_bot.send_message(DIRECTOR_TELEGRAM_ID, message)

    async def force_check_now(self) -> Dict[str, Any]:
        """Qo'lda tekshirish (admin uchun)"""
        await self._check_warnings()

        results = {}
        for user_id, member in self.team_members.items():
            results[user_id] = self.workflow.get_user_status(user_id)

        return results

    def stop(self):
        """Tsiklni to'xtatish"""
        self.is_running = False
        print("🛑 [DAILY ENFORCER] Stopped")


# Singleton
_enforcer: Optional[DailyEnforcer] = None


def get_daily_enforcer() -> DailyEnforcer:
    """Global enforcer instance"""
    global _enforcer
    if _enforcer is None:
        _enforcer = DailyEnforcer()
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
