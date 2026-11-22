"""
OpenClaw (Mr.Jon) <-> Oisha-OS koʻprigi.

OpenClaw gateway barcha tashqi kanallardan (WhatsApp, Slack, Discord, Telegram
@jon_clawbot, Signal, iMessage ...) xabarlarni /webhook/openclaw ga yuboradi.
Ushbu koʻprik Mr.Jon shaxsiyatini (deploy/openclaw/workspace/SOUL.md) saqlagan
holda soʻrovlarni qayta ishlaydi — hech qachon oʻzini Oisha yoki Amina deb
tanishtirmaydi.
"""
from __future__ import annotations

import hashlib
import logging
import os
import pathlib
from typing import Any, Dict, Optional

logger = logging.getLogger("OpenClawBridge")

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_MRJON_SOUL_PATH = _REPO_ROOT / "deploy" / "openclaw" / "workspace" / "SOUL.md"

MRJON_DEFAULT_INSTRUCTION = (
    "Sen Mr.Jonsan — Jon Branding agentligi asoschisi Baxtiyorjon Gaziyevning "
    "raqamli egizagisan (Digital Twin) va agentlikning tashqi yuzisan. "
    "Sen Oisha emassan va Amina emassan. Oʻzingni faqat 'Mr.Jon' deb tanishtir. "
    "Aniq narx, shartnoma sharti yoki chegirma vaʼda qilma; ichki moliya va "
    "xodimlar maʼlumotini oshkor qilma."
)

# Kanal -> user_id prefiks (har bir kanal uchun noyob ID maydoni)
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

# Mr.Jon uchun alohida agent manager va orkestrator (Oisha prompti bilan aralashmasligi uchun)
_agent_manager = None
_orchestrator = None


def load_mrjon_system_instruction(soul_path: Optional[pathlib.Path] = None) -> str:
    """Mr.Jon SOUL.md faylini oʻqish; topilmasa standart Mr.Jon koʻrsatmasini qaytarish."""
    target = soul_path or _MRJON_SOUL_PATH
    try:
        if target.is_file():
            content = target.read_text(encoding="utf-8").strip()
            if content:
                return content
    except OSError:
        logger.debug("[OpenClawBridge] Mr.Jon SOUL.md oʻqilmadi: %s", target, exc_info=True)
    return MRJON_DEFAULT_INSTRUCTION


def _get_numeric_user_id(sender_id: str, channel: str) -> int:
    """Kanal + sender_id dan barqaror int user_id hosil qilish."""
    prefix = _CHANNEL_PREFIX.get(channel.lower(), 9_000_000_000)
    try:
        numeric = int(sender_id)
        return prefix + abs(numeric)
    except (ValueError, TypeError):
        digest = hashlib.sha256(str(sender_id).encode("utf-8")).digest()
        return prefix + int.from_bytes(digest[:8], "big") % 1_000_000_000


def _build_context(
    channel: str, sender: str, metadata: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "source": "openclaw",
        "persona": "mrjon",
        "bot_name": "Mr.Jon",
        "channel": channel,
        "sender_name": sender,
        **metadata,
    }


def _resolve_live_controller() -> Optional[Any]:
    """Ishlab turgan MessageController ni (faqat db va executor uchun) topish."""
    for module_path, attr_holder in (
        ("src.api.routes.state", "api_state"),
        ("src.context", "app_ctx"),
    ):
        try:
            mod = __import__(module_path, fromlist=[attr_holder])
            holder = getattr(mod, attr_holder, None)
            ctrl = getattr(holder, "msg_controller", None)
            if ctrl is not None:
                return ctrl
        except Exception:
            logger.debug("[OpenClawBridge] %s.msg_controller oʻqilmadi", attr_holder, exc_info=True)
    return None


def _register_core_agents(
    manager: Any,
    api_keys: Dict[str, str],
    db: Optional[Any],
    executor: Optional[Any] = None,
) -> None:
    """OpenClaw koʻprigi uchun agentlarni Mr.Jon shaxsiyati (SOUL.md) bilan roʻyxatdan oʻtkazadi."""
    from src.agents.pm_agent import PMAgent
    from src.agents.researcher_agent import ResearcherAgent
    from src.agents.sales_agent import SalesAgent
    from src.agents.support_agent import SupportAgent

    base = load_mrjon_system_instruction()
    manager.register_agent(SalesAgent("sales", base, api_keys, executor, db))
    manager.register_agent(
        PMAgent("strategist", base + "\n\nBrending strategiyasi va loyiha rejasi uchun masʼulsiz.", api_keys, executor, db)
    )
    manager.register_agent(
        ResearcherAgent("researcher", base + "\n\nBozor tahlili va tadqiqot uchun masʼulsiz.", api_keys, executor, db)
    )
    manager.register_agent(
        SupportAgent("support", base + "\n\nMijoz va hamkor savollariga tezkor javob uchun masʼulsiz.", api_keys, executor, db)
    )


async def _get_orchestrator(db: Optional[Any]):
    """Mr.Jon shaxsiyatiga ega alohida AgentOrchestrator qaytarish."""
    global _agent_manager, _orchestrator

    if _orchestrator is not None:
        return _orchestrator

    from src.agents.core import AgentManager
    from src.agents.orchestrator import AgentOrchestrator

    ctrl = _resolve_live_controller()
    resolved_db = db if db is not None else getattr(ctrl, "db", None)
    executor = getattr(ctrl, "executor", None)

    api_keys: Dict[str, str] = dict(getattr(ctrl, "api_keys", None) or {})
    gemini_key = (
        os.environ.get("MRJON_GEMINI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
    if gemini_key:
        api_keys["gemini"] = gemini_key
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        api_keys["groq"] = groq_key

    _agent_manager = AgentManager(api_keys=api_keys)
    _register_core_agents(_agent_manager, api_keys, resolved_db, executor=executor)
    _orchestrator = AgentOrchestrator(agent_manager=_agent_manager)
    logger.info("[OpenClawBridge] Mr.Jon AgentOrchestrator tayyor.")
    return _orchestrator


async def handle_openclaw_message(
    *,
    text: str,
    sender: str = "Mijoz",
    sender_id: str = "openclaw_user",
    channel: str = "telegram",
    session: str = "oisha-main",
    db: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """OpenClaw webhook yoki tashqi kanaldan kelgan xabarni Mr.Jon shaxsiyatida qayta ishlash."""
    if metadata is None:
        metadata = {}

    user_id = _get_numeric_user_id(sender_id, channel)
    context = _build_context(channel, sender, {**metadata, "session": session})

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
        return reply or "Javob tayyorlanmadi. Qayta urinib koʻring."

    except Exception as exc:
        logger.exception("[OpenClawBridge] Xato: %s", exc)
        return (
            "Kechirasiz, hozir texnik muammo yuz berdi. "
            "Biroz kutib qayta yozing yoki Telegram orqali bogʻlaning."
        )
