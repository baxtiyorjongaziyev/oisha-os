"""
Workflow Telegram Bot - Jamoa uchun qat'iy nazorat bot
Jon.Branding - Har bir qadam nazorat ostida!
"""

from __future__ import annotations

from typing import Optional
from datetime import datetime

from src.services.core.mandatory_workflow import (
    get_mandatory_workflow,
    Role,
    TaskStatus,
)
from src.services.core.daily_enforcer import get_daily_enforcer

# This would be python-telegram-bot or aiogram in production
# For now, we'll create the interface


class WorkflowTelegramBot:
    """
    Telegram bot for mandatory workflow management

    Commands:
    /start - Ro'yxatdan o'tish
    /my_tasks - Mening vazifalarim
    /start_task [id] - Vazifani boshlash
    /complete_task [id] [evidence] - Vazifani yakunlash
    /status - Mening statusim
    /report - Kunlik hisobot
    /help - Yordam

    Admin commands:
    /admin_panel - Admin paneli
    /team_status - Jamoa statusi
    /block_user [id] - Foydalanuvchini bloklash
    /unblock_user [id] - Blokdan chiqarish
    /assign_task [user] [task] - Vazifa berish
    /broadcast [message] - Jamoaga xabar
    """

    def __init__(self):
        self.workflow = get_mandatory_workflow()
        self.enforcer = get_daily_enforcer()
        self.admins = []  # Admin telegram IDs

    async def handle_command(
        self, user_id: str, command: str, args: list, is_admin: bool = False
    ) -> str:
        """Komandani qayta ishlash"""

        # User commands
        if command == "start":
            return await self._cmd_start(user_id, args)

        elif command == "my_tasks":
            return await self._cmd_my_tasks(user_id)

        elif command == "start_task":
            return await self._cmd_start_task(user_id, args)

        elif command == "complete_task":
            return await self._cmd_complete_task(user_id, args)

        elif command == "status":
            return await self._cmd_status(user_id)

        elif command == "report":
            return await self._cmd_report(user_id)

        elif command == "help":
            return await self._cmd_help(is_admin)

        # Admin commands
        elif is_admin:
            if command == "admin_panel":
                return await self._cmd_admin_panel()

            elif command == "team_status":
                return await self._cmd_team_status()

            elif command == "block_user":
                return await self._cmd_block_user(args)

            elif command == "unblock_user":
                return await self._cmd_unblock_user(args)

            elif command == "broadcast":
                return await self._cmd_broadcast(args)

            elif command == "force_morning":
                await self.enforcer._morning_routine()
                return "✅ Ertalabki rejim qo'lda ishga tushirildi"

            elif command == "force_evening":
                await self.enforcer._evening_routine()
                return "✅ Kechki rejim qo'lda ishga tushirildi"

        return "❌ Unknown command. Use /help"

    async def _cmd_start(self, user_id: str, args: list) -> str:
        """/start komandasi"""
        if len(args) < 2:
            return (
                "👋 Salom! Jon.Branding Workflow Botiga xush kelibsiz!\n\n"
                "Ro'yxatdan o'tish uchun:\n"
                "/start [ism] [rol]\n\n"
                "Rollar:\n"
                "- hunter (Lead ovlash)\n"
                "- setter (Uchrashuv belgilash)\n"
                "- closer (Bitim yopish)\n"
                "- pm (Loyiha boshqaruvchi)\n"
                "- designer (Dizayner)\n"
                "- developer (Dasturchi)\n"
                "- copywriter (Matn yozuvchi)"
            )

        name = args[0]
        role_str = args[1].lower()

        role_map = {
            "hunter": Role.HUNTER,
            "setter": Role.SETTER,
            "closer": Role.CLOSER,
            "pm": Role.PROJECT_MANAGER,
            "designer": Role.DESIGNER,
            "developer": Role.DEVELOPER,
            "copywriter": Role.COPYWRITER,
        }

        role = role_map.get(role_str)
        if not role:
            return "❌ Noto'g'ri rol. /help dan ko'ring"

        # Register user
        self.enforcer.register_team_member(
            user_id=user_id, name=name, role=role, telegram_id=user_id
        )

        return (
            f"✅ {name}, siz muvaffaqiyatli ro'yxatdan o'tdingiz!\n"
            f"Rolingiz: {role.value.upper()}\n\n"
            f"⚠️ DIQQAT: Bu bot sizni qat'iy nazorat qiladi!\n"
            f"Har bir vazifa majburiy bajarilishi kerak.\n\n"
            f"📋 Ertalabki vazifalar 08:30 da beriladi.\n"
            f"⏰ Kechki tekshiruv 18:00 da.\n\n"
            f"Buyruqlar:\n"
            f"/my_tasks - Vazifalarim\n"
            f"/status - Statusim\n"
            f"/help - Barcha buyruqlar"
        )

    async def _cmd_my_tasks(self, user_id: str) -> str:
        """/my_tasks komandasi"""
        status = self.workflow.get_user_status(user_id)

        if status["is_blocked"]:
            return (
                f"🚫 SIZ BLOKLANDINGIZ!\n"
                f"Sababi: {status['block_reason']}\n\n"
                f"📞 Direktor bilan bog'laning."
            )

        # Get active tasks
        tasks = [
            task
            for task in self.workflow.active_tasks.values()
            if task.user_id == user_id
        ]

        if not tasks:
            return (
                "✅ Sizda hozircha faol vazifalar yo'q!\n\n"
                "Ertalabki vazifalar 08:30 da beriladi."
            )

        lines = [f"📋 SIZNING VAZIFALARINGIZ ({len(tasks)} ta)\n" + "=" * 40]

        for i, task in enumerate(tasks, 1):
            status_emoji = {
                TaskStatus.MANDATORY: "🔴",
                TaskStatus.IN_PROGRESS: "🟡",
                TaskStatus.BLOCKED: "🚫",
                TaskStatus.PENDING: "⚪",
            }.get(task.status, "⚪")

            lines.append(
                f"{i}. {status_emoji} {task.step.name}\n"
                f"   ⏱️ {task.step.estimated_time} daqiqa\n"
                f"   📝 {task.step.description[:50]}..."
            )

            if task.status == TaskStatus.BLOCKED:
                lines.append(f"   🚫 Bloklangan: {task.blocked_reason}")

        lines.extend(
            [
                "=" * 40,
                "Boshlash: /start_task [nomer]",
                "Yakunlash: /complete_task [nomer] [izoh]",
            ]
        )

        return "\n".join(lines)

    async def _cmd_start_task(self, user_id: str, args: list) -> str:
        """/start_task komandasi"""
        if not args:
            return "❌ Vazifa raqamini kiriting: /start_task 1"

        try:
            task_num = int(args[0]) - 1
        except ValueError:
            return "❌ Noto'g'ri raqam"

        # Get user's tasks
        tasks = [
            task
            for task in self.workflow.active_tasks.values()
            if task.user_id == user_id
        ]

        if task_num < 0 or task_num >= len(tasks):
            return f"❌ Vazifa topilmadi. Sizda {len(tasks)} ta vazifa bor."

        task = tasks[task_num]

        if task.status == TaskStatus.BLOCKED:
            return (
                f"🚫 Bu vazifa bloklangan!\n"
                f"Sababi: {task.blocked_reason}\n\n"
                f"Avval oldingi vazifani bajaring."
            )

        success = self.workflow.start_task(task.id, user_id)

        if success:
            return (
                f"🚀 '{task.step.name}' boshlandi!\n"
                f"⏱️ Taxminiy vaqt: {task.step.estimated_time} daqiqa\n\n"
                f"Yakunlaganda: /complete_task {task_num + 1} [natija]"
            )
        else:
            return "❌ Vazifani boshlash mumkin emas"

    async def _cmd_complete_task(self, user_id: str, args: list) -> str:
        """/complete_task komandasi"""
        if len(args) < 1:
            return "❌ Format: /complete_task [nomer] [izoh yoki rasm]"

        try:
            task_num = int(args[0]) - 1
        except ValueError:
            return "❌ Noto'g'ri raqam"

        evidence = " ".join(args[1:]) if len(args) > 1 else "Bajarildi"

        # Get user's tasks
        tasks = [
            task
            for task in self.workflow.active_tasks.values()
            if task.user_id == user_id
        ]

        if task_num < 0 or task_num >= len(tasks):
            return "❌ Vazifa topilmadi"

        task = tasks[task_num]

        result = self.workflow.complete_task(
            task.id,
            user_id,
            {"note": evidence, "completed_at": datetime.now().isoformat()},
        )

        if result["success"]:
            response = [
                f"✅ '{task.step.name}' bajarildi!",
                f"📝 Izoh: {evidence[:50]}...",
            ]

            # If unblocked tasks
            if result.get("unblocked_tasks"):
                response.append(
                    f"\n🔓 {len(result['unblocked_tasks'])} ta yangi vazifa ochildi!"
                )

            # Next step
            next_step = result.get("next_step")
            if next_step:
                response.append(f"\n➡️ Keyingi vazifa: {next_step['name']}")
            else:
                response.append("\n🎉 Barcha vazifalar bajarildi!")

            return "\n".join(response)
        else:
            return f"❌ Xatolik: {result.get('error', 'Unknown')}"

    async def _cmd_status(self, user_id: str) -> str:
        """/status komandasi"""
        status = self.workflow.get_user_status(user_id)

        member = self.enforcer.team_members.get(user_id, {})
        name = member.get("name", "Noma'lum")
        role = member.get("role", Role.HUNTER)

        lines = [
            f"📊 {name} - STATUS",
            f"Rol: {role.value.upper() if isinstance(role, Role) else role}",
            "=" * 40,
        ]

        if status["is_blocked"]:
            lines.extend(
                [
                    "",
                    "🚫 SIZ BLOKLANDINGIZ!",
                    f"Sababi: {status['block_reason']}",
                    "",
                    "📞 Direktor bilan bog'laning!",
                ]
            )
        else:
            lines.extend(
                [
                    f"✅ Bugun bajarildi: {status['completed_today']}",
                    f"⏳ Faol vazifalar: {status['active_tasks']}",
                    f"🔴 Majburiy: {status['mandatory_pending']}",
                    f"🚫 Bloklangan: {status['blocked_tasks']}",
                    "",
                ]
            )

            if status.get("next_mandatory"):
                lines.append("📋 Keyingi vazifa:")
                lines.append(f"   {status['next_mandatory']['name']}")
                lines.append(
                    f"   ⏱️ {status['next_mandatory']['estimated_minutes']} daqiqa"
                )

            if member.get("streak_days", 0) > 0:
                lines.extend(
                    [
                        "",
                        f"🔥 Streak: {member['streak_days']} kun!",
                        f"📈 Jami bajarildi: {member.get('total_completed', 0)}",
                    ]
                )

        return "\n".join(lines)

    async def _cmd_report(self, user_id: str) -> str:
        """/report komandasi"""
        report = self.workflow.get_daily_report()

        member = self.enforcer.team_members.get(user_id, {})
        name = member.get("name", "Noma'lum")

        lines = [f"📈 {name} - KUNLIK HISOBOT", f"Sana: {report['date']}", "=" * 40, ""]

        # Check if user is top performer
        top_performers = report.get("top_performers", [])
        user_in_top = any(p.get("user_id") == user_id for p in top_performers)

        if user_in_top:
            lines.append("🏆 Siz bugungi TOP bajaruvchilar orasidasiz!")
            lines.append("")

        # Show by role
        by_role = report.get("by_role", {})
        user_role = member.get("role", "unknown")
        role_value = user_role.value if isinstance(user_role, Role) else user_role

        if role_value in by_role:
            lines.append(f"📊 Sizning rolingiz ({role_value}):")
            lines.append(f"   Bugun bajarildi: {by_role[role_value]} ta vazifa")
            lines.append("")

        # Violations
        violations = report.get("violations", [])
        user_violation = next(
            (v for v in violations if v.get("user_id") == user_id), None
        )

        if user_violation:
            lines.append("⚠️ OGohlantirish:")
            lines.append(f"   {user_violation.get('reason', 'Qoida buzilishi')}")
        else:
            lines.append("✅ Bugun qoidabuzarliklar yo'q!")

        lines.extend(["", f"🔥 Sizning streak: {member.get('streak_days', 0)} kun"])

        return "\n".join(lines)

    async def _cmd_help(self, is_admin: bool) -> str:
        """/help komandasi"""
        lines = [
            "📚 JON.BRANDING WORKFLOW BOT",
            "=" * 40,
            "",
            "👤 FOYDALANUVCHI BUYRUQLARI:",
            "/start [ism] [rol] - Ro'yxatdan o'tish",
            "/my_tasks - Vazifalarimni ko'rish",
            "/start_task [nomer] - Vazifani boshlash",
            "/complete_task [nomer] [izoh] - Vazifani yakunlash",
            "/status - Mening statusim",
            "/report - Kunlik hisobot",
            "/help - Bu yordam",
            "",
            "⚠️ QOIDALAR:",
            "• Har bir vazifa majburiy bajarilishi kerak",
            "• Vazifa 4 soatdan keyin bajarilmasa - BLOK",
            "• Ertalabki vazifalar 08:30 da",
            "• Kechki tekshiruv 18:00 da",
            "",
        ]

        if is_admin:
            lines.extend(
                [
                    "👑 ADMIN BUYRUQLARI:",
                    "/admin_panel - Admin paneli",
                    "/team_status - Jamoa statusi",
                    "/block_user [id] - Bloklash",
                    "/unblock_user [id] - Blokdan chiqarish",
                    "/broadcast [xabar] - Jamoaga xabar",
                    "/force_morning - Ertalabki rejim",
                    "/force_evening - Kechki rejim",
                ]
            )

        return "\n".join(lines)

    # Admin commands
    async def _cmd_admin_panel(self) -> str:
        """Admin paneli"""
        report = self.workflow.get_daily_report()

        lines = [
            "👑 ADMIN PANEL",
            f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "=" * 40,
            "",
            "📊 JAMOA STATISTIKASI:",
            f"Jami a'zolar: {len(self.enforcer.team_members)}",
            f"Faol: {report['active_users']}",
            f"Bloklangan: {report['blocked_users']}",
            "",
            "📈 BUGUNGI NATIJALAR:",
            f"Bajarildi: {report['completed_tasks']} ✅",
            f"Muddati o'tgan: {report['overdue_tasks']} ⏰",
            "",
            "Rollar bo'yicha:",
        ]

        for role, count in report.get("by_role", {}).items():
            lines.append(f"   {role}: {count} ta")

        if report.get("violations"):
            lines.extend(["", f"🚨 QOIDABUZARLAR: {len(report['violations'])} ta"])

        lines.extend(
            [
                "",
                "Buyruqlar:",
                "/team_status - Batafsil status",
                "/force_morning - Ertalabki rejim",
                "/force_evening - Kechki rejim",
            ]
        )

        return "\n".join(lines)

    async def _cmd_team_status(self) -> str:
        """Jamoa statusi"""
        lines = ["👥 JAMOA STATUSI\n" + "=" * 40]

        for user_id, member in self.enforcer.team_members.items():
            status = self.workflow.get_user_status(user_id)

            emoji = "🚫" if status["is_blocked"] else "✅"
            role = member.get("role", Role.HUNTER)
            role_str = role.value if isinstance(role, Role) else role

            lines.append(
                f"{emoji} {member.get('name', 'N/A')} ({role_str})\n"
                f"   Bajarildi: {status['completed_today']} ✅\n"
                f"   Qoldi: {status['mandatory_pending']} 🔴"
            )

        return "\n".join(lines)

    async def _cmd_block_user(self, args: list) -> str:
        """Foydalanuvchini bloklash"""
        if not args:
            return "❌ Format: /block_user [user_id] [sabab]"

        user_id = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else "Qoida buzilishi"

        self.workflow.block_user(user_id, reason)

        member = self.enforcer.team_members.get(user_id, {})
        name = member.get("name", user_id)

        return f"🚫 {name} bloklandi!\nSababi: {reason}"

    async def _cmd_unblock_user(self, args: list) -> str:
        """Foydalanuvchini blokdan chiqarish"""
        if not args:
            return "❌ Format: /unblock_user [user_id]"

        user_id = args[0]

        if user_id in self.workflow.blocked_users:
            del self.workflow.blocked_users[user_id]

            # Unblock tasks
            for task_id, task in self.workflow.active_tasks.items():
                if task.user_id == user_id and task.blocked_by == "admin":
                    task.status = TaskStatus.MANDATORY
                    task.blocked_reason = None

            member = self.enforcer.team_members.get(user_id, {})
            name = member.get("name", user_id)

            return f"✅ {name} blokdan chiqarildi!"

        return "❌ Foydalanuvchi topilmadi"

    async def _cmd_broadcast(self, args: list) -> str:
        """Jamoaga xabar yuborish"""
        if not args:
            return "❌ Format: /broadcast [xabar]"

        message = " ".join(args)

        # Count would be actual sent messages
        count = len(self.enforcer.team_members)

        return f"📢 Xabar yuborildi!\nQabul qiluvchilar: {count} ta\nXabar: {message[:50]}..."


# Singleton
_bot: Optional[WorkflowTelegramBot] = None


def get_workflow_bot() -> WorkflowTelegramBot:
    """Global bot instance"""
    global _bot
    if _bot is None:
        _bot = WorkflowTelegramBot()
    return _bot
