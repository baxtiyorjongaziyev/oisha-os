"""
CRM Callback Handlers — Vazifa, Eslatma, CRM callbacklari.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from src.context import app_ctx

logger = logging.getLogger(__name__)


async def task_done_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Vazifa bajarildi callback."""
    query = update.callback_query
    await query.answer("✅ Vazifa bajarildi deb belgilandi!")

    data = query.data  # task_done_123
    task_id = int(data.split("_")[-1])

    try:
        from src.services.crm_integration import get_task_service
        from src.context import app_ctx

        task_service = get_task_service(app_ctx.db)
        result = await get_task_service(app_ctx.db).complete_task(task_id, query.from_user.id)

        if result.get("success"):
            await query.edit_message_text(
                f"✅ Vazifa #{task_id} bajarildi deb belgilandi!",
                reply_markup=None
            )
        else:
            await query.edit_message_text(f"❌ Xatolik: {result.get('error')}")

    except Exception as e:
        logger.error(f"[TASK] Done callback error: {e}")
        await query.edit_message_text("❌ Xatolik yuz berdi")


async def task_snooze_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Vazifa kechiktirish callback."""
    query = update.callback_query
    await query.answer("⏰ Vazifa kechiktirildi!")

    data = query.data  # task_snooze_123
    task_id = int(data.split("_")[-1])

    try:
        from src.services.crm_integration import get_task_service

        task_service = get_task_service(app_ctx.db)
        result = await get_task_service(app_ctx.db).snooze_task(task_id, 60)

        if result.get("success"):
            new_due = result.get("new_due_at")
            await query.edit_message_text(
                f"⏰ Vazifa #{task_id} 1 soat kechiktirildi.\n"
                f"Yangi muddat: {new_due.strftime('%d.%m.%Y %H:%M')}",
                reply_markup=None
            )
        else:
            await query.edit_message_text(f"❌ Xatolik: {result.get('error')}")

    except Exception as e:
        logger.error(f"[TASK] Snooze callback error: {e}")
        await query.edit_message_text("❌ Xatolik yuz berdi")


async def task_list_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Vazifalar ro'yxati callback."""
    query = update.callback_query
    await query.answer()

    try:
        user_id = query.from_user.id

        from src.services.crm_integration import get_task_service
        from src.context import app_ctx

        task_service = get_task_service(app_ctx.db)
        tasks = await get_task_service(app_ctx.db).get_user_tasks(query.from_user.id)

        if not tasks:
            await query.edit_message_text("📝 Sizda faol vazifalar yo'q.")
            return

        pending = [t for t in tasks if t.get("status") == "pending"]
        completed = [t for t in tasks if t.get("status") == "completed"]

        text = f"📋 **VAZIFALAR RO'YXATI** ({len(pending)} faol, {len(completed)} bajarilgan)\n\n"

        if pending:
            text += "📋 **FAOL:**\n"
            for i, task in enumerate(pending[:10], 1):
                due = task.get("due_at")
                due_str = due.strftime("%d.%m %H:%M") if due else "Muddat yo'q"
                text += f"{i}. {task.get('title')} — {due_str}\n"

        await query.edit_message_text(text, parse_mode="md")

    except Exception as e:
        logger.error(f"[TASK] List callback error: {e}")
        await query.edit_message_text("❌ Xatolik yuz berdi")


