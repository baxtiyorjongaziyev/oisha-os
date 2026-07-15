"""Self-improvement proposal commands (owner only, Saved Messages)."""
from __future__ import annotations

import logging

from src.commands import register_command

logger = logging.getLogger(__name__)


def _get_agent(ctx):
    from src.services.core.self_improvement_agent import SelfImprovementAgent

    msg_controller = ctx["msg_controller"]
    settings = ctx["settings"]
    return SelfImprovementAgent(
        db=msg_controller.db, gemini_api_key=settings.GEMINI_API_KEY
    )


@register_command("/improve_approve")
async def cmd_improve_approve(event, **ctx):
    await _set_status(event, ctx, "approved", "✅ Taklif tasdiqlandi")


@register_command("/improve_reject")
async def cmd_improve_reject(event, **ctx):
    await _set_status(event, ctx, "rejected", "🚫 Taklif rad etildi")


@register_command("/improve_run")
async def cmd_improve_run(event, **ctx):
    """Self-improvement tsiklini qo'lda ishga tushirish."""
    await event.respond("⏳ Oisha o'z ishini tahlil qilmoqda...")
    try:
        agent = _get_agent(ctx)
        report = await agent.run_cycle()
        if report:
            await event.respond(report)
        else:
            await event.respond(
                "✅ Tahlil tugadi — hozircha yangi rivojlanish taklifi yo'q."
            )
    except Exception as e:
        logger.error(f"[COMMAND] /improve_run error: {e}", exc_info=True)
        await event.respond(f"❌ Tahlil xatoligi: {e}")


@register_command("/improve")
async def cmd_improve_list(event, **ctx):
    """Ochiq rivojlanish takliflarini ko'rsatish."""
    try:
        agent = _get_agent(ctx)
        await agent.ensure_tables()
        proposals = await agent.get_open_proposals()
        if not proposals:
            await event.respond(
                "📭 Ochiq takliflar yo'q. Yangi tahlil: /improve_run"
            )
            return

        from src.services.core.self_improvement_agent import SelfImprovementAgent

        lines = [SelfImprovementAgent.format_report(proposals), ""]
        lines.append("ID lar: " + ", ".join(str(p["id"]) for p in proposals))
        await event.respond("\n".join(lines))
    except Exception as e:
        logger.error(f"[COMMAND] /improve error: {e}", exc_info=True)
        await event.respond(f"❌ Xatolik: {e}")


async def _set_status(event, ctx, status: str, ok_msg: str):
    parts = event.message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await event.respond(f"Foydalanish: {parts[0]} <id>")
        return
    proposal_id = int(parts[1])
    try:
        agent = _get_agent(ctx)
        await agent.ensure_tables()
        ok = await agent.update_proposal_status(proposal_id, status)
        if ok:
            await event.respond(f"{ok_msg} (#{proposal_id})")
        else:
            await event.respond("❌ Noto'g'ri status")
    except Exception as e:
        logger.error(f"[COMMAND] improvement status error: {e}", exc_info=True)
        await event.respond(f"❌ Xatolik: {e}")
