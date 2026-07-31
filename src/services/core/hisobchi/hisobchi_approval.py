"""
Hisobchi Approval — inline keyboard orqali to'lov tasdiqlash.

Flow:
  1. Card bot message arrives → parse → save as "pending"
  2. Send to admin with inline buttons (Biznes/Shaxsiy, Tasdiqlash/Tahrirlash/Rad etish)
  3. Admin clicks button → categorize, learn, confirm
"""
from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Pending approvals: callback_data → {tx_id, category, ownership, merchant, ...}
_pending: Dict[str, Dict[str, Any]] = {}
_pending_edit: Dict[int, str] = {}  # user_id → approve callback_data

# Common categories for quick selection
QUICK_CATEGORIES = [
    "🍽 Taom",
    "🚕 Taksi",
    "🛒 Oziq-ovqat",
    "⛽ Yonilg'i",
    "📱 Aloqa",
    "🏠 Ijara",
    "💰 Maosh",
    "📦 Xarid",
    "🔧 Xizmat",
    "❓ Noma'lum",
]


def _approval_key(tx_id: int, ownership: str) -> str:
    return f"happrove:{tx_id}:{ownership}"


def _edit_key(tx_id: int) -> str:
    return f"hedit:{tx_id}"


def _skip_key(tx_id: int) -> str:
    return f"hskip:{tx_id}"


def _category_key(tx_id: int, category: str) -> str:
    safe_cat = category[:20].replace(":", ";").replace("|", ";")
    return f"hcat:{tx_id}:{safe_cat}"


def _change_owner_key(tx_id: int, current: str) -> str:
    new_owner = "personal" if current == "business" else "business"
    return f"howner:{tx_id}:{new_owner}"


def build_approval_keyboard(tx_id: int, ownership: str = "business"):
    """Telethon Button inline keyboard yaratadi."""
    try:
        from telethon import Button

        owner_label = "🏢 Biznes" if ownership == "business" else "🏠 Shaxsiy"
        owner_cb = _change_owner_key(tx_id, ownership)

        buttons = [
            [
                Button.inline(owner_label, data=owner_cb),
            ],
            [
                Button.inline("✅ Tasdiqlash", data=_approval_key(tx_id, ownership)),
                Button.inline("✏️ Tahrirlash", data=_edit_key(tx_id)),
            ],
            [
                Button.inline("❌ Rad etish", data=_skip_key(tx_id)),
            ],
        ]
        return buttons
    except ImportError:
        return None


def build_category_keyboard(tx_id: int) -> list:
    """Kategoriya tanlash uchun inline keyboard."""
    try:
        from telethon import Button

        buttons = []
        row = []
        for cat in QUICK_CATEGORIES:
            row.append(Button.inline(cat, data=_category_key(tx_id, cat)))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([Button.inline("🔙 Ortga", data=f"hback:{tx_id}")])
        return buttons
    except ImportError:
        return None


def build_approval_message(tx: Any, tx_id: int, ownership: str = "business") -> str:
    """Admin uchun tasdiqlash xabarini formatlaydi."""
    dir_icon = "➖ Chiqim" if tx.direction == "out" else "➕ Kirim"
    card_label = "HUMO" if tx.source_bot == "humo" else "UZCARD"
    owner_label = "🏢 Biznes" if ownership == "business" else "🏠 Shaxsiy"
    question = (
        "Bu to'lov nima uchun ketdi?"
        if tx.direction == "out"
        else "Bu pul nima uchun keldi?"
    )
    balance_line = (
        f"\n💰 Qoldiq: {_fmt_money(tx.balance)} UZS" if tx.balance else ""
    )
    return (
        f"💳 <b>Yangi to'lov #{tx_id}</b>\n\n"
        f"{dir_icon}: <b>{_fmt_money(tx.amount)} UZS</b>\n"
        f"📍 {html.escape(tx.merchant)}\n"
        f"🏦 {card_label} {html.escape(tx.card_suffix)}\n"
        f"🕓 {html.escape(tx.tx_time)}"
        f"{balance_line}\n\n"
        f"📊 {owner_label}\n\n"
        f"❓ <b>{question}</b>\n"
        f"Kategoriyani tanlang yoki javob yozing"
    )


def _fmt_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


