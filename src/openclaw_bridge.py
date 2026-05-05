"""
OpenClaw ↔ Oisha-OS ko'prüsü.

OpenClaw gateway barcha kanallardan (WhatsApp, Slack, Discord, Telegram,
Signal, iMessage ...) xabarlarni /webhook/openclaw ga yuboradi.
Bu modul ularni tegishli Oisha agentiga yo'naltiradi va javob qaytaradi.
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("OpenClawBridge")

# Kanal → user_id prefiks (har bir kanal uchun noyob ID maydoni)
_CHANNEL_PREFIX: Dict[str, int] = {
    "telegram": 0,
    "whatsapp": 1_000_000_000,
    "slack": 2_000_000_000,
    "discord": 3_000_000_000,
    "signal": 4_000_000_000,
    "imessage": 5_000_000_000,
    "teams": 6_000_000_000,
    "matrix": 7_000_000_000,
    "webchat": 8_000_000_000,
}

# Singleton agent manager (birinchi chaqiruvda yaratiladi)
_agent_manager = None
_orchestrator = None


def _get_numeric_user_id(sender_id: str, channel: str) -> int:
    """Kanal + sender_id dan barqaror int user_id hosil qilish."""
    prefix = _CHANNEL_PREFIX.get(channel.lower(), 9_000_000_000)
    try:
        numeric = int(sender_id)
        return prefix + abs(numeric)
    except (ValueError, TypeError):
        return prefix + abs(hash(sender_id)) % 1_000_000_000


def _build_context(
    channel: str, sender: str, metadata: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "source": "openclaw",
        "channel": channel,
        "sender_name": sender,
        **metadata,
    }


async def _get_orchestrator(db: Optional[Any]):
    """Agent manager va orchestratorni lazy init qilish."""
    global _agent_manager, _orchestrator

    if _orchestrator is not None:
        return _orchestrator

    from src.agents.core import AgentManager
    from src.agents.orchestrator import AgentOrchestrator

    api_keys: Dict[str, str] = {}
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        api_keys["gemini"] = gemini_key
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        api_keys["groq"] = groq_key

    _agent_manager = AgentManager(api_keys=api_keys, db=db)
    _orchestrator = AgentOrchestrator(agent_manager=_agent_manager)
    logger.info("[OpenClawBridge] AgentOrchestrator tayyor.")
    return _orchestrator


async def handle_openclaw_message(
    *,
    text: str,
    sender: str,
    sender_id: str,
    channel: str,
    session: str,
    db: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    OpenClaw webhook dan kelgan xabarni qayta ishlash va javob qaytarish.

    Parametrlar:
        text       - foydalanuvchi xabari
        sender     - ko'rsatma ismi (display name)
        sender_id  - kanal ichidagi ID (raqam yoki satr)
        channel    - whatsapp / slack / discord / telegram / ...
        session    - openclaw session nomi
        db         - database instance (yoki None)
        metadata   - qo'shimcha kanal ma'lumotlari
    """
    if metadata is None:
        metadata = {}

    user_id = _get_numeric_user_id(sender_id, channel)
    context = _build_context(channel, sender, metadata)

    logger.info(
        "[OpenClawBridge] %s/%s (uid=%d): %s",
        channel,
        sender,
        user_id,
        text[:80],
    )

    try:
        orchestrator = await _get_orchestrator(db)
        intent = await orchestrator.determine_intent(text)
        reply = await orchestrator.get_agent_response(
            agent_id=intent,
            user_id=user_id,
            message=text,
            context=context,
        )
        return reply or "Javob tayyorlanmadi. Qayta urinib ko'ring."

    except Exception as exc:
        logger.exception("[OpenClawBridge] Xato: %s", exc)
        return (
            "Kechirasiz, hozir texnik muammo yuz berdi. "
            "Biroz kutib qayta yozing yoki Telegram orqali bog'laning."
        )
