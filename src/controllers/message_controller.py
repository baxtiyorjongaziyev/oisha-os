import sys
import os

# Set project root to sys.path for absolute imports and backward compatibility
sys.path.append(os.getcwd())

import logging
from typing import Optional, Dict, Any
from src.settings import settings
from src.agents.core import AgentManager
from src.agents.sales_agent import SalesAgent
from src.agents.pm_agent import PMAgent
from src.agents.researcher_agent import ResearcherAgent
from src.agents.support_agent import SupportAgent
from src.agents.copywriter_agent import CopywriterAgent
from src.agents.finance_agent import FinanceAgent
from src.agents.ops_agent import OpsAgent
from src.agents.brief_agent import BriefAgent
from src.agents.welcome_agent import WelcomeAgent
from src.agents.project_update_agent import ProjectUpdateAgent
from src.agents.presentation_agent import PresentationAgent
from src.agents.feedback_agent import FeedbackAgent
from src.agents.referral_agent import ReferralAgent
from src.agents.anniversary_agent import AnniversaryAgent
from src.agents.upsell_agent import UpsellAgent
from src.agents.branding_advisor_agent import BrandingAdvisorAgent
from src.agents.competitor_watch_agent import CompetitorWatchAgent
from src.agents.checklist_agent import ChecklistAgent
from src.agents.naming_agent import NamingAgent, NAMING_SUFFIX
from src.agents.trademark_agent import TrademarkAgent, TRADEMARK_SUFFIX
from src.agents.packaging_agent import PackagingAgent, PACKAGING_SUFFIX
from src.agents.reels_script_agent import ReelsScriptAgent, REELS_SCRIPT_SUFFIX
from src.agents.orchestrator import AgentOrchestrator
from src.agents.negotiation_engine import NegotiationEngine
from src.agents.feedback_memory import FeedbackMemory
from src.services.core.crm.crm_service import CRMService
from src.services.core.google_service import GoogleService
from src.services.core.enterprise_reporter import EnterpriseReporter
from src.agents.tools import AgentToolExecutor
from src.database import Database
import src.config as config

logger = logging.getLogger(__name__)


