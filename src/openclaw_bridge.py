"""
OpenClaw (Mr.Jon) <-> Oisha-OS koʻprigi.

- `/webhook/openclaw` va `/v1/chat/completions` (`persona="mrjon"`) Mr.Jon shaxsiyati
  (deploy/openclaw/workspace/SOUL.md) va MRJON_GEMINI_API_KEY bilan ishlaydi.
- Oisha Telegram AI (`webhooks.py`, `persona="oisha"`) Oishaning oʻz shaxsiyati va
  jonli MessageController orkestratorini saqlab qoladi.
- `SOUL.md` fayli yangilanganda `oisha.service` ni restart qilmasdan cache avtomatik yangilanadi.
"""
from __future__ import annotations

import hashlib
import importlib
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

_CHANNEL_PREFIX: Dict[str, int] = {
    "telegram": 0, "whatsapp": 1_000_000_000, "slack": 2_000_000_000,
    "discord": 3_000_000_000, "signal": 4_000_000_000, "imessage": 5_000_000_000,
    "teams": 6_000_000_000, "matrix": 7_000_000_000, "webchat": 8_000_000_000,
}

# Mr.Jon tashqi mijozlar bilan gaplashadigan mutaxassislar roʻyxati
_CUSTOMER_SPECIALISTS: tuple[tuple[str, str, str, str], ...] = (
    ("brief", "src.agents.brief_agent", "BriefAgent", "BRIEF_SUFFIX"),
    ("welcome", "src.agents.welcome_agent", "WelcomeAgent", "WELCOME_SUFFIX"),
    ("copywriter", "src.agents.copywriter_agent", "CopywriterAgent", "COPYWRITER_SUFFIX"),
    ("branding_advisor", "src.agents.branding_advisor_agent", "BrandingAdvisorAgent", "BRANDING_ADVISOR_SUFFIX"),
    ("competitor_watch", "src.agents.competitor_watch_agent", "CompetitorWatchAgent", "COMPETITOR_WATCH_SUFFIX"),
    ("naming", "src.agents.naming_agent", "NamingAgent", "NAMING_SUFFIX"),
    ("trademark", "src.agents.trademark_agent", "TrademarkAgent", "TRADEMARK_SUFFIX"),
    ("packaging", "src.agents.packaging_agent", "PackagingAgent", "PACKAGING_SUFFIX"),
    ("reels_script", "src.agents.reels_script_agent", "ReelsScriptAgent", "REELS_SCRIPT_SUFFIX"),
    ("presentation", "src.agents.presentation_agent", "PresentationAgent", "PRESENTATION_SUFFIX"),
    ("feedback", "src.agents.feedback_agent", "FeedbackAgent", "FEEDBACK_SUFFIX"),
    ("upsell", "src.agents.upsell_agent", "UpsellAgent", "UPSELL_SUFFIX"),
    ("referral", "src.agents.referral_agent", "ReferralAgent", "REFERRAL_SUFFIX"),
)

# Ichki operatsion intentlar Mr.Jon tashqi kanallarida strateg/sotuvga yoʻnaltiriladi
_MRJON_INTENT_REMAP: Dict[str, str] = {
    "ops": "strategist",
    "project_update": "strategist",
    "finance": "sales",
    "checklist": "sales",
    "anniversary": "sales",
}

_agent_manager = None
_orchestrator = None
_mrjon_soul_mtime: Optional[float] = None
_oisha_fallback_orchestrator = None


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


def _current_soul_mtime() -> Optional[float]:
    try:
        return _MRJON_SOUL_PATH.stat().st_mtime if _MRJON_SOUL_PATH.is_file() else None
    except OSError:
        return None


def _get_numeric_user_id(sender_id: str, channel: str) -> int:
    """Kanal + sender_id dan barqaror int user_id hosil qilish."""
    prefix = _CHANNEL_PREFIX.get(channel.lower(), 9_000_000_000)
    try:
        return prefix + abs(int(sender_id))
    except (ValueError, TypeError):
        digest = hashlib.sha256(str(sender_id).encode("utf-8")).digest()
        return prefix + int.from_bytes(digest[:8], "big") % 1_000_000_000


def _build_context(channel: str, sender: str, metadata: Dict[str, Any], *, persona: str = "mrjon") -> Dict[str, Any]:
    bot_name = "Oisha" if persona == "oisha" else "Mr.Jon"
    return {"source": "openclaw", "persona": persona, "bot_name": bot_name, "channel": channel, "sender_name": sender, **metadata}


