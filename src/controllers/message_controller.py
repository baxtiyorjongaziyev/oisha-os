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
from src.agents.orchestrator import AgentOrchestrator
from src.services.core.crm_service import CRMService
from src.services.debug.google_service import GoogleService
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
        self.crm = CRMService()
        self.google = GoogleService()
        self.enterprise_reporter = EnterpriseReporter(db=self.db, crm=self.crm)
        
        # Executor initialization (bot_app to be set later)
        self.executor = AgentToolExecutor(
            db=self.db,
            gcontacts=self.google.contacts,
            gcalendar=self.google.calendar,
            gsheet=self.google.sheets,
            amocrm=self.crm.amocrm, # Corrected parameter name
            bot_app=None, # Will be set via set_bot_app
            config=config
        )
        
        # Agentlarni ro'yxatdan o'tkazish
        # Barcha agentlar uchun Oisha (Biznes ToV) asosiy ko'rsatma bo'ladi
        system_instruction = getattr(settings, 'SYSTEM_INSTRUCTION', "Siz JonBranding yordamchisisiz.")
        
        self.agent_manager.register_agent(SalesAgent("sales", system_instruction, api_keys, self.executor, self.db))
        
        # PM va Researcher uchun faqat vazifa qo'shamiz, lekin Oisha obrazini saqlaymiz
        pm_prompt = system_instruction + "\n\nSiz ayniqsa loyihalarni rejalashtirish va ularni boshqarish bo'yicha masuliyatlisiz."
        self.agent_manager.register_agent(PMAgent("strategist", pm_prompt, api_keys, self.executor, self.db))
        
        research_prompt = system_instruction + "\n\nSiz ayniqsa bozor tahlili, OSINT yoki chuqur tadqiqotlar uchun masuliyatlisiz."
        self.agent_manager.register_agent(ResearcherAgent("researcher", research_prompt, api_keys, self.executor, self.db))
        
        support_prompt = system_instruction + "\n\nSiz ayniqsa tezkor yordam va texnik savollar uchun masuliyatlisiz."
        self.agent_manager.register_agent(SupportAgent("support", support_prompt, api_keys, self.executor, self.db))

    def set_bot_app(self, bot_app):
        """Telegram application built bo'lgandan so'ng executorga uzatish."""
        self.executor.bot_app = bot_app
        logger.info("[AGENT CONTROLLER] Bot application connected to executor.")

    async def get_response(self, user_id: int, user_name: str, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Asosiy javob qaytarish mantiqi."""
        context = context or {}
        
        # 1. CRM dan user haqida ma'lumot olish (agar tel bo'lsa)
        user_info = await self.db.get_user_info(user_id)
        crm_status = "Yangi mijoz"
        phone = user_info.get("phone") if user_info else None
        
        if phone:
            crm_status = await self.crm.get_user_context(phone)
        
        context["crm_status"] = crm_status
        context["user_name"] = user_name
        context["phone"] = phone
        context["user_profile"] = user_info or {}
        if user_info:
            context["service_type"] = user_info.get("service_type")
            context["business_type"] = user_info.get("business_type")

        # 2. Tarixni olish (Intent uchun)
        recent_history = await self.db.get_recent_messages(user_id, limit=5)
        history_str = ""
        if recent_history:
            history_str = "\n".join(
                f"{'AI' if h.get('role') == 'model' else 'User'}: {h['parts'][0]['text']}"
                for h in recent_history
            )

        # 3. Intentni aniqlash (LLM routing)
        agent_id = await self.orchestrator.determine_intent(message, history=history_str)
        
        # 4. Agent orqali javob olish (kontekst bilan birga)
        return await self.orchestrator.get_agent_response(agent_id, user_id, message, context=context)
