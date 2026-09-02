"""
User command handlers for workflow telegram bot (/start, /mytasks, /status, /help).
"""
from __future__ import annotations

import logging
from datetime import datetime

from src.services.core.workflow_engine.models import Role, TaskStatus

logger = logging.getLogger("WorkflowTelegramBot")


class UserCommandsMixin:
    """Handles standard user commands for task tracking and progress reporting."""

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