async def today_tasks_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Bugungi vazifalar callback."""
    query = update.callback_query
    await query.answer()

    try:
        from src.services.crm_integration import get_task_service
        from src.context import app_ctx

        task_service = get_task_service(app_ctx.db)
        tasks = await get_task_service(app_ctx.db).get_today_tasks(query.from_user.id)

        if not tasks:
            await query.edit_message_text("📅 Bugun uchun rejalashtirilgan vazifalar yo'q. Dam oling! ☕")
            return

        lines = ["📅 **BUGUNGI VAZIFALAR**", "━━━━━━━━━━━━━━━━━━━━"]
        for i, task in enumerate(tasks, 1):
            due = task.get("due_at")
            due_str = due.strftime("%H:%M") if due else "Har vaqt"
            status = "✅" if task.get("status") == "completed" else "⏳"
            lines.append(f"{i}. {status} [{due_str}] {task.get('title', 'Vazifa')}")

        text = "\n".join(lines) + "\n\n💡 *Vazifa bajarilganda '✅' tugmasini bosing*"
        await query.edit_message_text(text, parse_mode="md")

    except Exception as e:
        logger.error(f"[TASK] Today tasks error: {e}")
        await query.edit_message_text("❌ Xatolik yuz berdi")


async def overdue_tasks_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Kechikgan vazifalar callback."""
    query = update.callback_query
    await query.answer()

    try:
        from src.services.crm_integration import get_task_service
        from src.context import app_ctx

        task_service = get_task_service(app_ctx.db)
        tasks = await get_task_service(app_ctx.db).get_overdue_tasks(query.from_user.id)

        if not tasks:
            await query.edit_message_text("✅ Kechikgan vazifalar yo'q. Hammasi vaqtida! 👍")
            return

        lines = ["🚨 **KECHIKGAN VAZIFALAR**", "━━━━━━━━━━━━━━━━━━━━"]
        for i, task in enumerate(tasks, 1):
            due = task.get("due_at")
            due_str = due.strftime("%d.%m %H:%M") if due else "Muddat yo'q"
            overdue_hours = int((datetime.now() - task.get("due_at")).total_seconds() / 3600)
            lines.append(f"{i}. 🚨 {task.get('title')} — {due_str} ({overdue_hours}h kechikkan)")

        text = "\n".join(lines) + "\n\n⚠️ *Tezroq bajaring!*"
        await query.edit_message_text(text, parse_mode="md")

    except Exception as e:
        logger.error(f"[TASK] Overdue error: {e}")
        await query.edit_message_text("❌ Xatolik yuz berdi")


async def create_task_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Yangi vazifa yaratish callback."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📝 **YANGI VAZIFA YARATISH**\n\n"
        "Format:\n"
        "`/task <sarlavha> | <sana_va_vaqt> | [tavsif]`\n\n"
        "Misol:\n"
        "`/task Mijoz bilan uchrashuv | 25.12 14:00 | Shartnoma imzolash`\n\n"
        "Sana formati: `KK.OO SS:DD` yoki `bugun 14:00` / `ertaga 10:00`",
        parse_mode="md"
    )


async def process_task_command(event, context) -> bool:
    """/task buyrug'ini qayta ishlash."""
    if not event.message.text or not event.message.text.startswith("/task "):
        return False

    try:
        # Parse: /task Title | 25.12 14:00 | Description
        parts = event.message.text[6:].split("|")
        if len(parts) < 2:
            await event.respond("❌ Format noto'g'ri. Masol: `/task Title | 25.12 14:00 | Desc`", parse_mode="md")
            return True

        title = parts[0].strip()
        due_str = parts[1].strip() if len(parts) > 1 else None
        description = parts[2].strip() if len(parts) > 2 else None

        # Parse date
        due_at = None
        if due_str:
            due_str = due_str.strip().lower()
            if due_str == "bugun":
                due_at = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
            elif due_str == "ertaga":
                due_at = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
            else:
                try:
                    # 25.12 14:00 format
                    due_at = datetime.strptime(due_str, "%d.%m %H:%M")
                    due_at = due_at.replace(year=datetime.now().year)
                    if due_at < datetime.now():
                        due_at = due_at.replace(year=due_at.year + 1)
                except ValueError:
                    try:
                        due_at = datetime.strptime(due_str, "%d.%m.%Y %H:%M")
                    except ValueError:
                        await event.respond("❌ Sana formati noto'g'ri. Masol: `25.12 14:00`")
                        return True

        from src.services.crm_integration import get_task_service
        from src.context import app_ctx

        task_service = get_task_service(app_ctx.db)
        result = await get_task_service(app_ctx.db).create_task(
            user_id=event.sender_id,
            title=title,
            due_at=due_at,
            description=description,
        )

        if result.get("success"):
            due_str = result.get("task_id")
            text = f"✅ Vazifa yaratildi! ID: `{result['task_id']}`"
            if due_at:
                text += f"\n📅 Muddat: {due_at.strftime('%d.%m.%Y %H:%M')}"
            await event.respond(text, parse_mode="md")
        else:
            await event.respond(f"❌ Xatolik: {result.get('error')}")

        return True

    except Exception as e:
        logger.error(f"[TASK] Command error: {e}")
        await event.respond("❌ Xatolik yuz berdi")
        return True