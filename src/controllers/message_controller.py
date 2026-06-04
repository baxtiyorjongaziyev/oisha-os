import sys
import os

# Set project root to sys.path for absolute imports and backward compatibility
sys.path.append(os.getcwd())

import logging
from typing import Optional, Dict, Any
from src.settings import settings, logger
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
from src.agents.orchestrator import AgentOrchestrator
from src.agents.negotiation_engine import NegotiationEngine
from src.agents.feedback_memory import FeedbackMemory
from src.services.core.crm_service import CRMService
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

        # Agentlarni ro'yxatdan o'tkazish
        # Barcha agentlar uchun Oisha (Biznes ToV) asosiy ko'rsatma bo'ladi
        system_instruction = getattr(
            settings, "SYSTEM_INSTRUCTION", "Siz JonBranding yordamchisisiz."
        )

        self.agent_manager.register_agent(
            SalesAgent("sales", system_instruction, api_keys, self.executor, self.db)
        )

        # PM va Researcher uchun faqat vazifa qo'shamiz, lekin Oisha obrazini saqlaymiz
        pm_prompt = (
            system_instruction
            + "\n\nSiz ayniqsa loyihalarni rejalashtirish va ularni boshqarish bo'yicha masuliyatlisiz."
        )
        self.agent_manager.register_agent(
            PMAgent("strategist", pm_prompt, api_keys, self.executor, self.db)
        )

        research_prompt = (
            system_instruction
            + "\n\nSiz ayniqsa bozor tahlili, OSINT yoki chuqur tadqiqotlar uchun masuliyatlisiz."
        )
        self.agent_manager.register_agent(
            ResearcherAgent(
                "researcher", research_prompt, api_keys, self.executor, self.db
            )
        )

        support_prompt = (
            system_instruction
            + "\n\nSiz ayniqsa tezkor yordam va texnik savollar uchun masuliyatlisiz."
        )
        self.agent_manager.register_agent(
            SupportAgent("support", support_prompt, api_keys, self.executor, self.db)
        )

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
        ]
        for agent_id, AgentClass, suffix in _new_agents:
            self.agent_manager.register_agent(
                AgentClass(agent_id, system_instruction + suffix, api_keys, self.executor, self.db)
            )

    def set_bot_app(self, bot_app):
        """Telegram application built bo'lgandan so'ng executorga uzatish."""
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

        # 1. CRM dan user haqida ma'lumot olish (agar tel bo'lsa va mehmon bo'lmasa)
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
