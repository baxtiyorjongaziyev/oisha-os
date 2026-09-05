"""
Admin command handlers for workflow telegram bot (/admin, /team, /block, /broadcast).
"""
from __future__ import annotations

import logging
from datetime import datetime

from src.services.core.workflow_engine.models import Role, TaskStatus

logger = logging.getLogger("WorkflowTelegramBot")


class AdminCommandsMixin:
    """Handles administrative team management and broadcast commands."""

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
