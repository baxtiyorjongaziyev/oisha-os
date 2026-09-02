"""
Morning, lunch, evening routine checks, warning escalation, and formatting mixin.
"""
from __future__ import annotations

import logging
from datetime import datetime, time

from src.services.core.workflow_engine.models import TaskStatus

logger = logging.getLogger("DailyEnforcer")


class RoutinesMixin:
    """Handles daily checkpoint evaluation and warning calculations."""

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