class MessageController:
    """Xabarlarni qayta ishlash mantiqini boshqaruvchi controller."""

    def __init__(self, api_keys: Dict[str, str], db: Optional[Database] = None):
        self.api_keys = api_keys
        self.db = db or Database()
        self.agent_manager = AgentManager(api_keys)
        self.orchestrator = AgentOrchestrator(self.agent_manager)
        self.negotiation_engine = NegotiationEngine()
        self.feedback_memory = FeedbackMemory(self.db)
        self.crm = CRMService()
        self.google = GoogleService()
        self.enterprise_reporter = EnterpriseReporter(db=self.db, crm=self.crm)

        # Executor initialization (bot_app to be set later)
        self.executor = AgentToolExecutor(
            db=self.db,
            gcontacts=self.google.contacts,
            gcalendar=self.google.calendar,
            gsheet=self.google.sheets,
            amocrm=self.crm.amocrm,  # Corrected parameter name
            gdrive=self.google.drive,
            bot_app=None,  # Will be set via set_bot_app
            config=config,
        )

        # Agentlarni roʻyxatdan oʻtkazish
        # Oisha oʻz-oʻzini onboarding qilish jarayoni
        try:
            from src.services.core.onboarding import get_self_onboarding

            self.onboarding = get_self_onboarding()
            onboarding_context = self.onboarding.get_system_context()
        except Exception as exc:
            logger.warning("[MessageController] Onboarding context yuklanmadi: %s", exc)
            self.onboarding = None
            onboarding_context = ""

        # Barcha agentlar uchun Oisha (Biznes ToV + deploy/oisha/SOUL.md) asosiy koʻrsatma boʻladi
        self._base_instruction = getattr(
            settings, "SYSTEM_INSTRUCTION", "Siz JonBranding yordamchisisiz."
        )
        self._onboarding_context = onboarding_context
        self._soul_mtime: Optional[float] = None
        system_instruction = self._compose_oisha_instruction()
        self._register_all_agents(system_instruction)

    def _compose_oisha_instruction(self) -> str:
        from src.services.core.jamoa_ritm.texts import _OISHA_SOUL_PATH, load_oisha_soul

        try:
            self._soul_mtime = _OISHA_SOUL_PATH.stat().st_mtime if _OISHA_SOUL_PATH.is_file() else None
        except OSError:
            self._soul_mtime = None
        parts = [p for p in (load_oisha_soul(), self._base_instruction, self._onboarding_context) if p]
        return "\n\n".join(parts)

    def _refresh_soul_if_changed(self) -> None:
        from src.services.core.jamoa_ritm.texts import _OISHA_SOUL_PATH

        try:
            current_mtime = _OISHA_SOUL_PATH.stat().st_mtime if _OISHA_SOUL_PATH.is_file() else None
        except OSError:
            current_mtime = None
        if current_mtime != self._soul_mtime:
            self._register_all_agents(self._compose_oisha_instruction())

    def _register_all_agents(self, system_instruction: str) -> None:
        api_keys = self.api_keys
        self.agent_manager.register_agent(
            SalesAgent("sales", system_instruction, api_keys, self.executor, self.db)
        )
        core_defs = (
            ("strategist", PMAgent, "\n\nSiz ayniqsa loyihalarni rejalashtirish va ularni boshqarish boʻyicha masuliyatlisiz."),
            ("researcher", ResearcherAgent, "\n\nSiz ayniqsa bozor tahlili, OSINT yoki chuqur tadqiqotlar uchun masuliyatlisiz."),
            ("support", SupportAgent, "\n\nSiz ayniqsa tezkor yordam va texnik savollar uchun masuliyatlisiz."),
        )
        for aid, cls, suffix in core_defs:
            self.agent_manager.register_agent(
                cls(aid, system_instruction + suffix, api_keys, self.executor, self.db)
            )
        self._register_specialist_agents(system_instruction)

    def _register_specialist_agents(self, system_instruction: str) -> None:
        from src.agents.copywriter_agent import COPYWRITER_SUFFIX
        from src.agents.finance_agent import FINANCE_SUFFIX
        from src.agents.ops_agent import OPS_SUFFIX
        from src.agents.brief_agent import BRIEF_SUFFIX
        from src.agents.welcome_agent import WELCOME_SUFFIX
        from src.agents.project_update_agent import PROJECT_UPDATE_SUFFIX
        from src.agents.presentation_agent import PRESENTATION_SUFFIX
        from src.agents.feedback_agent import FEEDBACK_SUFFIX
        from src.agents.referral_agent import REFERRAL_SUFFIX
        from src.agents.anniversary_agent import ANNIVERSARY_SUFFIX
        from src.agents.upsell_agent import UPSELL_SUFFIX
        from src.agents.branding_advisor_agent import BRANDING_ADVISOR_SUFFIX
        from src.agents.competitor_watch_agent import COMPETITOR_WATCH_SUFFIX
        from src.agents.checklist_agent import CHECKLIST_SUFFIX

        _new_agents = [
            ("copywriter",       CopywriterAgent,       COPYWRITER_SUFFIX),
            ("finance",          FinanceAgent,           FINANCE_SUFFIX),
            ("ops",              OpsAgent,               OPS_SUFFIX),
            ("brief",            BriefAgent,             BRIEF_SUFFIX),
            ("welcome",          WelcomeAgent,           WELCOME_SUFFIX),
            ("project_update",   ProjectUpdateAgent,     PROJECT_UPDATE_SUFFIX),
            ("presentation",     PresentationAgent,      PRESENTATION_SUFFIX),
            ("feedback",         FeedbackAgent,          FEEDBACK_SUFFIX),
            ("referral",         ReferralAgent,          REFERRAL_SUFFIX),
            ("anniversary",      AnniversaryAgent,       ANNIVERSARY_SUFFIX),
            ("upsell",           UpsellAgent,            UPSELL_SUFFIX),
            ("branding_advisor", BrandingAdvisorAgent,   BRANDING_ADVISOR_SUFFIX),
            ("competitor_watch", CompetitorWatchAgent,   COMPETITOR_WATCH_SUFFIX),
            ("checklist",        ChecklistAgent,          CHECKLIST_SUFFIX),
            ("naming",           NamingAgent,            NAMING_SUFFIX),
            ("trademark",        TrademarkAgent,         TRADEMARK_SUFFIX),
            ("packaging",        PackagingAgent,         PACKAGING_SUFFIX),
            ("reels_script",     ReelsScriptAgent,       REELS_SCRIPT_SUFFIX),
        ]
        for agent_id, AgentClass, suffix in _new_agents:
            self.agent_manager.register_agent(
                AgentClass(agent_id, system_instruction + suffix, self.api_keys, self.executor, self.db)
            )

    def set_bot_app(self, bot_app):
        """Telegram application built boʻlgandan soʻng executorga uzatish."""
        self.executor.bot_app = bot_app
        logger.info("[AGENT CONTROLLER] Bot application connected to executor.")

    async def get_response(
        self,
        user_id: int,
        user_name: Optional[str] = None,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **legacy_kwargs,
    ) -> str:
        """Asosiy javob qaytarish mantiqi.

        Older callers still pass `text=` or `message_obj=`. We accept those
        here so the live userbot flow does not silently fail.
        """
        context = context or {}
        if message is None:
            message = legacy_kwargs.get("text")
        if not user_name:
            user_name = context.get("user_name") or "Mijoz"
        if not message:
            return ""
        self._refresh_soul_if_changed()

        # 1. CRM dan user haqida maʼlumot olish (agar tel boʻlsa va mehmon boʻlmasa)
        crm_status = "Yangi mijoz"
        phone = None
        user_info = {}

        if not context.get("is_guest"):
            user_info = await self.db.get_user_info(user_id) or {}
            phone = user_info.get("phone")
            if phone:
                crm_status = await self.crm.get_user_context(phone)
        else:
            crm_status = "Mehmon (Guest Mode)"
            logger.info(f"👸 [GUEST] Skipping CRM lookup for guest: {user_id}")

        # Bot-to-Bot negotiation awareness
        if context.get("is_bot"):
            crm_status = "🤖 Agent (Bot-to-Bot)"
            logger.info(f"👸 [BOT-TO-BOT] Autonomous negotiation detected with uid: {user_id}")

        # Team group mode — inject internal context into all agents
        if context.get("is_team_group"):
            crm_status = f"[JAMOA GURUH] {context.get('chat_title', 'Internal')} | {user_name}"
            logger.info(f"[TEAM GROUP] Request from team member {user_name} in {context.get('chat_title')}")

        context["crm_status"] = crm_status
        context["user_name"] = user_name
        context["phone"] = phone
        context["user_profile"] = user_info
        context["service_type"] = user_info.get("service_type")
        context["business_type"] = user_info.get("business_type")

        # 2. Tarixni olish (NegotiationEngine va Intent uchun)
        recent_history = await self.db.get_recent_messages(user_id, limit=5)
        history_str = ""
        if recent_history:
            history_str = "\n".join(
                f"{'AI' if h.get('role') == 'model' else 'User'}: {h['parts'][0]['text']}"
                for h in recent_history
            )

        # 3. NegotiationEngine — mandatory semantic assessment (Feedback Loop 1)
        neg_history = await self.feedback_memory.get_as_negotiation_history(
            user_id, limit=8
        )
        assessment = None
        try:
            assessment = await self.negotiation_engine.assess_async(
                message=message,
                crm_status=crm_status,
                autonomy_mode="autonomous",
                history=neg_history,
                context=context,
            )
            context["assessment"] = assessment.to_payload()
            context["close_probability"] = assessment.close_probability
            context["autonomy_mode"] = assessment.autonomy_mode
            context["lead_stage"] = assessment.stage
        except Exception as exc:
            logger.warning(f"[MessageController] NegotiationEngine failed: {exc}")

        # 4. Intentni aniqlash (LLM routing)
        agent_id = await self.orchestrator.determine_intent(
            message, history=history_str
        )

        # Standart moliya va kunlik balans boʻyicha ortiqcha savollarni toʻxtatish
        if context.get("is_team_group") and self.onboarding and self.onboarding.should_suppress_clarify_question(message):
            member = self.onboarding.lookup_member(user_name or "")
            if member and member.id == "dilbar":
                if any(w in message.lower() for w in ["kiritdim", "tayyor", "balans", "hisobot"]):
                    return "Balans qabul qilindi, Dilbar opa."

        # Team group: inject internal-mode note and smart silence logic
        if context.get("is_team_group"):
            agent = self.agent_manager.get_agent(agent_id)
            if agent and "_team_mode_active" not in getattr(agent, "_flags", set()):
                _team_note = (
                    "\n\n[ICHKI REJIM — JAMOA GURUHI]"
                    "\nSen hozir Jon Branding jamoasi guruhida har bir xabarni kuzatyapsan."
                    "\nFAQAT quyidagi hollarda javob ber:"
                    "\n  • Senga savol berilgan yoki maʼlumot soʻralgan"
                    "\n  • Raqam, sana, miqdor, holat haqida soʻrov bor"
                    "\n  • Amaliy yordam kerak (topshiriq, deadline, nima qilish kerak)"
                    "\nQuyidagi hollarda HECH NARSA YOZMA (boʻsh satr qaytariladi):"
                    "\n  • Oddiy salomlashish yoki gap (ha, ok, yaxshi, emoji)"
                    "\n  • Jamoa ichki munozarasi (Oishadan savol yoʻq)"
                    "\n  • Xabar faqat boshqa birovga qaratilgan"
                    "\nJavob berayotganda — real maʼlumotlar: search_crm_leads, "
                    "get_airtable_projects, get_today_stats toollarini ishlatib faktlarga asoslan."
                    "\nJavob qisqa va aniq boʻlsin."
                )
                if not hasattr(agent, "_flags"):
                    agent._flags = set()
                agent._flags.add("_team_mode_active")
                agent.system_prompt += _team_note
                context["_team_prompt_injected"] = True

        # 5. Agent orqali javob olish (kontekst + assessment bilan birga)
        response = await self.orchestrator.get_agent_response(
            agent_id, user_id, message, context=context
        )

        # 6. Feedback loop — persist turn + assessment to conversation memory
        try:
            await self.feedback_memory.append(user_id, "user", message, assessment)
            if response:
                await self.feedback_memory.append(user_id, "assistant", response)
        except Exception as exc:
            logger.debug(f"[MessageController] feedback_memory append failed: {exc}")

        return response