async def register_pending(
    tx_id: int,
    tx: Any,
    ownership: str = "business",
    category: Optional[str] = None,
) -> None:
    """Pending approval ro'yxatga qo'shadi."""
    key = _approval_key(tx_id, ownership)
    _pending[key] = {
        "tx_id": tx_id,
        "tx": tx,
        "ownership": ownership,
        "category": category,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


async def handle_callback(
    callback_data: str,
    event: Any,
    engine: Any,
) -> bool:
    """
    Callback handler — Telethon callback event'dan chaqiriladi.

    Returns True if handled.
    """
    # ── OWNERSHIP TOGGLE ──────────────────────────────────────────────
    if callback_data.startswith("howner:"):
        parts = callback_data.split(":")
        if len(parts) != 3:
            return False
        try:
            tx_id = int(parts[1])
            new_owner = parts[2]
        except (ValueError, IndexError):
            return False

        # Update pending entry
        for key, val in list(_pending.items()):
            if val.get("tx_id") == tx_id:
                val["ownership"] = new_owner
                # Rebuild keyboard with new ownership
                kb = build_approval_keyboard(tx_id, new_owner)
                if kb:
                    try:
                        await event.edit(buttons=kb)
                    except Exception as exc:
                        logger.debug("[HISOBCHI] Edit ownership button: %s", exc)
                await event.answer(f"📊 {'🏢 Biznes' if new_owner == 'business' else '🏠 Shaxsiy'} tanlandi")
                return True

        await event.answer("⚠️ Topilmadi")
        return False

    # ── APPROVE ───────────────────────────────────────────────────────
    if callback_data.startswith("happrove:"):
        parts = callback_data.split(":")
        if len(parts) != 3:
            return False
        try:
            tx_id = int(parts[1])
            ownership = parts[2]
        except (ValueError, IndexError):
            return False

        pending = _pending.get(callback_data)
        if not pending:
            # Try to find by tx_id
            for key, val in list(_pending.items()):
                if val.get("tx_id") == tx_id:
                    pending = val
                    break

        if not pending:
            await event.answer("⚠️ Topilmadi yoki allaqachon tasdiqlangan")
            return False

        category = pending.get("category") or "❓ Noma'lum"
        tx = pending.get("tx")

        # Categorize and learn
        try:
            await engine.categorize(tx_id, category, ownership)
            if tx:
                await engine.learn_rule(
                    merchant=tx.merchant,
                    card_suffix=tx.card_suffix,
                    direction=tx.direction,
                    amount=tx.amount,
                    category=category,
                    ownership=ownership,
                )
                await engine.learn_category(tx.merchant, category)
        except Exception as exc:
            logger.error("[HISOBCHI] Approve xatolik: %s", exc)

        # Edit message to show approved status
        try:
            dir_icon = "➖" if tx.direction == "out" else "➕" if tx else "💳"
            owner_label = "🏢 Biznes" if ownership == "business" else "🏠 Shaxsiy"
            approved_text = (
                f"✅ <b>Tasdiqlandi</b>\n\n"
                f"{dir_icon} {_fmt_money(tx.amount) if tx else '?'} UZS\n"
                f"🗂 {html.escape(category)}\n"
                f"📊 {owner_label}"
            )
            await event.edit(approved_text, parse_mode="html")
        except Exception as exc:
            logger.debug("[HISOBCHI] Edit approved text: %s", exc)

        # Cleanup
        for key in list(_pending.keys()):
            if _pending[key].get("tx_id") == tx_id:
                _pending.pop(key, None)

        await event.answer("✅ Tasdiqlandi!")
        return True

    # ── EDIT (show category selection) ────────────────────────────────
    if callback_data.startswith("hedit:"):
        parts = callback_data.split(":")
        if len(parts) != 2:
            return False
        try:
            tx_id = int(parts[1])
        except (ValueError, IndexError):
            return False

        kb = build_category_keyboard(tx_id)
        if kb:
            try:
                await event.edit(
                    "📂 <b>Kategoriyani tanlang:</b>",
                    parse_mode="html",
                    buttons=kb,
                )
            except Exception as exc:
                logger.debug("[HISOBCHI] Edit category keyboard: %s", exc)

        await event.answer("✏️ Kategoriyani tanlang")
        return True

    # ── CATEGORY SELECTION ────────────────────────────────────────────
    if callback_data.startswith("hcat:"):
        parts = callback_data.split(":")
        if len(parts) != 3:
            return False
        try:
            tx_id = int(parts[1])
            category = parts[2].replace(";", ":")
        except (ValueError, IndexError):
            return False

        # Update pending with selected category
        for key, val in list(_pending.items()):
            if val.get("tx_id") == tx_id:
                val["category"] = category
                ownership = val.get("ownership", "business")

                # Show back to approval with selected category
                try:
                    tx = val.get("tx")
                    if tx:
                        msg = build_approval_message(tx, tx_id, ownership)
                        # Prepend category info
                        msg = f"🗂 <b>Kategoriya:</b> {html.escape(category)}\n\n" + msg
                        kb = build_approval_keyboard(tx_id, ownership)
                        if kb:
                            await event.edit(msg, parse_mode="html", buttons=kb)
                except Exception as exc:
                    logger.debug("[HISOBCHI] Edit category selection: %s", exc)
                break

        await event.answer(f"🗂 {category} tanlandi")
        return True

    # ── SKIP ──────────────────────────────────────────────────────────
    if callback_data.startswith("hskip:"):
        parts = callback_data.split(":")
        if len(parts) != 2:
            return False
        try:
            tx_id = int(parts[1])
        except (ValueError, IndexError):
            return False

        try:
            await engine.skip(tx_id)
        except Exception as exc:
            logger.error("[HISOBCHI] Skip xatolik: %s", exc)

        # Edit message
        try:
            await event.edit("⏭ <b>O'tkazib yuborildi</b>", parse_mode="html")
        except Exception as exc:
            logger.debug("[HISOBCHI] Edit skip text: %s", exc)

        # Cleanup
        for key in list(_pending.keys()):
            if _pending[key].get("tx_id") == tx_id:
                _pending.pop(key, None)

        await event.answer("⏭ O'tkazib yuborildi")
        return True

    # ── BACK TO APPROVAL ──────────────────────────────────────────────
    if callback_data.startswith("hback:"):
        parts = callback_data.split(":")
        if len(parts) != 2:
            return False
        try:
            tx_id = int(parts[1])
        except (ValueError, IndexError):
            return False

        for key, val in list(_pending.items()):
            if val.get("tx_id") == tx_id:
                tx = val.get("tx")
                ownership = val.get("ownership", "business")
                if tx:
                    msg = build_approval_message(tx, tx_id, ownership)
                    kb = build_approval_keyboard(tx_id, ownership)
                    if kb:
                        try:
                            await event.edit(msg, parse_mode="html", buttons=kb)
                        except Exception as exc:
                            logger.debug("[HISOBCHI] Edit back to approval: %s", exc)
                break

        await event.answer("🔙 Ortga")
        return True

    return False


async def handle_text_reply(
    event: Any,
    engine: Any,
) -> bool:
    """
    Admin reply text handler — category yoki ownership o'zgartirish uchun.
    Returns True if handled.
    """
    user_id = getattr(event.sender_id, "user_id", None) or getattr(event, "sender_id", None)
    if not user_id:
        return False

    # Check if user is in edit mode
    approve_key = _pending_edit.get(user_id)
    if not approve_key:
        return False

    text = (event.message.message or "").strip()
    if not text:
        return False

    pending = _pending.get(approve_key)
    if not pending:
        _pending_edit.pop(user_id, None)
        return False

    tx_id = pending.get("tx_id")
    ownership = pending.get("ownership", "business")

    # Use replied text as category
    await engine.categorize(tx_id, text, ownership)
    tx = pending.get("tx")
    if tx:
        try:
            await engine.learn_rule(
                merchant=tx.merchant,
                card_suffix=tx.card_suffix,
                direction=tx.direction,
                amount=tx.amount,
                category=text,
                ownership=ownership,
            )
            await engine.learn_category(tx.merchant, text)
        except Exception as exc:
            logger.debug("[HISOBCHI] Learn category from text reply: %s", exc)

    # Edit message
    try:
        dir_icon = "➖" if tx.direction == "out" else "➕" if tx else "💳"
        owner_label = "🏢 Biznes" if ownership == "business" else "🏠 Shaxsiy"
        approved_text = (
            f"✅ <b>Tasdiqlandi</b>\n\n"
            f"{dir_icon} {_fmt_money(tx.amount) if tx else '?'} UZS\n"
            f"🗂 {html.escape(text)}\n"
            f"📊 {owner_label}"
        )
        await event.edit(approved_text, parse_mode="html")
    except Exception as exc:
        logger.debug("[HISOBCHI] Edit text reply approved: %s", exc)

    # Cleanup
    _pending_edit.pop(user_id, None)
    for key in list(_pending.keys()):
        if _pending[key].get("tx_id") == tx_id:
            _pending.pop(key, None)

    return True


def set_pending_edit(user_id: int, approve_key: str) -> None:
    """Edit mode ni activate qiladi."""
    _pending_edit[user_id] = approve_key


def get_pending_count() -> int:
    """Nechta pending approval bor."""
    return len(_pending)


async def prune_old_pending(max_age_seconds: int = 86400) -> None:
    """Eski pending larni tozalash."""
    cutoff = datetime.now(timezone.utc)
    stale = [
        k for k, v in list(_pending.items())
        if (cutoff - datetime.fromisoformat(v["created_at"]).replace(tzinfo=timezone.utc)).total_seconds() > max_age_seconds
    ]
    for k in stale:
        _pending.pop(k, None)
    if stale:
        logger.info("[HISOBCHI] Pruned %d old pending approvals", len(stale))
