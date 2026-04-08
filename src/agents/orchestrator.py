import logging
from typing import Optional, Dict, Any
from src.agents.core import AgentManager

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """Agentlarni boshqarish va vazifalarni yo'naltirish orkestratori."""
    
    def __init__(self, agent_manager: AgentManager):
        self.manager = agent_manager

    async def determine_intent(self, user_message: str, history: Optional[str] = None) -> str:
        """Gemini yordamida user xabari mazmuniga qarab mos agentni tanlash."""
        # Agar PRIMARY model (Gemini) mavjud bo'lsa, undan intentni so'rash
        sales_agent = self.manager.get_agent("sales")
        if not sales_agent or not sales_agent.model_configs["gemini"]["client"]:
            return self._route_intent_fallback(user_message)

        prompt = f"""
        Siz "JonBranding" agentligining "Dispatcher" (Router) botisiz. 
        Vazifangiz - foydalanuvchi xabarini tahlil qilib, uni quyidagi 4 ta agentdan biriga yo'naltirish:
        
        1. 'sales' - Narxlar, xizmatlar, buyurtma berish, to'lov, shartnoma haqidagi savollar. Umuman, asosiy muloqot uchun foydalaniladi.
        2. 'support' - FAQ, texnik muammolar, umumiy yordam.
        3. 'strategist' - Loyiha holati, reja, strategiya (mavjud mijozlar uchun).
        4. 'researcher' - Faqat chuqur bozor tahlili, OSINT yoki raqobatchilarni o'rganish so'ralganda. (Oddiy savollarga ishlatmang).

        FOYDALANUVCHI XABARI: "{user_message}"
        SUHBAT TARIXI (AGAR BO'LSA): {history or "Yo'q"}

        FAQAT agent_id ni qaytaring (sales/support/strategist/researcher). Hech qanday qo'shimcha so'z yozmang.
        """
        
        try:
            client = sales_agent.model_configs["gemini"]["client"]
            model = sales_agent.model_configs["gemini"]["model"]
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            intent = response.text.strip().lower()
            if intent in ["sales", "support", "strategist", "researcher"]:
                return intent
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] LLM routing error: {e}")
            
        return self._route_intent_fallback(user_message)

    def _route_intent_fallback(self, user_message: str) -> str:
        """Zaxira (fallback) keyword-based routing."""
        msg = user_message.lower()
        if any(word in msg for word in ["narx", "qancha", "buyurtma", "xizmat"]):
            return "sales"
        if any(word in msg for word in ["reja", "strategiya", "loyiha", "holat"]):
            return "strategist"
        if any(word in msg for word in ["tadqiqot", "tahlil", "bozor", "raqobatchi"]):
            return "researcher"
        return "sales"

    async def get_agent_response(self, agent_id: str, user_id: int, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Belgilangan agent orqali javob olish."""
        agent = self.manager.get_agent(agent_id)
        if not agent:
            agent = self.manager.get_agent("sales") # Fallback
            
        return await agent.process_task(user_id, message, context=context)
