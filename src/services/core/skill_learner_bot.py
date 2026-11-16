"""Skill Learner Telegram integratsiyasi (Aiogram inline tugmalar va AdminBot buyruqlari)."""
from __future__ import annotations

import asyncio
import html as std_html
import logging
import re
from typing import Any, Dict, List, Optional

from src.services.core.adaptive_learning import reset_adaptive_cache, resolve_runtime_db

logger = logging.getLogger(__name__)

_SKILL_CMD_RE = re.compile(
    r"^/(skills|skill_ok|skill_no)(?:@[A-Za-z0-9_]+)?(?:\s+(\d+))?\s*$"
)


def skill_review_buttons(skill_id: int) -> List[List[Dict[str, str]]]:
    return [[
        {"text": "✅ Tasdiqlash", "callback_data": f"skill:ok:{skill_id}"},
        {"text": "❌ Rad etish", "callback_data": f"skill:no:{skill_id}"},
    ]]


async def notify_pending_skills_to_owner(
    skill_ids: List[int],
    db: Any = None,
    client: Any = None,
    bot_runtime: Any = None,
    owner_id: Optional[int] = None,
) -> int:
    """Yangi qazilgan skill qoralamalarini tugmalar bilan Ownerʼga yuboradi."""
    if not skill_ids:
        return 0
    from src.services.core.skill_learner import _conn, _get_skill, format_skill_card

    conn = await _conn(resolve_runtime_db(db))
    if conn is None:
        return 0

    sent = 0
    for skill_id in skill_ids:
        skill = await _get_skill(conn, int(skill_id))
        if not skill:
            continue
        card = format_skill_card(skill)
        if bot_runtime is not None and owner_id:
            try:
                await bot_runtime.send_message(
                    int(owner_id),
                    std_html.escape(card),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    buttons=skill_review_buttons(int(skill_id)),
                )
                sent += 1
                continue
            except Exception as exc:
                logger.warning("[SKILL_LEARNER] bot_runtime notify failed: %s", exc)
        if client is not None:
            await client.send_message("me", card)
            sent += 1
    return sent


async def run_skill_learner_loop(
    client: Any = None,
    db: Any = None,
    bot_runtime: Any = None,
    owner_id: Optional[int] = None,
) -> None:
    """Davriy skill qazib olish va Ownerʼga tasdiq kartasini yuborish sikli."""
    from src.services.core.skill_learner import MINE_INTERVAL_SECONDS, is_enabled, mine_skills

    if not is_enabled():
        logger.info("[SKILL_LEARNER] Oʻchirilgan (ENABLE_SKILL_LEARNER=0)")
        return
    await asyncio.sleep(120)
    while True:
        try:
            new_ids = await mine_skills(db)
            if new_ids:
                await notify_pending_skills_to_owner(
                    new_ids, db=db, client=client, bot_runtime=bot_runtime, owner_id=owner_id
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[SKILL_LEARNER] Loop xatosi: %s", exc, exc_info=True)
        await asyncio.sleep(MINE_INTERVAL_SECONDS)


async def handle_skill_callback(
    event: Any, data: str, owner_id: int, db: Any = None
) -> bool:
    """`skill:ok:<id>` va `skill:no:<id>` inline tugmalarini qayta ishlaydi."""
    if not data.startswith("skill:"):
        return False
    if int(getattr(event, "sender_id", 0) or 0) != int(owner_id):
        await event.answer("Bu qarorni faqat owner bera oladi.", alert=True)
        return True
    parts = data.split(":", 2)
    if len(parts) != 3 or parts[1] not in {"ok", "no"} or not parts[2].isdigit():
        await event.answer("Notoʻgʻri skill buyrugʻi.", alert=True)
        return True

    approve = parts[1] == "ok"
    skill_id = int(parts[2])
    from src.services.core.skill_learner import decide_skill

    skill = await decide_skill(skill_id, approve=approve, db=resolve_runtime_db(db))
    if skill is None:
        await event.answer(f"Skill #{skill_id} topilmadi.", alert=True)
        return True

    reset_adaptive_cache()
    badge = (
        f"✅ Skill #{skill_id} tasdiqlandi: {skill['name']}"
        if approve
        else f"❌ Skill #{skill_id} rad etildi: {skill['name']}"
    )
    await event.answer("Saqlandi.", alert=False)
    msg = getattr(event, "message", None)
    raw_text = str(getattr(msg, "raw_text", None) or getattr(msg, "message", None) or "")
    try:
        await event.edit(
            f"{std_html.escape(raw_text)}\n\n<b>{std_html.escape(badge)}</b>",
            parse_mode="html",
            buttons=None,
        )
    except Exception as exc:
        logger.debug("[SKILL_LEARNER] Card edit failed: %s", exc)
    return True


async def handle_admin_skill_command(
    event: Any, owner_id: int, db: Any = None, bot_runtime: Any = None
) -> bool:
    """AdminBot ichida `/skills`, `/skill_ok <id>`, `/skill_no <id>` buyruqlari."""
    raw_text = (getattr(event, "raw_text", None) or getattr(event, "text", None) or "").strip()
    match = _SKILL_CMD_RE.match(raw_text)
    if not match or int(getattr(event, "sender_id", 0) or 0) != int(owner_id):
        return False

    cmd, raw_id = match.group(1), match.group(2)
    target_db = resolve_runtime_db(db)
    from src.services.core.skill_learner import decide_skill, format_skill_card, list_skills

    if cmd == "skills":
        return await _send_skill_list_and_cards(event, owner_id, target_db, bot_runtime, list_skills, format_skill_card)
    if not raw_id:
        await event.respond(f"Foydalanish: /{cmd} <id>")
        return True

    approve = cmd == "skill_ok"
    skill = await decide_skill(int(raw_id), approve=approve, db=target_db)
    if skill is None:
        await event.respond(f"Skill #{raw_id} topilmadi.")
        return True
    reset_adaptive_cache()
    status_word = "faollashtirildi" if approve else "rad etildi"
    await event.respond(f"{'✅' if approve else '❌'} Skill #{raw_id} {status_word}: {skill['name']}")
    return True


async def _send_skill_list_and_cards(
    event: Any,
    owner_id: int,
    target_db: Any,
    bot_runtime: Any,
    list_skills: Any,
    format_skill_card: Any,
) -> bool:
    skills = await list_skills(target_db)
    if not skills:
        await event.respond("🧠 Hali skill oʻrganilmagan.")
        return True
    icons = {"pending": "⏳", "active": "✅", "rejected": "❌"}
    lines = [f"{icons.get(s['status'], '•')} #{s['id']} {s['name']}" for s in skills[-20:]]
    await event.respond("🧠 Skilllar roʻyxati:\n" + "\n".join(lines))
    for skill in [s for s in skills if s["status"] == "pending"][-3:]:
        buttons = skill_review_buttons(int(skill["id"]))
        if bot_runtime is not None and owner_id:
            await bot_runtime.send_message(
                int(owner_id),
                std_html.escape(format_skill_card(skill)),
                parse_mode="HTML",
                buttons=buttons,
            )
        else:
            await event.respond(format_skill_card(skill), buttons=buttons)
    return True
