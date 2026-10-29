"""
Delayed DM Responder for Oisha-OS.

Responds to private human Telegram messages only when they remain unanswered
by the owner (Baxtiyorjon Gaziyev) after a configurable delay (default: 15 minutes).
Replies in Baxtiyorjon's authentic personal voice, respecting quiet hours
(delays until 09:00 AM) and strictly excluding family/personal folders,
team members, and escalated issues.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import os
import re
from typing import Any, Dict, List, Optional

from src.time_utils import get_local_now, is_quiet_hours

logger = logging.getLogger("DelayedDmResponder")

# Configuration constants
DEFAULT_DELAY_MINUTES = 15
QUIET_HOURS_START = 22  # 22:00
QUIET_HOURS_END = 9    # 09:00
RATE_LIMIT_COOLDOWN_SECS = 43200  # 12 hours cooldown per chat

FALLBACK_REPLY_TEXT = (
    "Assalomu alaykum! Hozir biroz band edim (uchrashuvdaman). "
    "Xabaringizni ko'rdim, tez orada shaxsan o'zim batafsil javob yozaman."
)

BAXTIYOR_SYSTEM_PROMPT = (
    "Sen — Baxtiyor Gaziyevsan (Jon Branding agentligi asoschisi va art-direktori). "
    "Mijoz senga Telegram shaxsiy xabaringga yozgan. Sen 15 daqiqadan beri band bo'lganing "
    "(uchrashuvda yoki yangi loyiha ustida ishlayotganing) sababli darhol javob bera olmading.\n\n"
    "Vazifa: Mijozga shaxsan o'z nomingdan juda samimiy, xushmuomala, professional va tabiiy javob yoz.\n\n"
    "QAT'IY QOIDALAR:\n"
    "1. O'zingni hech qachon 'bot', 'sun'iy intellekt' yoki 'Oisha' deb tanishtirma. 1-shaxsda ('men', 'biz') gapir.\n"
    "2. Hozir biroz band ekanligingni (uchrashuvdaligingni) samimiy bildir.\n"
    "3. Mijozning savoli yoki mavzusiga qisqa e'tibor qaratib, tez orada shaxsan o'zing batafsil javob yozishingni ayt.\n"
    "4. Hech qanday soxta narx, yolg'on va'da yoki to'qima ma'lumot yozma.\n"
    "5. Matn qisqa va lo'nda bo'lsin (ko'pi bilan 2-3 jumla)."
)


def is_delayed_dm_enabled() -> bool:
    """Check if delayed DM auto-replies are enabled."""
    return os.getenv("ENABLE_DELAYED_DM_AUTO_REPLY", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def get_delay_minutes() -> int:
    """Return configured delay in minutes."""
    try:
        return int(os.getenv("DM_UNANSWERED_DELAY_MINUTES", str(DEFAULT_DELAY_MINUTES)))
    except ValueError:
        return DEFAULT_DELAY_MINUTES


def calculate_target_reply_time(
    now: Optional[datetime] = None, delay_minutes: Optional[int] = None
) -> datetime:
    """Calculate the target reply timestamp, pushing into morning (09:00) if in quiet hours."""
    current = now or get_local_now()
    minutes = delay_minutes if delay_minutes is not None else get_delay_minutes()
    target = current + timedelta(minutes=minutes)

    if is_quiet_hours(target, start_hour=QUIET_HOURS_START, end_hour=QUIET_HOURS_END):
        if target.hour >= QUIET_HOURS_START:
            target_date = target.date() + timedelta(days=1)
        else:
            target_date = target.date()
        return datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            QUIET_HOURS_END,
            0,
            0,
            tzinfo=target.tzinfo,
        )

    return target


class DelayedDmResponder:
    """Manages tracking, delayed evaluation, and sending AI replies for unattended DMs."""

    def __init__(self) -> None:
        self._pending_tasks: Dict[int, asyncio.Task[None]] = {}
        self._pending_info: Dict[int, Dict[str, Any]] = {}
        self._last_replied_times: Dict[int, float] = {}

    def is_active(self) -> bool:
        return is_delayed_dm_enabled()

    def on_owner_reply(self, chat_id: int) -> None:
        """Cancel any pending auto-reply because owner actively responded in this chat."""
        task = self._pending_tasks.pop(chat_id, None)
        info = self._pending_info.pop(chat_id, None)
        if task and not task.done():
            task.cancel()
            logger.info(
                "[DELAYED_DM] Cancelled auto-reply for chat %s (owner replied)", chat_id
            )

    async def register_incoming_dm(
        self,
        event: Any,
        *,
        client: Any,
        db: Any = None,
        admin_bot: Any = None,
        safe_responder: Any = None,
    ) -> None:
        """Register an incoming DM and schedule delayed evaluation if eligible."""
        if not self.is_active():
            return

        chat_id = getattr(event, "chat_id", None)
        if not chat_id or not getattr(event, "is_private", False) or getattr(event, "out", False):
            return

        # Avoid groups or channel IDs
        if chat_id < 0:
            return

        sender = await event.get_sender()
        if not sender or getattr(sender, "bot", False):
            return

        # Check folder exclusion (Family, personal folders)
        from src.entrypoint.filters import _is_personal_folder_sender
        if await _is_personal_folder_sender(sender):
            logger.debug("[DELAYED_DM] Skipping chat %s (personal folder)", chat_id)
            return

        # Check team member
        sender_id = getattr(sender, "id", None)
        username = getattr(sender, "username", "")
        if safe_responder and await safe_responder.is_team_member(sender_id, username):
            logger.debug("[DELAYED_DM] Skipping chat %s (team member)", chat_id)
            return

        # Check escalation triggers
        text = getattr(event, "raw_text", "") or getattr(getattr(event, "message", None), "text", "") or ""
        from src.services.core.auto_reply_gate import _has_escalation_trigger
        trigger = _has_escalation_trigger(text)
        if trigger:
            logger.info(
                "[DELAYED_DM] Skipping chat %s due to escalation trigger: %s",
                chat_id,
                trigger,
            )
            return

        # Cooldown check: max 1 auto-reply per chat in 12 hours
        now_ts = get_local_now().timestamp()
        if (now_ts - self._last_replied_times.get(chat_id, 0.0)) < RATE_LIMIT_COOLDOWN_SECS:
            logger.debug("[DELAYED_DM] Chat %s is within cooldown period", chat_id)
            return

        # If already waiting, let the existing timer continue
        if chat_id in self._pending_tasks and not self._pending_tasks[chat_id].done():
            logger.debug("[DELAYED_DM] Chat %s already has a scheduled reply", chat_id)
            return

        sender_name = getattr(sender, "first_name", "") or getattr(sender, "title", "Mijoz")
        info = {
            "chat_id": chat_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "username": username,
            "arrival_time": now_ts,
            "client": client,
            "db": db,
            "admin_bot": admin_bot,
        }
        self._pending_info[chat_id] = info
        task = asyncio.create_task(self._wait_and_reply(chat_id))
        self._pending_tasks[chat_id] = task
        logger.info(
            "[DELAYED_DM] Scheduled unanswered check for chat %s (%s) in %s mins",
            chat_id,
            sender_name,
            get_delay_minutes(),
        )

    async def _wait_and_reply(self, chat_id: int) -> None:
        """Wait until calculated target time, re-verify, and send auto-reply if unanswered."""
        try:
            target_time = calculate_target_reply_time()
            current = get_local_now()
            wait_seconds = max((target_time - current).total_seconds(), 0.0)

            logger.info(
                "[DELAYED_DM] Chat %s sleeping for %.1f seconds (until %s)",
                chat_id,
                wait_seconds,
                target_time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            await asyncio.sleep(wait_seconds)

            info = self._pending_info.get(chat_id)
            if not info:
                return

            client = info["client"]
            arrival_time = info["arrival_time"]

            # Re-verify against live Telegram chat history
            is_unanswered, messages_text = await self._check_if_still_unanswered(
                client, chat_id, arrival_time
            )
            if not is_unanswered:
                logger.info(
                    "[DELAYED_DM] Chat %s was answered or resolved during wait. Skipping.",
                    chat_id,
                )
                return

            # Generate Baxtiyorjon's voice response
            sender_name = info["sender_name"]
            reply_text = await self.generate_personal_reply(sender_name, messages_text)

            # Send typing indicator for natural feel
            try:
                async with client.action(chat_id, "typing"):
                    await asyncio.sleep(2.0)
            except Exception:
                pass

            # Send message
            await client.send_message(chat_id, reply_text)
            self._last_replied_times[chat_id] = get_local_now().timestamp()
            logger.info("[DELAYED_DM] Successfully sent auto-reply to chat %s", chat_id)

            # Record in database
            db = info.get("db")
            if db:
                try:
                    await db.log_message(chat_id, reply_text, is_ai=True)
                except Exception as db_ex:
                    logger.warning("[DELAYED_DM] Could not log message to DB: %s", db_ex)

            # Notify admin
            admin_bot = info.get("admin_bot")
            if admin_bot:
                username = f"@{info['username']}" if info.get("username") else sender_name
                try:
                    await admin_bot.notify_lead(
                        f"💬 **[Shaxsiy xabar — 15 daqiqa javobsiz]**\n"
                        f"👤 Mijoz: {username} (`{chat_id}`)\n"
                        f"✉️ Xabari: {messages_text[:200]}\n"
                        f"🤖 Baxtiyorjon nomidan yuborildi:\n_{reply_text}_"
                    )
                except Exception as notify_ex:
                    logger.warning("[DELAYED_DM] Admin notification failed: %s", notify_ex)

        except asyncio.CancelledError:
            logger.info("[DELAYED_DM] Wait task cancelled for chat %s", chat_id)
            raise
        except Exception as exc:
            logger.error("[DELAYED_DM] Error processing delayed reply for %s: %s", chat_id, exc)
        finally:
            self._pending_tasks.pop(chat_id, None)
            self._pending_info.pop(chat_id, None)

    async def _check_if_still_unanswered(
        self, client: Any, chat_id: int, arrival_time: float
    ) -> tuple[bool, str]:
        """Check live Telegram history to ensure no outgoing message was sent."""
        try:
            messages = await client.get_messages(chat_id, limit=10)
            if not messages:
                return False, ""

            client_parts: List[str] = []
            for m in messages:
                m_date = getattr(m, "date", None)
                m_ts = m_date.timestamp() if m_date else 0.0

                # If owner sent an outgoing message after our tracked arrival time, abort!
                if getattr(m, "out", False) and m_ts >= (arrival_time - 5.0):
                    return False, ""

                # Collect incoming messages from client
                if not getattr(m, "out", False) and getattr(m, "text", ""):
                    client_parts.append(m.text)

            combined_text = "\n".join(reversed(client_parts[:4]))
            return True, combined_text or "Salom"
        except Exception as exc:
            logger.warning("[DELAYED_DM] Failed to read history for %s: %s", chat_id, exc)
            return False, ""

    async def generate_personal_reply(self, sender_name: str, message_text: str) -> str:
        """Generate response in Baxtiyorjon's tone via Gemini / FreeAIRouter."""
        user_prompt = (
            f"Mijoz ismi: {sender_name}\n"
            f"Mijozning so'nggi xabarlari:\n\"{message_text[:800]}\"\n\n"
            "Vazifa: Baxtiyorjon Gaziyev sifatida juda samimiy, xushmuomala, lo'nda va professional javob yoz."
        )

        # 1. Try Hermes Agent (natural, human-like conversational tone)
        try:
            from src.services.core.ai.hermes_provider import get_hermes_provider
            hermes = get_hermes_provider()
            if hermes.is_available():
                hermes_reply = await hermes.generate_response(
                    user_prompt,
                    system_instruction=BAXTIYOR_SYSTEM_PROMPT,
                    timeout=30,
                )
                if hermes_reply:
                    return hermes_reply.strip().strip('"')
        except Exception as hermes_ex:
            logger.warning("[DELAYED_DM] Hermes generation fallback: %s", hermes_ex)

        # 2. Try Gemini
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                from google import genai
                client = genai.Client(api_key=gemini_key)
                resp = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.0-flash",
                    contents=f"{BAXTIYOR_SYSTEM_PROMPT}\n\n{user_prompt}",
                )
                text = (getattr(resp, "text", "") or "").strip().strip('"')
                if text:
                    return text
            except Exception as gem_ex:
                logger.warning("[DELAYED_DM] Gemini generation fallback: %s", gem_ex)

        # 2. Try FreeAIRouter
        try:
            from src.services.utils.free_ai_router import get_free_ai_router
            res = await get_free_ai_router().generate_text(
                user_prompt,
                system=BAXTIYOR_SYSTEM_PROMPT,
            )
            reply = (getattr(res, "text", "") or "").strip().strip('"')
            if reply:
                return reply
        except Exception as router_ex:
            logger.warning("[DELAYED_DM] FreeAIRouter fallback: %s", router_ex)

        # 3. Deterministic safe fallback
        return FALLBACK_REPLY_TEXT


_SINGLETON_RESPONDER: Optional[DelayedDmResponder] = None


def get_delayed_dm_responder() -> DelayedDmResponder:
    """Singleton getter for DelayedDmResponder."""
    global _SINGLETON_RESPONDER
    if _SINGLETON_RESPONDER is None:
        _SINGLETON_RESPONDER = DelayedDmResponder()
    return _SINGLETON_RESPONDER