def _resolve_live_controller() -> Optional[Any]:
    """Ishlab turgan MessageController ni topish."""
    for module_path, attr_holder in (("src.api.routes.state", "api_state"), ("src.context", "app_ctx")):
        try:
            holder = getattr(importlib.import_module(module_path), attr_holder, None)
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
    *,
    persona: str = "mrjon",
) -> None:
    """Agentlarni Mr.Jon yoki Oisha shaxsiyati bilan roʻyxatdan oʻtkazish."""
    from src.agents.pm_agent import PMAgent
    from src.agents.researcher_agent import ResearcherAgent
    from src.agents.sales_agent import SalesAgent
    from src.agents.support_agent import SupportAgent

    if persona == "oisha":
        from src.services.core.jamoa_ritm.texts import load_oisha_soul
        from src.settings import settings

        base = load_oisha_soul() or getattr(settings, "SYSTEM_INSTRUCTION", "Siz JonBranding yordamchisisiz.")
    else:
        base = load_mrjon_system_instruction()

    manager.register_agent(SalesAgent("sales", base, api_keys, executor, db))
    manager.register_agent(PMAgent("strategist", base + "\n\nBrending strategiyasi va loyiha rejasi uchun masʼulsiz.", api_keys, executor, db))
    manager.register_agent(ResearcherAgent("researcher", base + "\n\nBozor tahlili va tadqiqot uchun masʼulsiz.", api_keys, executor, db))
    manager.register_agent(SupportAgent("support", base + "\n\nMijoz va hamkor savollariga tezkor javob uchun masʼulsiz.", api_keys, executor, db))

    for agent_id, mod_path, cls_name, suffix_attr in _CUSTOMER_SPECIALISTS:
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, cls_name)
        suffix = getattr(mod, suffix_attr, "")
        manager.register_agent(cls(agent_id, base + suffix, api_keys, executor, db))


def _resolve_api_keys(ctrl: Optional[Any], *, persona: str) -> Dict[str, str]:
    api_keys: Dict[str, str] = dict(getattr(ctrl, "api_keys", None) or {})
    if persona == "mrjon":
        gemini_key = os.environ.get("MRJON_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    else:
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        api_keys["gemini"] = gemini_key
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        api_keys["groq"] = groq_key
    return api_keys


async def _get_orchestrator(db: Optional[Any], *, persona: str = "mrjon"):
    """Persona boʻyicha izolyatsiyalangan AgentOrchestrator qaytarish."""
    global _agent_manager, _orchestrator, _mrjon_soul_mtime, _oisha_fallback_orchestrator
    from src.agents.core import AgentManager
    from src.agents.orchestrator import AgentOrchestrator

    ctrl = _resolve_live_controller()
    if persona == "oisha":
        if ctrl is not None and getattr(ctrl, "orchestrator", None) is not None:
            return ctrl.orchestrator
        if _oisha_fallback_orchestrator is not None:
            return _oisha_fallback_orchestrator
        api_keys = _resolve_api_keys(ctrl, persona="oisha")
        mgr = AgentManager(api_keys=api_keys)
        _register_core_agents(mgr, api_keys, db, persona="oisha")
        _oisha_fallback_orchestrator = AgentOrchestrator(agent_manager=mgr)
        return _oisha_fallback_orchestrator

    soul_mtime = _current_soul_mtime()
    if _orchestrator is not None and soul_mtime == _mrjon_soul_mtime:
        return _orchestrator

    resolved_db = db if db is not None else getattr(ctrl, "db", None)
    executor = getattr(ctrl, "executor", None)
    api_keys = _resolve_api_keys(ctrl, persona="mrjon")
    _agent_manager = AgentManager(api_keys=api_keys)
    _register_core_agents(_agent_manager, api_keys, resolved_db, executor=executor, persona="mrjon")
    _orchestrator = AgentOrchestrator(agent_manager=_agent_manager)
    _mrjon_soul_mtime = soul_mtime
    logger.info("[OpenClawBridge] Mr.Jon AgentOrchestrator tayyor (mtime=%s).", soul_mtime)
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
    persona: str = "mrjon",
) -> str:
    """OpenClaw (Mr.Jon) yoki Telegram AI (Oisha) xabarini mos shaxsiyatda qayta ishlash."""
    if metadata is None:
        metadata = {}
    resolved_persona = "oisha" if persona == "oisha" else "mrjon"
    user_id = _get_numeric_user_id(sender_id, channel)
    context = _build_context(channel, sender, {**metadata, "session": session}, persona=resolved_persona)

    logger.info("[OpenClawBridge:%s] %s/%s (uid=%d): %s", resolved_persona, channel, sender, user_id, text[:80])
    try:
        try:
            orchestrator = await _get_orchestrator(db, persona=resolved_persona)
        except TypeError:
            orchestrator = await _get_orchestrator(db)
        intent = await orchestrator.determine_intent(text)
        if resolved_persona == "mrjon":
            intent = _MRJON_INTENT_REMAP.get(intent, intent)
        reply = await orchestrator.get_agent_response(agent_id=intent, user_id=user_id, message=text, context=context)
        return reply or "Javob tayyorlanmadi. Qayta urinib koʻring."
    except Exception as exc:
        logger.exception("[OpenClawBridge] Xato: %s", exc)
        return "Kechirasiz, hozir texnik muammo yuz berdi. Biroz kutib qayta yozing yoki Telegram orqali bogʻlaning."
